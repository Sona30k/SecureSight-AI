from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_multi_agency_ingestion_is_hashed_deduplicated_and_persisted(client, auth_headers):
    created = await client.post("/graph/feeds", headers=auth_headers, json={
        "name": "Delhi Cyber Cell", "agency_type": "law_enforcement",
        "data_type": "agency_case", "jurisdiction": "Delhi",
    })
    assert created.status_code == 201
    feed = created.json()
    batch = {
        "external_batch_id": "agency-batch-001",
        "events": [{
            "external_event_id": "case-link-001", "event_type": "case_link",
            "source_type": "phone", "source_value": "+919999000001",
            "target_type": "bank_account", "target_value": "HASHED-ACCOUNT-1",
            "relationship": "LINKED_TO",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "attributes": {"risk_score": 91, "source_system": "case-management"},
        }],
    }
    headers = {"X-Intelligence-API-Key": feed["ingest_api_key"]}
    ingested = await client.post(f"/graph/feeds/{feed['id']}/ingest", headers=headers, json=batch)
    assert ingested.status_code == 202
    assert ingested.json()["accepted"] == 1
    assert len(ingested.json()["payload_hash"]) == 64
    assert ingested.json()["graph_status"] in {"synchronized", "stored_graph_pending"}

    duplicate = await client.post(f"/graph/feeds/{feed['id']}/ingest", headers=headers, json=batch)
    assert duplicate.status_code == 202
    assert duplicate.json()["duplicate"] is True

    status = await client.get("/graph/ingestion/status", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["total_events"] == 1
    network = await client.get("/graph/operational-network", headers=auth_headers)
    assert network.status_code == 200
    assert network.json()["statistics"]["source"] == "persisted_graph_events"
    assert network.json()["statistics"]["nodes"] == 2
    assert len(network.json()["edges"]) == 1
    assert all("pagerank" in node and "centrality" in node for node in network.json()["nodes"])


@pytest.mark.asyncio
async def test_evidence_chain_and_cross_jurisdiction_exchange(client, auth_headers):
    acquired = await client.post(
        "/graph/evidence", headers=auth_headers,
        data={
            "case_reference": "FIR-DL-2026-1042", "title": "CDR export",
            "evidence_type": "telecom_cdr", "location": "Delhi Cyber Lab",
        },
        files={"file": ("cdr.csv", b"caller,callee,duration\n100,200,48\n", "text/csv")},
    )
    assert acquired.status_code == 201
    evidence_id = acquired.json()["evidence_id"]
    assert len(acquired.json()["content_hash"]) == 64

    transferred = await client.post(
        f"/graph/evidence/{evidence_id}/custody", headers=auth_headers,
        json={"action": "transferred", "location": "Interstate Desk", "notes": "Sealed handover"},
    )
    assert transferred.status_code == 201
    assert transferred.json()["previous_hash"] != "0" * 64

    verified = await client.get(f"/graph/evidence/{evidence_id}/verify", headers=auth_headers)
    assert verified.status_code == 200
    assert verified.json()["chain_valid"] is True
    assert verified.json()["file_hash_valid"] is True
    assert verified.json()["event_count"] == 2

    exchange = await client.post("/graph/exchanges", headers=auth_headers, json={
        "case_reference": "FIR-DL-2026-1042", "source_jurisdiction": "Delhi",
        "target_jurisdiction": "Haryana", "summary": "Linked telecom and account evidence.",
        "entity_references": ["phone:+919999000001"], "evidence_ids": [evidence_id],
    })
    assert exchange.status_code == 201
    assert len(exchange.json()["package_hash"]) == 64
    acknowledged = await client.post(
        f"/graph/exchanges/{exchange.json()['exchange_id']}/acknowledge", headers=auth_headers,
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
