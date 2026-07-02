import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
from jose import JWTError, jwt
from app.config.settings import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    if hashed.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        except ValueError:
            return False
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


def create_token(
    subject: UUID | str, token_version: int, token_type: str, *,
    session_id: UUID | str | None = None, jti: str | None = None, remember_me: bool = False,
) -> tuple[str, int]:
    delta = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=30 if remember_me else settings.refresh_token_days)
    )
    now = datetime.now(timezone.utc)
    expires = now + delta
    payload: dict[str, Any] = {
        "sub": str(subject), "type": token_type, "ver": token_version,
        "iat": now, "exp": expires, "jti": jti or secrets.token_urlsafe(24),
    }
    if session_id:
        payload["sid"] = str(session_id)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm), int(delta.total_seconds())


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise ValueError("Invalid token type")
    return payload


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def needs_password_rehash(hashed: str) -> bool:
    return not hashed.startswith("$2")
