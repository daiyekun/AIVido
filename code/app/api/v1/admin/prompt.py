from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.deps import DbSession, PageParam
from app.core.response import ok, ok_page
from app.services import prompt_service

router = APIRouter(prefix="/system-prompt", tags=["admin-prompt"])


class PromptPayload(BaseModel):
    prompt_name: str = Field(min_length=1, max_length=128)
    task_type: str
    bind_model_id: int | None = None
    system_content: str = Field(min_length=1)
    is_enable: bool = True
    sort: int = 0
    remark: str = ""


class StatusPayload(BaseModel):
    is_enable: bool


@router.get("/list")
async def list_prompts(
    db: DbSession,
    page: PageParam,
    task_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
) -> dict:
    items, total = await prompt_service.admin_list_prompts(
        db, page.page, page.size, task_type=task_type, keyword=keyword
    )
    return ok_page(items, total, page.page, page.size)


@router.post("/create")
async def create_prompt(db: DbSession, payload: PromptPayload) -> dict:
    prompt = await prompt_service.admin_create_prompt(db, payload.model_dump())
    return ok(prompt_service.serialize_prompt(prompt))


@router.get("/{prompt_id}")
async def get_prompt(db: DbSession, prompt_id: int) -> dict:
    prompt = await prompt_service.admin_get_prompt(db, prompt_id)
    return ok(prompt_service.serialize_prompt(prompt))


@router.put("/{prompt_id}")
async def update_prompt(db: DbSession, prompt_id: int, payload: PromptPayload) -> dict:
    prompt = await prompt_service.admin_update_prompt(db, prompt_id, payload.model_dump())
    return ok(prompt_service.serialize_prompt(prompt))


@router.put("/{prompt_id}/status")
async def set_prompt_status(db: DbSession, prompt_id: int, payload: StatusPayload) -> dict:
    prompt = await prompt_service.admin_set_prompt_status(db, prompt_id, payload.is_enable)
    return ok(prompt_service.serialize_prompt(prompt))
