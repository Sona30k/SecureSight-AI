import re

import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Notification, UserSession


async def _delivery(recipient: str) -> Notification:
    async with AsyncSessionLocal() as db:
        item = await db.scalar(
            select(Notification)
            .where(Notification.recipient == recipient)
            .order_by(Notification.created_at.desc())
        )
        assert item is not None
        return item


@pytest.mark.asyncio
async def test_verified_citizen_registration_and_session_lifecycle(client):
    payload = {
        "email": "verified@example.com",
        "full_name": "Verified Citizen",
        "phone": "+919876543210",
        "password": "VeryStrong!42",
        "confirm_password": "VeryStrong!42",
        "role": "citizen",
        "accept_terms": True,
    }
    registered = await client.post("/auth/register", json=payload)
    assert registered.status_code == 201
    assert registered.json()["account_status"] == "pending"

    blocked_login = await client.post(
        "/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert blocked_login.status_code == 403

    email_delivery = await _delivery(payload["email"])
    verified_email = await client.post(
        "/auth/verify-email",
        json={"token": email_delivery.metadata_["verification_token"]},
    )
    assert verified_email.status_code == 200

    sms_delivery = await _delivery(payload["phone"])
    otp = re.search(r"\b(\d{6})\b", sms_delivery.body)
    assert otp
    verified_phone = await client.post(
        "/auth/verify-otp",
        json={
            "destination": payload["phone"],
            "code": otp.group(1),
            "purpose": "phone_verification",
        },
    )
    assert verified_phone.status_code == 200

    login = await client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"], "remember_me": True},
    )
    assert login.status_code == 200
    assert login.json()["session_id"]
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    sessions = await client.get("/auth/sessions", headers=headers)
    assert sessions.status_code == 200
    assert sessions.json()[0]["remember_me"] is True

    logout = await client.post("/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert (await client.get("/auth/me", headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rotation_detects_reuse(client):
    await client.post("/auth/register", json={
        "email": "rotate@example.com", "full_name": "Rotate User",
        "password": "VeryStrong!42", "role": "citizen",
    })
    login = await client.post(
        "/auth/login", json={"email": "rotate@example.com", "password": "VeryStrong!42"}
    )
    first_refresh = login.json()["refresh_token"]
    rotated = await client.post("/auth/refresh", json={"refresh_token": first_refresh})
    assert rotated.status_code == 200
    reuse = await client.post("/auth/refresh", json={"refresh_token": first_refresh})
    assert reuse.status_code == 401
    assert "reuse" in reuse.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_lockout_and_password_recovery(client):
    await client.post("/auth/register", json={
        "email": "locked@example.com", "full_name": "Locked User",
        "password": "VeryStrong!42", "role": "citizen",
    })
    for _ in range(5):
        response = await client.post(
            "/auth/login", json={"email": "locked@example.com", "password": "WrongPassword!9"}
        )
        assert response.status_code == 401
    assert (await client.post(
        "/auth/login", json={"email": "locked@example.com", "password": "VeryStrong!42"}
    )).status_code == 423

    recovery = await client.post(
        "/auth/forgot-password", json={"email": "locked@example.com"}
    )
    assert recovery.status_code == 200
    assert recovery.json()["otp"]
    reset = await client.post("/auth/reset-password", json={
        "email": "locked@example.com",
        "otp": recovery.json()["otp"],
        "new_password": "NewStrongPass!43",
    })
    assert reset.status_code == 200
    assert (await client.post(
        "/auth/login", json={"email": "locked@example.com", "password": "NewStrongPass!43"}
    )).status_code == 200


@pytest.mark.asyncio
async def test_non_admin_cannot_access_identity_administration(client):
    await client.post("/auth/register", json={
        "email": "ordinary@example.com", "full_name": "Ordinary Citizen",
        "password": "VeryStrong!42", "role": "citizen",
    })
    login = await client.post(
        "/auth/login", json={"email": "ordinary@example.com", "password": "VeryStrong!42"}
    )
    response = await client.get(
        "/auth/admin/users",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 403
