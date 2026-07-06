from collections import Counter
from datetime import datetime, timezone

import pytest

from app.services.demo_incidents import CITY_HOTSPOTS, INCIDENTS_PER_CITY, SYNTHETIC_MARKER, build_city_incidents


def test_faker_incidents_cover_five_cities_with_7500_clustered_records():
    incidents = build_city_incidents()
    counts = Counter(item["district"] for item in incidents)

    assert len(incidents) == 7_500
    assert counts == {city: INCIDENTS_PER_CITY for city in CITY_HOTSPOTS}
    assert all(item["description"].startswith(SYNTHETIC_MARKER) for item in incidents)
    assert all(25 <= item["risk_score"] <= 99 for item in incidents)


@pytest.mark.asyncio
async def test_cluster_endpoint_aggregates_nearby_incidents(client, auth_headers):
    base = {
        "district": "Cluster Test",
        "crime_type": "UPI Fraud",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": "Test clustering record",
        "risk_score": 80,
    }
    for latitude, longitude in ((28.61391, 77.20901), (28.61394, 77.20904), (28.61401, 77.20910)):
        response = await client.post(
            "/crime/report", headers=auth_headers,
            json={**base, "latitude": latitude, "longitude": longitude},
        )
        assert response.status_code == 201

    response = await client.get("/crime/clusters?district=Cluster%20Test", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_incidents"] == 3
    assert sum(item["incident_count"] for item in body["clusters"]) == 3
