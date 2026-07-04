from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_gis_feed_ingestion_patrol_and_district_sharing(client, auth_headers):
    created = await client.post("/crime/feeds", headers=auth_headers, json={
        "name": "Delhi Police GIS", "provider": "district-command", "district": "Central",
    })
    assert created.status_code == 201
    feed, key = created.json(), created.json()["ingest_api_key"]

    ingested = await client.post(
        f"/crime/feeds/{feed['id']}/ingest",
        headers={"X-GIS-API-Key": key},
        json={"type": "FeatureCollection", "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [77.209, 28.6139]},
            "properties": {
                "district": "Central", "crime_type": "digital_fraud",
                "risk_score": 88, "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }]},
    )
    assert ingested.status_code == 200
    assert ingested.json()["accepted"] == 1

    patrol = await client.get("/crime/patrol-plan", headers=auth_headers)
    assert patrol.status_code == 200
    assert patrol.json()["recommendations"][0]["priority_score"] >= 88

    shared = await client.post("/crime/shares", headers=auth_headers, json={
        "source_district": "Central", "target_district": "North",
        "title": "Coordinated mule activity", "summary": "Linked reports cross the district boundary.",
        "severity": "high", "incident_ids": [],
    })
    assert shared.status_code == 201
    acknowledged = await client.post(
        f"/crime/shares/{shared.json()['id']}/acknowledge", headers=auth_headers,
    )
    assert acknowledged.json()["status"] == "acknowledged"


@pytest.mark.asyncio
async def test_multilingual_chat_speech_stream_and_ncrb_boundary(client, auth_headers):
    response = await client.post("/assistant/chat", headers=auth_headers, data={
        "text": "CBI officer says transfer money immediately and share OTP",
        "language": "hi",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "hi"
    assert "OTP" in body["response"]

    stream = await client.post(
        "/assistant/speech/stream/start", headers=auth_headers, json={"language": "hi"},
    )
    assert stream.status_code == 201
    transcript = await client.post(
        f"/assistant/speech/stream/{stream.json()['stream_id']}/transcript",
        headers=auth_headers, json={
            "text": "CBI digital arrest. Do not disconnect. Transfer money immediately and share OTP."
        },
    )
    assert transcript.status_code == 200
    assert "transfer money" in transcript.json()["transcript"].lower()
    final = await client.post(
        f"/assistant/speech/stream/{stream.json()['stream_id']}/finalize", headers=auth_headers,
    )
    assert final.status_code == 200
    assert final.json()["status"] == "finalized"
    assert final.json()["risk_level"] in {"high", "critical"}

    ncrb = await client.post(
        f"/assistant/analyses/{body['analysis_id']}/ncrb-submit", headers=auth_headers,
    )
    assert ncrb.status_code == 202
    assert ncrb.json()["status"] == "not_configured"

    webhook = await client.post("/assistant/channels/whatsapp/webhook", json={
        "sender_reference": "hashed-sender", "text": "check this payment", "language": "en",
    })
    assert webhook.status_code == 401
