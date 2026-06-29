import pytest

from app.ai.risk_scoring import RiskScoringEngine, RiskSignals


def test_risk_engine_is_bounded_and_explainable():
    score, contributions = RiskScoringEngine().score(RiskSignals(
        spoof_detected=True, suspicious_keywords=9, previous_reports=8,
        unusual_location=True, suspicious_transactions=5, coercion_detected=True,
    ))
    assert score == 100
    assert contributions["spoof_detection"] == 25


@pytest.mark.asyncio
async def test_digital_arrest_analysis(client, auth_headers):
    response = await client.post("/digital-arrest/analyze", headers=auth_headers, json={
        "caller_number": "+919999900000",
        "transcript": "A digital arrest warrant exists. Stay on this call and transfer immediately to the verification account.",
        "duration": 180, "video_call": True, "caller_location": "Unknown",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["risk_score"] >= 75
    assert body["spoof_detected"] is True


@pytest.mark.asyncio
async def test_report_crud(client, auth_headers):
    created = await client.post("/reports", headers=auth_headers, json={
        "title": "UPI impersonation attempt",
        "description": "A caller requested an urgent UPI collect approval.",
        "category": "upi_fraud", "location": "Delhi",
    })
    assert created.status_code == 201
    report_id = created.json()["id"]
    assert (await client.get(f"/reports/{report_id}", headers=auth_headers)).status_code == 200
    assert (await client.put(f"/reports/{report_id}", headers=auth_headers, json={"status": "verified"})).json()["status"] == "verified"
