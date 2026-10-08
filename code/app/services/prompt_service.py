from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PromptNotFoundError
from app.domain.model_config import validate_prompt_payload
from app.domain.prompt import PromptCandidate, PromptMatch, match_prompt
from app.infrastructure.db.models.prompt import AiSystemPrompt
from app.infrastructure.db.repositories import prompt as prompt_repo

logger = logging.getLogger("ainew.prompt")


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def serialize_prompt(prompt: AiSystemPrompt) -> dict[str, Any]:
    return {
        "prompt_id": prompt.prompt_id,
        "prompt_name": prompt.prompt_name,
        "task_type": prompt.task_type,
        "bind_model_id": prompt.bind_model_id,
        "system_content": prompt.system_content,
        "is_enable": prompt.is_enable,
        "sort": prompt.sort,
        "remark": prompt.remark or "",
        "create_time": _iso(prompt.create_time),
        "update_time": _iso(prompt.update_time),
    }


async def match_system_prompt(
    db: AsyncSession, task_type: str, model_id: int | None
) -> PromptMatch | None:
    prompts = await prompt_repo.list_enabled_by_task_type(db, task_type)
    candidates = [
        PromptCandidate(
            prompt_id=p.prompt_id,
            task_type=p.task_type,
            bind_model_id=p.bind_model_id,
            system_content=p.system_content,
            is_enable=p.is_enable,
            sort=p.sort,
        )
        for p in prompts
    ]
    return match_prompt(task_type, model_id, candidates)


async def admin_list_prompts(
    db: AsyncSession,
    page: int,
    size: int,
    task_type: str | None = None,
    keyword: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    offset = (page - 1) * size
    total = await prompt_repo.count_prompts(db, task_type=task_type, keyword=keyword)
    prompts = await prompt_repo.list_prompts_page(
        db, task_type=task_type, keyword=keyword, offset=offset, limit=size
    )
    return [serialize_prompt(p) for p in prompts], total


async def admin_get_prompt(db: AsyncSession, prompt_id: int) -> AiSystemPrompt:
    prompt = await prompt_repo.get_prompt_by_id(db, prompt_id)
    if prompt is None:
        raise PromptNotFoundError()
    return prompt


async def admin_create_prompt(db: AsyncSession, payload: dict[str, Any]) -> AiSystemPrompt:
    fields = validate_prompt_payload(payload)
    prompt = AiSystemPrompt(**fields)
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    logger.info("prompt_created", extra={"prompt_id": prompt.prompt_id})
    return prompt


async def admin_update_prompt(
    db: AsyncSession, prompt_id: int, payload: dict[str, Any]
) -> AiSystemPrompt:
    prompt = await admin_get_prompt(db, prompt_id)
    fields = validate_prompt_payload(payload)
    for key, value in fields.items():
        setattr(prompt, key, value)
    await db.commit()
    await db.refresh(prompt)
    logger.info("prompt_updated", extra={"prompt_id": prompt_id})
    return prompt


async def admin_set_prompt_status(
    db: AsyncSession, prompt_id: int, is_enable: bool
) -> AiSystemPrompt:
    prompt = await admin_get_prompt(db, prompt_id)
    prompt.is_enable = is_enable
    await db.commit()
    await db.refresh(prompt)
    logger.info("prompt_status_changed", extra={"prompt_id": prompt_id, "is_enable": is_enable})
    return prompt
