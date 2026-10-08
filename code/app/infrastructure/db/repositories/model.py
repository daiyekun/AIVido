from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.ai_model import AiModel


async def get_model_by_id(session: AsyncSession, model_id: int) -> AiModel | None:
    stmt = select(AiModel).where(AiModel.model_id == model_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_enabled_models_by_type(session: AsyncSession, model_type: str) -> list[AiModel]:
    stmt = (
        select(AiModel)
        .where(AiModel.model_type == model_type, AiModel.is_enable.is_(True))
        .order_by(AiModel.sort.asc(), AiModel.model_id.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _apply_filters(stmt, *, model_type: str | None, keyword: str | None):
    if model_type:
        stmt = stmt.where(AiModel.model_type == model_type)
    if keyword:
        stmt = stmt.where(AiModel.model_name.ilike(f"%{keyword}%"))
    return stmt


async def list_models_page(
    session: AsyncSession,
    *,
    model_type: str | None = None,
    keyword: str | None = None,
    offset: int,
    limit: int,
) -> list[AiModel]:
    stmt = _apply_filters(select(AiModel), model_type=model_type, keyword=keyword)
    stmt = stmt.order_by(AiModel.model_id.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_models(
    session: AsyncSession,
    *,
    model_type: str | None = None,
    keyword: str | None = None,
) -> int:
    stmt = _apply_filters(
        select(func.count()).select_from(AiModel), model_type=model_type, keyword=keyword
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())
