from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_token
from app.database import get_db
from app.models import User, UserRole

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
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable:
    async def dependency(user: CurrentUser) -> User:
        if user.role not in roles and user.role != UserRole.administrator:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency
