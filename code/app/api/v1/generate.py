from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.core.response import ok
from app.core.tracing import current_trace_id
from app.services import task_service

router = APIRouter(prefix="/generate", tags=["generate"])


class GenerateRequest(BaseModel):
    gen_type: str
    model_id: int
    prompt: str
    negative_prompt: str | None = None
    resolution: str | None = None
    aspect_ratio: str | None = None
    duration: int | None = None
    n: int = 1
    denoising_strength: float | None = None
    video_sub_mode: str | None = None
    asset_object_key: str | None = None
    extra: dict = Field(default_factory=dict)


@router.post("/task")
async def create_generate_task(payload: GenerateRequest, db: DbSession, user: CurrentUser) -> dict:
    trace_id = current_trace_id()
    result = await task_service.create_generate_task(db, user, payload.model_dump(), trace_id)
    return ok(result)
