import pytest
import io
from PIL import Image, ImageDraw

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
    assert body["spoof_detected"] is False
    assert body["spoof_score"] == 0
    assert body["threat_level"] in {"high", "critical"}
    assert body["conversation_stages"]


@pytest.mark.asyncio
async def test_digital_arrest_case_lifecycle(client, auth_headers):
    analyzed = await client.post("/digital-arrest/analyze", headers=auth_headers, json={
        "caller_number": "+919876543210",
        "transcript": (
            "I am from CBI. Your Aadhaar is involved in money laundering. Do not disconnect "
            "this video call. Your bank account will freeze. Transfer money now and share OTP."
        ),
        "duration": 720, "video_call": True, "location": "Delhi",
        "country": "India", "spoof_detected": True,
    })
    assert analyzed.status_code == 200
    result = analyzed.json()
    assert result["risk_score"] >= 90
    assert result["scam_probability"] > .8
    assert {"authority", "threat", "financial"}.issubset({
        span["category"] for span in result["suspicious_spans"]
    })
    assert "Authority impersonation" in result["manipulation_techniques"]
    case_id = result["case_id"]

    history = await client.get(
        "/digital-arrest/history", headers=auth_headers,
        params={"caller_number": "+919876543210"},
    )
    assert history.status_code == 200
    assert history.json()[0]["id"] == case_id

    blocked = await client.post(
        f"/digital-arrest/{case_id}/actions", headers=auth_headers, json={"action": "block"},
    )
    assert blocked.status_code == 200
    assert blocked.json()["blocked"] is True

    reported = await client.post("/digital-arrest/report", headers=auth_headers, json={
        "case_id": case_id, "notes": "Citizen ended the call before transferring funds.",
        "total_victims": 1, "bank_accounts": ["0011223344"], "device_ids": ["device-a"],
    })
    assert reported.status_code == 201
    assert reported.json()["status"] == "reported"

    dashboard = await client.get("/digital-arrest/dashboard", headers=auth_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["total_cases"] == 1
    assert dashboard.json()["blocked_calls"] == 1
    assert dashboard.json()["common_keywords"]

    evidence = await client.get(f"/digital-arrest/{case_id}/evidence.pdf", headers=auth_headers)
    assert evidence.status_code == 200
    assert evidence.headers["content-type"].startswith("application/pdf")
    assert evidence.content.startswith(b"%PDF-1.4")


@pytest.mark.asyncio
async def test_digital_arrest_validates_phone_and_scopes_citizen_history(client, auth_headers):
    invalid = await client.post("/digital-arrest/analyze", headers=auth_headers, json={
        "caller_number": "not-a-number", "transcript": "This is a sufficiently long transcript.",
        "duration": 10,
    })
    assert invalid.status_code == 422

    officer_case = await client.post("/digital-arrest/analyze", headers=auth_headers, json={
        "caller_number": "+919111111111", "transcript": "Routine appointment confirmation call.",
        "duration": 30, "location": "Delhi", "country": "India",
    })
    assert officer_case.status_code == 200

    await client.post("/auth/register", json={
        "email": "citizen@shieldiq.example.com", "full_name": "Citizen Tester",
        "password": "StrongPass!42", "role": "citizen",
    })
    login = await client.post("/auth/login", json={
        "email": "citizen@shieldiq.example.com", "password": "StrongPass!42",
    })
    citizen_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    citizen_history = await client.get("/digital-arrest/history", headers=citizen_headers)
    assert citizen_history.status_code == 200
    assert citizen_history.json() == []


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


@pytest.mark.asyncio
async def test_currency_forensic_lifecycle(client, auth_headers):
    image = Image.new("RGB", (960, 400), (142, 121, 157))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 951, 391), outline=(35, 30, 50), width=6)
    draw.rectangle((280, 20, 298, 380), fill=(85, 78, 98))
    draw.ellipse((490, 65, 700, 335), outline=(45, 40, 60), width=10)
    for x in range(35, 930, 22):
        draw.line((x, 30, x + 18, 370), fill=(65 + x % 100, 70, 110), width=2)
    draw.text((50, 50), "RESERVE BANK OF INDIA 100", fill=(20, 20, 25))
    output = io.BytesIO()
    image.save(output, "PNG")
    response = await client.post(
        "/currency/analyze", headers=auth_headers,
        data={"location": "Test Branch"},
        files={"image": ("note.png", output.getvalue(), "image/png")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["features"]["security_thread"]["confidence"] >= 0
    assert body["detected_note"].startswith("data:image/png;base64,")
    assert body["model_version"] == "shieldiq-currency-forensics-v2"

    history = await client.get("/currency/history", headers=auth_headers)
    assert history.status_code == 200
    assert history.json()[0]["location"] == "Test Branch"
    statistics = await client.get("/currency/statistics", headers=auth_headers)
    assert statistics.status_code == 200
    assert statistics.json()["total_notes_scanned"] == 1
    report = await client.get(f"/currency/{body['case_id']}/report.pdf", headers=auth_headers)
    assert report.status_code == 200
    assert report.content.startswith(b"%PDF")
