import asyncio
import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_roles
from app.config import settings
from app.database import get_db
from app.graph import Neo4jClient
from app.models import (
    CaseExchange, EvidenceCustodyEvent, EvidenceItem, GraphEvent, GraphIngestionBatch,
    IntelligenceFeed, User, UserRole,
)
from app.realtime import hub
from app.schemas import (
    CaseExchangeCreate, CustodyEventCreate, GraphBatchCreate, GraphReport, IntelligenceFeedCreate,
)

router = APIRouter(prefix="/graph", tags=["Fraud Network Graph"])
GraphUser = Annotated[
    User,
    Depends(require_roles(UserRole.police, UserRole.bank, UserRole.telecom_provider)),
]
DB = Annotated[AsyncSession, Depends(get_db)]


def _canonical_hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


async def _client() -> Neo4jClient:
    return Neo4jClient()


@router.post("/create-report", status_code=201)
async def create_graph_report(payload: GraphReport, user: GraphUser):
    client = await _client()
    try:
        return await client.create_report(payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Graph database is unavailable") from exc
    finally:
        await client.close()


@router.get("/network/{case_id}")
async def network(case_id: str, user: GraphUser):
    client = await _client()
    try:
        return await client.network(case_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Graph database is unavailable") from exc
    finally:
        await client.close()


@router.get("/cluster/{cluster_id}")
async def cluster(cluster_id: str, user: GraphUser):
    client = await _client()
    try:
        return await client.network(cluster_id)
    finally:
        await client.close()


@router.get("/high-risk")
async def high_risk(user: GraphUser, minimum: int = Query(70, ge=0, le=100)):
    client = await _client()
    try:
        return {"items": await client.high_risk(minimum)}
    finally:
        await client.close()


@router.post("/feeds", status_code=201)
async def create_feed(payload: IntelligenceFeedCreate, user: GraphUser, db: DB):
    role_map = {"bank": UserRole.bank, "telecom": UserRole.telecom_provider, "law_enforcement": UserRole.police}
    required = role_map.get(payload.agency_type)
    if required and user.role not in {required, UserRole.administrator}:
        raise HTTPException(status_code=403, detail="Feed agency type does not match your role")
    raw_key = secrets.token_urlsafe(36)
    feed = IntelligenceFeed(
        **payload.model_dump(), api_key_hash=hashlib.sha256(raw_key.encode()).hexdigest(), created_by=user.id,
    )
    db.add(feed)
    await db.commit()
    await db.refresh(feed)
    return {"id": feed.id, "name": feed.name, "data_type": feed.data_type, "ingest_api_key": raw_key}


@router.get("/feeds")
async def list_feeds(user: GraphUser, db: DB):
    rows = (await db.scalars(select(IntelligenceFeed).order_by(IntelligenceFeed.created_at.desc()))).all()
    return [{"id": x.id, "name": x.name, "agency_type": x.agency_type, "data_type": x.data_type,
             "jurisdiction": x.jurisdiction, "active": x.active, "last_ingested_at": x.last_ingested_at}
            for x in rows]


@router.post("/feeds/{feed_id}/ingest", status_code=202)
async def ingest_feed(
    feed_id: UUID, payload: GraphBatchCreate, db: DB,
    x_intelligence_api_key: Annotated[str, Header(min_length=20)],
):
    feed = await db.get(IntelligenceFeed, feed_id)
    supplied_hash = hashlib.sha256(x_intelligence_api_key.encode()).hexdigest()
    if not feed or not feed.active or not secrets.compare_digest(feed.api_key_hash, supplied_hash):
        raise HTTPException(status_code=401, detail="Invalid intelligence feed credentials")
    existing = await db.scalar(select(GraphIngestionBatch).where(
        GraphIngestionBatch.feed_id == feed.id,
        GraphIngestionBatch.external_batch_id == payload.external_batch_id,
    ))
    if existing:
        return {"batch_id": existing.id, "status": existing.status, "duplicate": True,
                "accepted": existing.accepted_count, "graph_status": existing.graph_status}
    serialized = payload.model_dump(mode="json")
    batch = GraphIngestionBatch(
        feed_id=feed.id, external_batch_id=payload.external_batch_id,
        event_count=len(payload.events), accepted_count=len(payload.events), rejected_count=0,
        payload_hash=_canonical_hash(serialized), status="accepted", graph_status="pending",
    )
    db.add(batch)
    await db.flush()
    graph_payload = []
    for item in payload.events:
        event_data = item.model_dump(mode="json")
        event_hash = _canonical_hash({"feed_id": str(feed.id), **event_data})
        db.add(GraphEvent(batch_id=batch.id, event_hash=event_hash, **item.model_dump()))
        graph_payload.append({**event_data, "event_hash": event_hash})
    feed.last_ingested_at = datetime.now(timezone.utc)
    await db.commit()
    client = await _client()
    try:
        await client.ingest_events(graph_payload, str(feed.id))
        batch.graph_status = "synchronized"
    except Exception:
        batch.graph_status = "stored_graph_pending"
    finally:
        await client.close()
    await db.commit()
    await hub.broadcast("graph", "graph.batch_ingested", {
        "batch_id": str(batch.id), "feed": feed.name, "events": batch.accepted_count,
        "graph_status": batch.graph_status,
    })
    return {"batch_id": batch.id, "status": batch.status, "duplicate": False,
            "accepted": batch.accepted_count, "payload_hash": batch.payload_hash,
            "graph_status": batch.graph_status}


@router.get("/ingestion/status")
async def ingestion_status(user: GraphUser, db: DB):
    batches = (await db.scalars(
        select(GraphIngestionBatch).order_by(GraphIngestionBatch.created_at.desc()).limit(100)
    )).all()
    total_events = await db.scalar(select(func.count(GraphEvent.id))) or 0
    return {"total_events": total_events, "batches": [
        {"id": x.id, "feed_id": x.feed_id, "external_batch_id": x.external_batch_id,
         "accepted": x.accepted_count, "status": x.status, "graph_status": x.graph_status,
         "payload_hash": x.payload_hash, "created_at": x.created_at} for x in batches
    ]}


@router.get("/operational-network")
async def operational_network(
    user: GraphUser, db: DB, limit: int = Query(5000, ge=1, le=20_000),
):
    events = (await db.scalars(
        select(GraphEvent).order_by(GraphEvent.occurred_at.desc()).limit(limit)
    )).all()
    nodes: dict[str, dict] = {}
    adjacency: dict[str, set[str]] = {}
    edges = []
    for event in events:
        source_id = f"{event.source_type}:{event.source_value}"
        target_id = f"{event.target_type}:{event.target_value}"
        risk = max(0, min(100, int(event.attributes.get("risk_score", 0) or 0)))
        for node_id, kind, value in (
            (source_id, event.source_type, event.source_value),
            (target_id, event.target_type, event.target_value),
        ):
            node = nodes.setdefault(node_id, {
                "id": node_id, "type": kind, "label": value, "risk_score": 0,
                "first_seen": event.occurred_at.isoformat(), "last_seen": event.occurred_at.isoformat(),
            })
            node["risk_score"] = max(node["risk_score"], risk)
            node["last_seen"] = max(node["last_seen"], event.occurred_at.isoformat())
            adjacency.setdefault(node_id, set())
        adjacency[source_id].add(target_id)
        adjacency[target_id].add(source_id)
        edges.append({
            "source": source_id, "target": target_id, "type": event.relationship,
            "event_type": event.event_type, "occurred_at": event.occurred_at,
        })
    count = len(nodes)
    pagerank = {node_id: 1 / count for node_id in nodes} if count else {}
    for _ in range(12):
        next_rank = {node_id: (1 - .85) / count for node_id in nodes} if count else {}
        for node_id, neighbors in adjacency.items():
            if neighbors:
                share = .85 * pagerank[node_id] / len(neighbors)
                for neighbor in neighbors:
                    next_rank[neighbor] += share
        pagerank = next_rank
    cluster_map, cluster_index = {}, 0
    for root in nodes:
        if root in cluster_map:
            continue
        cluster_index += 1
        stack, cluster_map[root] = [root], f"C{cluster_index:04d}"
        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor not in cluster_map:
                    cluster_map[neighbor] = cluster_map[root]
                    stack.append(neighbor)
    for node_id, node in nodes.items():
        node["centrality"] = round(len(adjacency[node_id]) / max(1, count - 1), 4)
        node["pagerank"] = round(pagerank.get(node_id, 0), 6)
        node["cluster_id"] = cluster_map[node_id]
        node["connections"] = len(adjacency[node_id])
    return {
        "nodes": list(nodes.values()), "edges": edges,
        "statistics": {"nodes": count, "edges": len(edges), "clusters": cluster_index, "source": "persisted_graph_events"},
    }


def _custody_hash(
    evidence_id: UUID, action: str, actor_id: UUID, occurred_at: datetime,
    previous_hash: str, location: str | None, notes: str | None,
) -> str:
    normalized_time = occurred_at
    if normalized_time.tzinfo is not None:
        normalized_time = normalized_time.astimezone(timezone.utc).replace(tzinfo=None)
    return _canonical_hash({
        "evidence_id": str(evidence_id), "action": action, "actor_id": str(actor_id),
        "occurred_at": f"{normalized_time.isoformat(timespec='microseconds')}Z", "previous_hash": previous_hash,
        "location": location, "notes": notes,
    })


@router.post("/evidence", status_code=201)
async def acquire_evidence(
    user: GraphUser, db: DB, case_reference: str = Form(..., min_length=1, max_length=150),
    title: str = Form(..., min_length=2, max_length=200),
    evidence_type: str = Form(..., min_length=2, max_length=60),
    location: str | None = Form(None, max_length=200),
    file: UploadFile = File(...),
):
    content = await file.read()
    if not content or len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Evidence file must be between 1 byte and 25 MB")
    content_hash = hashlib.sha256(content).hexdigest()
    evidence_dir = settings.storage_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "evidence.bin").suffix[:12]
    target = evidence_dir / f"{content_hash}{suffix}"
    if not target.exists():
        await asyncio.to_thread(target.write_bytes, content)
    item = EvidenceItem(
        case_reference=case_reference, title=title, evidence_type=evidence_type,
        content_hash=content_hash, storage_reference=str(target),
        metadata_={"filename": file.filename, "content_type": file.content_type, "size": len(content)},
        created_by=user.id,
    )
    db.add(item)
    await db.flush()
    occurred = datetime.now(timezone.utc)
    event = EvidenceCustodyEvent(
        evidence_id=item.id, action="acquired", actor_id=user.id, location=location,
        notes="Initial evidence acquisition", previous_hash="0" * 64, occurred_at=occurred,
        event_hash=_custody_hash(item.id, "acquired", user.id, occurred, "0" * 64, location, "Initial evidence acquisition"),
    )
    db.add(event)
    await db.commit()
    return {"evidence_id": item.id, "content_hash": content_hash, "custody_event_id": event.id}


@router.post("/evidence/{evidence_id}/custody", status_code=201)
async def add_custody_event(evidence_id: UUID, payload: CustodyEventCreate, user: GraphUser, db: DB):
    item = await db.get(EvidenceItem, evidence_id)
    if not item:
        raise HTTPException(status_code=404, detail="Evidence not found")
    previous = await db.scalar(select(EvidenceCustodyEvent).where(
        EvidenceCustodyEvent.evidence_id == evidence_id
    ).order_by(EvidenceCustodyEvent.occurred_at.desc()))
    previous_hash = previous.event_hash if previous else "0" * 64
    occurred = datetime.now(timezone.utc)
    event = EvidenceCustodyEvent(
        evidence_id=evidence_id, actor_id=user.id, occurred_at=occurred,
        previous_hash=previous_hash,
        event_hash=_custody_hash(
            evidence_id, payload.action, user.id, occurred, previous_hash, payload.location, payload.notes,
        ),
        **payload.model_dump(),
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return {"event_id": event.id, "event_hash": event.event_hash, "previous_hash": event.previous_hash}


@router.get("/evidence/{evidence_id}/verify")
async def verify_evidence(evidence_id: UUID, user: GraphUser, db: DB):
    item = await db.get(EvidenceItem, evidence_id)
    if not item:
        raise HTTPException(status_code=404, detail="Evidence not found")
    events = (await db.scalars(select(EvidenceCustodyEvent).where(
        EvidenceCustodyEvent.evidence_id == evidence_id
    ).order_by(EvidenceCustodyEvent.occurred_at.asc()))).all()
    previous_hash, valid = "0" * 64, True
    for event in events:
        expected = _custody_hash(
            evidence_id, event.action, event.actor_id, event.occurred_at,
            previous_hash, event.location, event.notes,
        )
        if event.previous_hash != previous_hash or not secrets.compare_digest(expected, event.event_hash):
            valid = False
            break
        previous_hash = event.event_hash
    file_path = Path(item.storage_reference)
    file_valid = file_path.exists() and secrets.compare_digest(
        item.content_hash, hashlib.sha256(await asyncio.to_thread(file_path.read_bytes)).hexdigest()
    )
    return {"evidence_id": evidence_id, "chain_valid": valid, "file_hash_valid": file_valid,
            "event_count": len(events), "content_hash": item.content_hash, "latest_chain_hash": previous_hash}


@router.get("/evidence/{evidence_id}/download")
async def download_evidence(evidence_id: UUID, user: GraphUser, db: DB):
    item = await db.get(EvidenceItem, evidence_id)
    if not item or not Path(item.storage_reference).exists():
        raise HTTPException(status_code=404, detail="Evidence file not found")
    return FileResponse(item.storage_reference, filename=item.metadata_.get("filename") or f"{evidence_id}.bin")


@router.post("/exchanges", status_code=201)
async def create_exchange(payload: CaseExchangeCreate, user: GraphUser, db: DB):
    evidence = []
    for evidence_id in payload.evidence_ids:
        item = await db.get(EvidenceItem, evidence_id)
        if not item or item.case_reference != payload.case_reference:
            raise HTTPException(status_code=422, detail=f"Evidence {evidence_id} is not part of this case")
        evidence.append({"id": str(item.id), "content_hash": item.content_hash, "title": item.title})
    package = {**payload.model_dump(mode="json"), "evidence_manifest": evidence,
               "created_at": datetime.now(timezone.utc).isoformat()}
    exchange = CaseExchange(
        case_reference=payload.case_reference, source_jurisdiction=payload.source_jurisdiction,
        target_jurisdiction=payload.target_jurisdiction, package_hash=_canonical_hash(package),
        payload=package, shared_by=user.id,
    )
    db.add(exchange)
    await db.commit()
    await db.refresh(exchange)
    return {"exchange_id": exchange.id, "status": exchange.status, "package_hash": exchange.package_hash}


@router.get("/exchanges")
async def list_exchanges(user: GraphUser, db: DB):
    rows = (await db.scalars(select(CaseExchange).order_by(CaseExchange.created_at.desc()).limit(200))).all()
    return [{"id": x.id, "case_reference": x.case_reference, "source_jurisdiction": x.source_jurisdiction,
             "target_jurisdiction": x.target_jurisdiction, "status": x.status,
             "package_hash": x.package_hash, "created_at": x.created_at} for x in rows]


@router.post("/exchanges/{exchange_id}/acknowledge")
async def acknowledge_exchange(exchange_id: UUID, user: GraphUser, db: DB):
    exchange = await db.get(CaseExchange, exchange_id)
    if not exchange:
        raise HTTPException(status_code=404, detail="Case exchange not found")
    exchange.status, exchange.acknowledged_by = "acknowledged", user.id
    exchange.acknowledged_at = datetime.now(timezone.utc)
    await db.commit()
    return {"exchange_id": exchange.id, "status": exchange.status, "package_hash": exchange.package_hash}
