import hashlib
import secrets
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, require_roles
from app.database import get_db
from app.models import AuditLog, CrimeLocation, DistrictIntelligenceShare, GISFeed, User, UserRole
from app.realtime import hub
from app.schemas import CrimeCreate, DistrictShareCreate, GeoJSONIngest, GISFeedCreate

router = APIRouter(prefix="/crime", tags=["Crime Intelligence & Heatmap"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/report", status_code=201)
async def report_crime(payload: CrimeCreate, user: CurrentUser, db: DB):
    item = CrimeLocation(
        latitude=payload.latitude, longitude=payload.longitude, district=payload.district,
        crime_type=payload.crime_type, occurred_at=payload.timestamp,
        description=payload.description, risk_score=payload.risk_score, reported_by=user.id,
    )
    db.add(item)
    await db.commit()
    await hub.broadcast("heatmap", "crime.reported", {"id": str(item.id), "district": item.district, "risk_score": item.risk_score})
    return {"id": item.id, "status": "reported"}


def _filters(district: str | None, crime_type: str | None, start: datetime | None, end: datetime | None):
    result = []
    if district: result.append(CrimeLocation.district == district)
    if crime_type: result.append(CrimeLocation.crime_type == crime_type)
    if start: result.append(CrimeLocation.occurred_at >= start)
    if end: result.append(CrimeLocation.occurred_at <= end)
    return result


@router.get("/heatmap")
async def heatmap(
    user: CurrentUser, db: DB, district: str | None = None, crime_type: str | None = None,
    start: datetime | None = None, end: datetime | None = None,
):
    items = (await db.scalars(select(CrimeLocation).where(*_filters(district, crime_type, start, end)).limit(5000))).all()
    return {"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [x.longitude, x.latitude]},
        "properties": {"id": str(x.id), "district": x.district, "crime_type": x.crime_type, "risk_score": x.risk_score, "timestamp": x.occurred_at.isoformat()},
    } for x in items]}


@router.get("/hotspots")
async def hotspots(user: CurrentUser, db: DB, limit: int = Query(10, ge=1, le=100)):
    rows = (await db.execute(
        select(CrimeLocation.district, func.count().label("incidents"), func.avg(CrimeLocation.risk_score).label("risk"))
        .group_by(CrimeLocation.district).order_by(desc("risk")).limit(limit)
    )).all()
    return [{"district": row.district, "incidents": row.incidents, "predicted_risk": round(float(row.risk), 1)} for row in rows]


@router.get("/statistics")
async def statistics(user: CurrentUser, db: DB):
    total = await db.scalar(select(func.count(CrimeLocation.id))) or 0
    by_type = (await db.execute(select(CrimeLocation.crime_type, func.count()).group_by(CrimeLocation.crime_type))).all()
    return {"total_incidents": total, "by_crime_type": [{"crime_type": x[0], "count": x[1]} for x in by_type]}


@router.post("/feeds", status_code=201)
async def create_feed(
    payload: GISFeedCreate, db: DB,
    user: Annotated[User, Depends(require_roles(UserRole.police, UserRole.administrator))],
):
    raw_key = secrets.token_urlsafe(32)
    feed = GISFeed(
        name=payload.name, provider=payload.provider, district=payload.district,
        api_key_hash=hashlib.sha256(raw_key.encode()).hexdigest(), created_by=user.id,
    )
    db.add(feed)
    await db.commit()
    await db.refresh(feed)
    return {"id": feed.id, "name": feed.name, "ingest_api_key": raw_key, "source_type": feed.source_type}


@router.get("/feeds")
async def list_feeds(
    db: DB, user: Annotated[User, Depends(require_roles(UserRole.police, UserRole.administrator))],
):
    feeds = (await db.scalars(select(GISFeed).order_by(GISFeed.created_at.desc()))).all()
    return [{"id": x.id, "name": x.name, "provider": x.provider, "district": x.district,
             "active": x.active, "last_ingested_at": x.last_ingested_at} for x in feeds]


@router.post("/feeds/{feed_id}/ingest")
async def ingest_geojson(
    feed_id: UUID, payload: GeoJSONIngest, db: DB,
    x_gis_api_key: Annotated[str, Header(min_length=20)],
):
    feed = await db.get(GISFeed, feed_id)
    if not feed or not feed.active or not secrets.compare_digest(
        feed.api_key_hash, hashlib.sha256(x_gis_api_key.encode()).hexdigest()
    ):
        raise HTTPException(status_code=401, detail="Invalid GIS feed credentials")
    accepted, rejected = 0, []
    for index, feature in enumerate(payload.features):
        try:
            geometry = feature["geometry"]
            properties = feature.get("properties") or {}
            if geometry.get("type") != "Point" or len(geometry["coordinates"]) < 2:
                raise ValueError("Only Point geometry is supported")
            longitude, latitude = map(float, geometry["coordinates"][:2])
            if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                raise ValueError("Coordinates outside valid range")
            occurred = datetime.fromisoformat(str(properties.get("timestamp", "")).replace("Z", "+00:00"))
            db.add(CrimeLocation(
                latitude=latitude, longitude=longitude,
                district=str(properties.get("district") or feed.district or "Unknown")[:100],
                crime_type=str(properties.get("crime_type") or "unspecified")[:100],
                occurred_at=occurred, description=str(properties.get("description") or "")[:5000],
                risk_score=max(0, min(100, int(properties.get("risk_score", 50)))),
                reported_by=feed.created_by,
            ))
            accepted += 1
        except (KeyError, TypeError, ValueError) as exc:
            rejected.append({"index": index, "reason": str(exc)})
    feed.last_ingested_at = datetime.now(timezone.utc)
    await db.commit()
    await hub.broadcast("heatmap", "gis.ingested", {"feed_id": str(feed.id), "accepted": accepted})
    return {"accepted": accepted, "rejected": rejected[:100]}


@router.get("/patrol-plan")
async def patrol_plan(
    user: CurrentUser, db: DB, district: str | None = None,
    units: int = Query(4, ge=1, le=50), hours: int = Query(8, ge=1, le=48),
):
    cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600
    query = select(CrimeLocation).where(CrimeLocation.occurred_at >= datetime.fromtimestamp(cutoff, timezone.utc))
    if district:
        query = query.where(CrimeLocation.district == district)
    incidents = (await db.scalars(query.order_by(CrimeLocation.risk_score.desc()).limit(1000))).all()
    buckets: dict[tuple[float, float], dict] = {}
    for incident in incidents:
        key = (round(incident.latitude, 2), round(incident.longitude, 2))
        item = buckets.setdefault(key, {"latitude": key[0], "longitude": key[1], "incidents": 0, "risk": 0, "districts": set()})
        item["incidents"] += 1
        item["risk"] += incident.risk_score
        item["districts"].add(incident.district)
    ranked = sorted(buckets.values(), key=lambda x: x["risk"] + x["incidents"] * 10, reverse=True)[:units]
    return {"generated_at": datetime.now(timezone.utc), "basis": "recent persisted incidents",
            "recommendations": [
                {"priority": i + 1, "latitude": x["latitude"], "longitude": x["longitude"],
                 "district": ", ".join(sorted(x["districts"])), "incident_count": x["incidents"],
                 "priority_score": min(100, round(x["risk"] / max(x["incidents"], 1) + x["incidents"] * 3)),
                 "recommended_action": "Visible patrol and rapid-response staging" if i < 2 else "Directed patrol and community verification"}
                for i, x in enumerate(ranked)
            ], "limitations": "Decision support only; dispatch commanders retain operational authority."}


@router.post("/shares", status_code=201)
async def share_intelligence(
    payload: DistrictShareCreate, db: DB,
    user: Annotated[User, Depends(require_roles(UserRole.police, UserRole.administrator))],
):
    share = DistrictIntelligenceShare(**payload.model_dump(), shared_by=user.id)
    db.add(share)
    await db.commit()
    await db.refresh(share)
    await hub.broadcast("heatmap", "district.intelligence_shared", {"id": str(share.id), "target_district": share.target_district})
    return {"id": share.id, "status": share.status}


@router.get("/shares")
async def list_shares(
    db: DB, user: Annotated[User, Depends(require_roles(UserRole.police, UserRole.administrator))],
    district: str | None = None,
):
    query = select(DistrictIntelligenceShare)
    if district:
        query = query.where(
            (DistrictIntelligenceShare.source_district == district) |
            (DistrictIntelligenceShare.target_district == district)
        )
    items = (await db.scalars(query.order_by(DistrictIntelligenceShare.created_at.desc()).limit(200))).all()
    return [{"id": x.id, "source_district": x.source_district, "target_district": x.target_district,
             "title": x.title, "summary": x.summary, "severity": x.severity, "status": x.status,
             "created_at": x.created_at} for x in items]


@router.post("/shares/{share_id}/acknowledge")
async def acknowledge_share(
    share_id: UUID, db: DB,
    user: Annotated[User, Depends(require_roles(UserRole.police, UserRole.administrator))],
):
    share = await db.get(DistrictIntelligenceShare, share_id)
    if not share:
        raise HTTPException(status_code=404, detail="Intelligence share not found")
    share.status, share.acknowledged_by = "acknowledged", user.id
    share.acknowledged_at = datetime.now(timezone.utc)
    db.add(AuditLog(user_id=user.id, action="district_share.acknowledged", resource="district_share", resource_id=str(share.id)))
    await db.commit()
    return {"id": share.id, "status": share.status}
