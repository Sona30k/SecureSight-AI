import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from app.config.settings import settings


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = hashed.split("$", 5)
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(
            plain.encode(), salt=base64.urlsafe_b64decode(salt),
            n=int(n), r=int(r), p=int(p), dklen=32,
        )
        return hmac.compare_digest(digest, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError):
        return False


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
