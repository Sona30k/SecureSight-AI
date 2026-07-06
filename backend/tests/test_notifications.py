import pytest

from app.database import AsyncSessionLocal
from app.models import Notification


@pytest.mark.asyncio
async def test_notification_inbox_is_scoped_and_supports_read_state(client, auth_headers):
    me = (await client.get("/auth/me", headers=auth_headers)).json()
    async with AsyncSessionLocal() as db:
        personal = Notification(
            channel="email",
            recipient=me["email"],
            subject="Account update",
            body="Your command profile was updated.",
            status="sent",
        )
        shared = Notification(
            channel="push",
            recipient="police-dashboard",
            subject="Critical risk alert",
            body="A high-risk digital arrest case requires review.",
            status="queued",
        )
        private = Notification(
            channel="email",
            recipient="another@example.com",
            subject="Private verification",
            body="This must not appear in another user's inbox.",
            status="queued",
        )
        db.add_all([personal, shared, private])
        await db.commit()
        await db.refresh(shared)
        shared_id = str(shared.id)

    inbox = await client.get("/notifications", headers=auth_headers)
    assert inbox.status_code == 200
    subjects = {item["subject"] for item in inbox.json()["items"]}
    assert {"Account update", "Critical risk alert"}.issubset(subjects)
    assert "Private verification" not in subjects
    assert all(item["read"] is False for item in inbox.json()["items"])

    marked = await client.post(f"/notifications/{shared_id}/read", headers=auth_headers)
    assert marked.status_code == 200
    refreshed = await client.get("/notifications", headers=auth_headers)
    shared_item = next(item for item in refreshed.json()["items"] if item["id"] == shared_id)
    assert shared_item["read"] is True
