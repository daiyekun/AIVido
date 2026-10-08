from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass

import jwt

from app.core.exceptions import TokenExpiredError, UnauthorizedError


@dataclass(frozen=True)
class TokenPayload:
    user_id: int
    salt: str
    issued_at: int
    expires_at: int


def generate_salt() -> str:
    return secrets.token_hex(16)


def create_access_token(user_id: int, salt: str, expire_days: int, jwt_secret: str) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "salt": salt,
        "iat": now,
        "exp": now + expire_days * 86400,
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


def decode_access_token(token: str, jwt_secret: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError() from exc
    try:
        user_id = int(payload.get("sub", "0"))
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError() from exc
    return TokenPayload(
        user_id=user_id,
        salt=str(payload.get("salt", "")),
        issued_at=int(payload.get("iat", 0)),
        expires_at=int(payload.get("exp", 0)),
    )


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise UnauthorizedError()
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise UnauthorizedError()
    return parts[1].strip()


def token_denylist_key(token: str) -> str:
    return "auth:blocked:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def mask_phone(phone: str) -> str:
    if not phone or len(phone) < 7:
        return phone
    return phone[:3] + "****" + phone[-4:]


def prompt_fingerprint(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]
