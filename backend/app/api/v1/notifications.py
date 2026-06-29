from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
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
    items = (await db.scalars(select(Notification).order_by(desc(Notification.created_at)).limit(100))).all()
    return {"items": [{"id": x.id, "channel": x.channel, "recipient": x.recipient, "subject": x.subject, "status": x.status, "created_at": x.created_at} for x in items]}
