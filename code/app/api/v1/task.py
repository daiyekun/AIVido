from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, PageParam
from app.core.response import ok, ok_page
from app.services import task_service

router = APIRouter(prefix="/task", tags=["task"])


@router.get("/list")
async def list_tasks(db: DbSession, user: CurrentUser, page: PageParam) -> dict:
    items, total = await task_service.list_tasks(db, user.id, page.page, page.size)
    return ok_page(items, total, page.page, page.size)


@router.get("/{task_id}")
async def get_task(db: DbSession, user: CurrentUser, task_id: UUID) -> dict:
    task = await task_service.get_task(db, user.id, task_id)
    return ok(task_service.serialize_task_detail(task))


@router.post("/{task_id}/cancel")
async def cancel_task(db: DbSession, user: CurrentUser, task_id: UUID) -> dict:
    task = await task_service.cancel_task(db, user.id, task_id)
    return ok({"task_id": str(task.task_id), "status": task.status})
