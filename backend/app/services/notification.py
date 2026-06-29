from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification
from app.schemas import NotificationCreate


class NotificationService:
    async def queue(self, db: AsyncSession, payload: NotificationCreate) -> Notification:
        notification = Notification(
            channel=payload.channel, recipient=payload.recipient, subject=payload.subject,
            body=payload.body, metadata_=payload.metadata, status="queued",
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification

    async def mark_sent(self, db: AsyncSession, notification: Notification) -> None:
        notification.status = "sent"
        notification.sent_at = datetime.now(timezone.utc)
        await db.commit()
