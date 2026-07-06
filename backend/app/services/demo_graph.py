import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from faker import Faker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph import Neo4jClient
from app.models import GraphEvent, GraphIngestionBatch, IntelligenceFeed, User

SEED_NAME = "ShieldIQ Synthetic Fraud Intelligence"
SEED_BATCH = "shieldiq-faker-network-v1"
ENTITY_COUNTS = {
    "phone": 120,
    "device": 100,
    "bank_account": 100,
    "upi": 100,
    "complaint": 100,
}


def _hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_fraud_graph(seed: int = 20260706) -> list[dict[str, Any]]:
    """Build a deterministic, realistic synthetic network with 520 unique entities."""
    fake = Faker("en_IN")
    fake.seed_instance(seed)
    now = datetime.now(timezone.utc)
    complaints = [f"CMP-{now.year}-{index + 1:05d}" for index in range(ENTITY_COUNTS["complaint"])]
    phones = [f"+91{fake.unique.random_number(digits=10, fix_len=True)}" for _ in range(ENTITY_COUNTS["phone"])]
    devices = [f"DEV-{fake.unique.uuid4().split('-')[0].upper()}" for _ in range(ENTITY_COUNTS["device"])]
    bank_accounts = [
        f"{fake.random_element(('SBI', 'HDFC', 'ICICI', 'AXIS', 'PNB'))}-{fake.unique.random_number(digits=12, fix_len=True)}"
        for _ in range(ENTITY_COUNTS["bank_account"])
    ]
    upi_ids = [
        f"{fake.unique.user_name()[:28]}@{fake.random_element(('oksbi', 'okaxis', 'ybl', 'paytm', 'ibl'))}"
        for _ in range(ENTITY_COUNTS["upi"])
    ]
    events: list[dict[str, Any]] = []

    def add(
        source_type: str, source_value: str, target_type: str, target_value: str,
        relationship: str, event_type: str, index: int, risk_score: int,
    ) -> None:
        external_id = f"SYN-{len(events) + 1:05d}"
        occurred_at = now - timedelta(minutes=(index * 17) % 43_200)
        payload = {
            "external_event_id": external_id,
            "event_type": event_type,
            "source_type": source_type,
            "source_value": source_value,
            "target_type": target_type,
            "target_value": target_value,
            "relationship": relationship,
            "occurred_at": occurred_at,
            "attributes": {
                "risk_score": risk_score,
                "synthetic": True,
                "source_system": "shieldiq-faker-demo",
                "jurisdiction": fake.random_element((
                    "Delhi", "Maharashtra", "Karnataka", "Rajasthan",
                    "West Bengal", "Tamil Nadu", "Telangana", "Uttar Pradesh",
                )),
            },
        }
        payload["event_hash"] = _hash(payload)
        events.append(payload)

    # Every operational entity is anchored to a complaint.
    entity_groups = (
        ("phone", phones, "REPORTED_IN", "call"),
        ("device", devices, "OBSERVED_IN", "device_observation"),
        ("bank_account", bank_accounts, "NAMED_IN", "transaction"),
        ("upi", upi_ids, "NAMED_IN", "transaction"),
    )
    for group_offset, (kind, values, relationship, event_type) in enumerate(entity_groups):
        for index, value in enumerate(values):
            complaint_index = index % len(complaints)
            risk = 52 + ((index * 11 + group_offset * 7) % 47)
            add(kind, value, "complaint", complaints[complaint_index], relationship, event_type, index, risk)

    # Twelve connected campaigns keep the graph readable while exposing shared infrastructure.
    campaign_roots = complaints[:12]
    for index, complaint in enumerate(complaints[12:], start=12):
        root = campaign_roots[index % len(campaign_roots)]
        add("complaint", complaint, "complaint", root, "SAME_CAMPAIGN", "case_link", index, 60 + index % 39)
    for index, phone in enumerate(phones):
        add("phone", phone, "device", devices[index % len(devices)], "USES_DEVICE", "device_observation", index, 58 + index % 41)
    for index, account in enumerate(bank_accounts):
        add("bank_account", account, "upi", upi_ids[index], "SETTLES_UPI", "transaction", index, 62 + index % 37)
        add("phone", phones[index], "upi", upi_ids[index], "CONTROLS_UPI", "case_link", index, 57 + (index * 3) % 42)
    return events


async def seed_fraud_graph(db: AsyncSession, admin: User) -> dict[str, int | str | bool]:
    existing = await db.scalar(
        select(GraphIngestionBatch).where(GraphIngestionBatch.external_batch_id == SEED_BATCH)
    )
    if existing:
        count = len(build_fraud_graph())
        return {"created": False, "events": count, "entities": sum(ENTITY_COUNTS.values())}

    feed = await db.scalar(select(IntelligenceFeed).where(IntelligenceFeed.name == SEED_NAME))
    if not feed:
        feed = IntelligenceFeed(
            name=SEED_NAME,
            agency_type="law_enforcement",
            data_type="agency_case",
            jurisdiction="Multi-state synthetic demonstration",
            api_key_hash=_hash({"feed": SEED_NAME}),
            active=True,
            created_by=admin.id,
        )
        db.add(feed)
        await db.flush()

    events = build_fraud_graph()
    batch = GraphIngestionBatch(
        feed_id=feed.id,
        external_batch_id=SEED_BATCH,
        event_count=len(events),
        accepted_count=len(events),
        rejected_count=0,
        payload_hash=_hash(events),
        status="accepted",
        graph_status="pending",
    )
    db.add(batch)
    await db.flush()
    for event in events:
        db.add(GraphEvent(batch_id=batch.id, **event))
    feed.last_ingested_at = datetime.now(timezone.utc)
    await db.commit()

    client = Neo4jClient()
    try:
        neo4j_events = [
            {**event, "occurred_at": event["occurred_at"].isoformat()}
            for event in events
        ]
        await client.ingest_events(neo4j_events, str(feed.id))
        batch.graph_status = "synchronized"
    except Exception:
        batch.graph_status = "stored_graph_pending"
    finally:
        await client.close()
    await db.commit()
    return {
        "created": True,
        "events": len(events),
        "entities": sum(ENTITY_COUNTS.values()),
        "graph_status": batch.graph_status,
    }
