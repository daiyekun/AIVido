from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.prompt import AiSystemPrompt


async def get_prompt_by_id(session: AsyncSession, prompt_id: int) -> AiSystemPrompt | None:
    stmt = select(AiSystemPrompt).where(AiSystemPrompt.prompt_id == prompt_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_enabled_by_task_type(session: AsyncSession, task_type: str) -> list[AiSystemPrompt]:
    stmt = (
        select(AiSystemPrompt)
        .where(
            AiSystemPrompt.task_type == task_type,
            AiSystemPrompt.is_enable.is_(True),
        )
        .order_by(AiSystemPrompt.sort.desc(), AiSystemPrompt.prompt_id.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _apply_filters(stmt, *, task_type: str | None, keyword: str | None):
    if task_type:
        stmt = stmt.where(AiSystemPrompt.task_type == task_type)
    if keyword:
        stmt = stmt.where(AiSystemPrompt.prompt_name.ilike(f"%{keyword}%"))
    return stmt


async def list_prompts_page(
    session: AsyncSession,
    *,
    task_type: str | None = None,
    keyword: str | None = None,
    offset: int,
    limit: int,
) -> list[AiSystemPrompt]:
    stmt = _apply_filters(select(AiSystemPrompt), task_type=task_type, keyword=keyword)
    stmt = stmt.order_by(AiSystemPrompt.prompt_id.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_prompts(
    session: AsyncSession,
    *,
    task_type: str | None = None,
    keyword: str | None = None,
) -> int:
    stmt = _apply_filters(
        select(func.count()).select_from(AiSystemPrompt), task_type=task_type, keyword=keyword
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())
