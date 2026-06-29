from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, create_token, decode_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, Message, RefreshRequest, RegisterRequest, TokenPair, UserRead

router = APIRouter(prefix="/auth", tags=["Authentication"])
DB = Annotated[AsyncSession, Depends(get_db)]


def _tokens(user: User) -> TokenPair:
    access, expires = create_token(user.id, user.token_version, "access")
    refresh, _ = create_token(user.id, user.token_version, "refresh")
    return TokenPair(access_token=access, refresh_token=refresh, expires_in=expires)


@router.post("/register", response_model=UserRead, status_code=201)
async def register(payload: RegisterRequest, db: DB):
    if await db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = User(
        email=payload.email.lower(), full_name=payload.full_name,
        hashed_password=hash_password(payload.password), role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: DB):
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    return _tokens(user)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser):
    return user


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DB):
    try:
        claims = decode_token(payload.refresh_token, "refresh")
        user = await db.get(User, claims["sub"])
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if not user or not user.is_active or user.token_version != claims.get("ver"):
        raise HTTPException(status_code=401, detail="Refresh token was revoked")
    return _tokens(user)


@router.post("/logout", response_model=Message)
async def logout(user: CurrentUser, db: DB):
    user.token_version += 1
    await db.commit()
    return Message(message="All active tokens have been revoked")
