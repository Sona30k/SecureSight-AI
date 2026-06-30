import io

import pytest
from sqlalchemy import func, select

from app.config.settings import settings
from app.database import AsyncSessionLocal
from app.models import AIAnalysis


@pytest.mark.asyncio
async def test_privileged_self_registration_is_disabled_outside_demo(client):
    original = settings.demo_mode
    settings.demo_mode = False
    try:
        response = await client.post("/auth/register", json={
            "email": "attacker@example.com", "full_name": "Privilege Escalation",
            "password": "StrongPass!42", "role": "administrator",
        })
        assert response.status_code == 403
    finally:
        settings.demo_mode = original


@pytest.mark.asyncio
async def test_citizen_cannot_access_agency_analytics(client):
    await client.post("/auth/register", json={
        "email": "citizen-rbac@example.com", "full_name": "Citizen User",
        "password": "StrongPass!42", "role": "citizen",
    })
    login = await client.post("/auth/login", json={"email": "citizen-rbac@example.com", "password": "StrongPass!42"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.get("/analytics/dashboard", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_logout_revokes_access_token(client):
    await client.post("/auth/register", json={
        "email": "logout@example.com", "full_name": "Logout User",
        "password": "StrongPass!42", "role": "citizen",
    })
    login = await client.post("/auth/login", json={"email": "logout@example.com", "password": "StrongPass!42"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.post("/auth/logout", headers=headers)).status_code == 200
    assert (await client.get("/auth/me", headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_currency_upload_rejects_spoofed_mime_type(client, auth_headers):
    response = await client.post(
        "/ai/currency-detection", headers=auth_headers,
        files={"image": ("note.png", io.BytesIO(b"this is not a png"), "image/png")},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ai_prediction_is_persisted(client, auth_headers):
    response = await client.post("/ai/scam-detection", headers=auth_headers, json={
        "caller_number": "+919999900000", "transcript": "CBI digital arrest. Transfer immediately.",
        "duration": 300, "video_call": True, "previous_reports": 3, "spoof_detected": True,
    })
    assert response.status_code == 200
    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(func.count(AIAnalysis.id)))
    assert count == 1
