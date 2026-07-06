from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, require_roles
from app.database import get_db
from app.models import Notification, User, UserRole
from app.schemas import NotificationCreate
from app.services import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])
NotificationSender = Annotated[
    User,
    Depends(require_roles(UserRole.police, UserRole.bank, UserRole.telecom_provider)),
]


@router.post("", status_code=202)
async def send_notification(payload: NotificationCreate, user: NotificationSender, db: Annotated[AsyncSession, Depends(get_db)]):
    item = await NotificationService().queue(db, payload)
    return {"id": item.id, "status": item.status}


@router.get("")
async def notification_history(user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    recipients = [str(user.id), user.email]
    if user.phone:
        recipients.append(user.phone)
    conditions = [Notification.recipient.in_(recipients)]
    if user.role in {UserRole.police, UserRole.administrator}:
        conditions.append(Notification.recipient == "police-dashboard")
    items = (await db.scalars(
        select(Notification)
        .where(or_(*conditions))
        .order_by(desc(Notification.created_at))
        .limit(100)
    )).all()
    user_id = str(user.id)
    return {"items": [{
        "id": x.id,
        "channel": x.channel,
        "subject": x.subject,
        "body": x.body,
        "status": x.status,
        "created_at": x.created_at,
        "read": user_id in (x.metadata_ or {}).get("read_by", []),
    } for x in items]}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    item = await db.get(Notification, notification_id)
    allowed_recipients = {str(user.id), user.email, user.phone}
    shared_with_user = (
        item
        and item.recipient == "police-dashboard"
        and user.role in {UserRole.police, UserRole.administrator}
    )
    if not item or (item.recipient not in allowed_recipients and not shared_with_user):
        raise HTTPException(status_code=404, detail="Notification not found")
    metadata = dict(item.metadata_ or {})
    read_by = list(metadata.get("read_by", []))
    if str(user.id) not in read_by:
        read_by.append(str(user.id))
        metadata["read_by"] = read_by
        item.metadata_ = metadata
        await db.commit()
    return {"id": item.id, "read": True}
