import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, status

from app.core.config import settings


def hash_otp(phone_number: str, otp: str) -> str:
    message = f"{phone_number}:{otp}".encode("utf-8")
    return hmac.new(
        settings.jwt_secret_key.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()


def create_jwt(
    user_id: int, token_type: str, lifetime: timedelta
) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + lifetime
    token_id = secrets.token_urlsafe(24)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": token_id,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")
    return token, token_id, expires_at.replace(tzinfo=None)


def decode_jwt(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub", "jti", "type"]},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token geçersiz veya süresi dolmuş.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bu işlem için uygun token türü değil.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
