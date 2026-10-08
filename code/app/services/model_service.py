from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ModelNotFoundError
from app.domain.model_config import validate_model_payload
from app.infrastructure.cache.redis_client import cache_delete
from app.infrastructure.db.models.ai_model import AiModel
from app.infrastructure.db.repositories import model as model_repo

logger = logging.getLogger("ainew.model")

MODEL_CACHE_PREFIX = "cfg:model:"


async def _invalidate_model_cache(model_id: int) -> None:
    try:
        await cache_delete(MODEL_CACHE_PREFIX + str(model_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("model_cache_invalidate_failed", extra={"model_id": model_id, "error": str(exc)})


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _build_price_tip(price_config: dict[str, Any]) -> str:
    if not price_config:
        return ""
    parts = []
    for key, value in price_config.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            parts.append(f"{key}:{value}积分")
    return "，".join(parts)


def serialize_model_public(model: AiModel) -> dict[str, Any]:
    return {
        "model_id": model.model_id,
        "model_name": model.model_name,
        "model_type": model.model_type,
        "sort": model.sort,
        "support_resolution": model.support_resolution or [],
        "support_duration": model.support_duration or [],
        "price_tip": _build_price_tip(model.price_config_json or {}),
    }


def serialize_model_admin(model: AiModel) -> dict[str, Any]:
    return {
        "model_id": model.model_id,
        "model_name": model.model_name,
        "model_type": model.model_type,
        "adapter_key": model.adapter_key,
        "is_enable": model.is_enable,
        "sort": model.sort,
        "support_resolution": model.support_resolution or [],
        "support_duration": model.support_duration or [],
        "config_json": model.config_json or {},
        "price_config_json": model.price_config_json or {},
        "remark": model.remark or "",
        "create_time": _iso(model.create_time),
        "update_time": _iso(model.update_time),
    }


async def list_enabled_models(db: AsyncSession, model_type: str) -> list[dict[str, Any]]:
    models = await model_repo.list_enabled_models_by_type(db, model_type)
    return [serialize_model_public(m) for m in models]


async def admin_list_models(
    db: AsyncSession,
    page: int,
    size: int,
    model_type: str | None = None,
    keyword: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    offset = (page - 1) * size
    total = await model_repo.count_models(db, model_type=model_type, keyword=keyword)
    models = await model_repo.list_models_page(
        db, model_type=model_type, keyword=keyword, offset=offset, limit=size
    )
    return [serialize_model_admin(m) for m in models], total


async def admin_get_model(db: AsyncSession, model_id: int) -> AiModel:
    model = await model_repo.get_model_by_id(db, model_id)
    if model is None:
        raise ModelNotFoundError()
    return model


async def admin_create_model(db: AsyncSession, payload: dict[str, Any]) -> AiModel:
    fields = validate_model_payload(payload)
    model = AiModel(**fields)
    db.add(model)
    await db.commit()
    await db.refresh(model)
    logger.info("model_created", extra={"model_id": model.model_id, "model_name": model.model_name})
    return model


async def admin_update_model(db: AsyncSession, model_id: int, payload: dict[str, Any]) -> AiModel:
    model = await admin_get_model(db, model_id)
    fields = validate_model_payload(payload)
    for key, value in fields.items():
        setattr(model, key, value)
    await db.commit()
    await db.refresh(model)
    await _invalidate_model_cache(model_id)
    logger.info("model_updated", extra={"model_id": model_id})
    return model


async def admin_set_model_status(db: AsyncSession, model_id: int, is_enable: bool) -> AiModel:
    model = await admin_get_model(db, model_id)
    model.is_enable = is_enable
    await db.commit()
    await db.refresh(model)
    await _invalidate_model_cache(model_id)
    logger.info("model_status_changed", extra={"model_id": model_id, "is_enable": is_enable})
    return model
