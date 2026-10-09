from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ParamError,
    PhoneNotRegisteredError,
    PhoneRegisteredError,
)
from app.core.security import create_access_token, generate_salt, token_denylist_key
from app.infrastructure.cache.redis_client import cache_set
from app.infrastructure.db.models.user import SysUser
from app.services.sms_service import verify_sms_code

logger = logging.getLogger("ainew.auth")


async def register(db: AsyncSession, phone: str, code: str, agreement: bool) -> SysUser:
    if not agreement:
        raise ParamError("请先阅读并同意用户协议、隐私政策与生成式 AI 使用声明")
    await verify_sms_code(phone, code)

    existing = await db.execute(
        select(SysUser).where(SysUser.phone == phone, SysUser.is_deleted.is_(False))
    )
    if existing.scalar_one_or_none() is not None:
        raise PhoneRegisteredError()

    user = SysUser(phone=phone, jwt_salt=generate_salt())
    db.add(user)
    await db.commit()
    logger.info("user_registered", extra={"user_id": user.id, "phone": phone})
    return user


async def login(db: AsyncSession, phone: str, code: str) -> dict[str, object]:
    await verify_sms_code(phone, code)

    result = await db.execute(
        select(SysUser).where(SysUser.phone == phone, SysUser.is_deleted.is_(False))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise PhoneNotRegisteredError()

    token = create_access_token(
        user_id=user.id,
        salt=user.jwt_salt,
        expire_days=settings.jwt_expire_days,
        jwt_secret=settings.jwt_secret,
    )
    logger.info("user_login", extra={"user_id": user.id, "phone": phone})
    return {
        "token": token,
        "expire_days": settings.jwt_expire_days,
        "user_id": user.id,
        "phone": user.phone,
        "is_admin": bool(user.is_admin),
    }


async def logout(token: str, expires_at: int) -> None:
    ttl = max(expires_at - int(time.time()), 1)
    await cache_set(token_denylist_key(token), "1", ex=ttl)
    logger.info("user_logout", extra={"token_fingerprint": token_denylist_key(token)[:24]})
