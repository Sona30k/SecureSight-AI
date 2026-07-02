from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_token
from app.database import get_db
from app.models import User, UserRole, UserSession

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = decode_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user or not user.is_active or user.token_version != payload.get("ver"):
        raise HTTPException(status_code=401, detail="User is inactive or token was revoked")
    if payload.get("sid"):
        try:
            session_id = UUID(payload["sid"])
        except (ValueError, TypeError):
            raise HTTPException(status_code=401, detail="Invalid session")
        session = await db.scalar(select(UserSession).where(
            UserSession.id == session_id, UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > datetime.now(timezone.utc),
        ))
        if not session:
            raise HTTPException(status_code=401, detail="Session expired or revoked")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable:
    async def dependency(user: CurrentUser) -> User:
        if user.role not in roles and user.role != UserRole.administrator:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency
