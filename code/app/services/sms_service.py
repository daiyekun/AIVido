from __future__ import annotations

import logging
import secrets
from datetime import date

from app.core.config import settings
from app.core.exceptions import ParamError, SmsCodeError
from app.infrastructure.cache.redis_client import cache_delete, cache_get, cache_set

logger = logging.getLogger("ainew.sms")

CODE_KEY_PREFIX = "sms:code:"
RATE_KEY_PREFIX = "sms:rate:"
DAILY_KEY_PREFIX = "sms:daily:"


def _validate_phone(phone: str) -> None:
    if not phone or not phone.isdigit() or len(phone) != 11:
        raise ParamError("手机号格式非法")


async def _check_rate_limit(phone: str) -> None:
    rate_key = RATE_KEY_PREFIX + phone
    if await cache_get(rate_key) is not None:
        raise ParamError("验证码发送过于频繁，请稍后再试")

    daily_key = DAILY_KEY_PREFIX + phone + ":" + date.today().isoformat()
    daily_count_raw = await cache_get(daily_key)
    daily_count = int(daily_count_raw) if daily_count_raw else 0
    if daily_count >= settings.sms_daily_limit:
        raise ParamError("验证码发送次数已达今日上限")


async def send_sms_code(phone: str) -> None:
    _validate_phone(phone)
    if not settings.dev_sms_endpoint:
        await _check_rate_limit(phone)

    code = settings.sms_dev_fixed_code or secrets.randbelow(900000) + 100000
    code_key = CODE_KEY_PREFIX + phone
    await cache_set(code_key, str(code), ex=settings.sms_code_ttl_seconds)

    rate_key = RATE_KEY_PREFIX + phone
    await cache_set(rate_key, "1", ex=settings.sms_rate_seconds)

    daily_key = DAILY_KEY_PREFIX + phone + ":" + date.today().isoformat()
    daily_count_raw = await cache_get(daily_key)
    daily_count = int(daily_count_raw) if daily_count_raw else 0
    await cache_set(daily_key, str(daily_count + 1), ex=86400)

    if settings.sms_provider_key and settings.sms_provider_url:
        logger.info(
            "sms_send",
            extra={"phone": phone, "channel": "provider"},
        )
    else:
        logger.info(
            "sms_send_dev",
            extra={"phone": phone, "channel": "dev_fixed"},
        )


async def verify_sms_code(phone: str, code: str) -> None:
    _validate_phone(phone)
    if not code:
        raise ParamError("验证码不能为空")
    if settings.dev_sms_endpoint:
        if code != settings.sms_dev_fixed_code:
            raise SmsCodeError()
        return
    code_key = CODE_KEY_PREFIX + phone
    stored = await cache_get(code_key)
    if stored is None or stored != code:
        raise SmsCodeError()
    await cache_delete(code_key)
