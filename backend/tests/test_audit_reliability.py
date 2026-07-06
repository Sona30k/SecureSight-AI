import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import AuditLog


@pytest.mark.asyncio
async def test_public_summary_is_available_without_authentication(client):
    response = await client.get("/analytics/public-summary")
    assert response.status_code == 200
    assert set(response.json()) == {
        "fraud_reports", "citizens_protected", "counterfeit_notes",
        "crime_incidents", "ai_analyses", "fraud_entities",
    }


@pytest.mark.asyncio
async def test_failed_login_and_authenticated_mutation_store_outcome_ip_and_timestamp(client, auth_headers):
    failed = await client.post(
        "/auth/login",
        json={"email": "unknown@example.com", "password": "WrongPassword!42"},
    )
    assert failed.status_code == 401

    report = await client.post("/reports", headers=auth_headers, json={
        "title": "Audit test report",
        "description": "Suspicious caller requested an urgent payment.",
        "category": "digital_arrest",
        "risk_score": 88,
    })
    assert report.status_code == 201

    async with AsyncSessionLocal() as db:
        rows = list((await db.scalars(
            select(AuditLog).order_by(AuditLog.created_at.asc())
        )).all())

    login_failure = next(item for item in rows if item.action == "auth.login_failed")
    mutation = next(
        item for item in rows
        if item.action == "http.post" and item.resource_id == "/reports"
    )
    assert login_failure.status == "failure"
    assert mutation.status == "success"
    assert mutation.ip_address
    assert mutation.created_at
