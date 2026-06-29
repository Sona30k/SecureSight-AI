from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config.settings import settings

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    pbkdf2_sha256__default_rounds=600_000,
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(subject: UUID | str, token_version: int, token_type: str) -> tuple[str, int]:
    delta = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    now = datetime.now(timezone.utc)
    expires = now + delta
    payload: dict[str, Any] = {
        "sub": str(subject), "type": token_type, "ver": token_version,
        "iat": now, "exp": expires,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm), int(delta.total_seconds())


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise ValueError("Invalid token type")
    return payload
