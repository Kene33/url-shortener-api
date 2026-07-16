import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import Settings

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user_id: int, settings: Settings) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.access_token_minutes)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + expires_delta,
        "jti": secrets.token_urlsafe(16),
    }
    token = jwt.encode(payload, settings.auth_secret_key, algorithm="HS256")
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str, settings: Settings) -> int | None:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=["HS256"],
            options={"require": ["sub", "type", "iat", "exp", "jti"]},
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    try:
        return int(payload["sub"])
    except (TypeError, ValueError):
        return None


def create_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def expires_at(*, minutes: int = 0, hours: int = 0, days: int = 0) -> str:
    value = datetime.now(UTC) + timedelta(minutes=minutes, hours=hours, days=days)
    return value.strftime("%Y-%m-%d %H:%M:%S")
