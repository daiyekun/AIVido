from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.deps import DbSession, PageParam
from app.core.response import ok, ok_page
from app.services import model_service

router = APIRouter(prefix="/model", tags=["admin-model"])


class ModelPayload(BaseModel):
    model_name: str = Field(min_length=1, max_length=128)
    model_type: str
    adapter_key: str
    is_enable: bool = True
    sort: int = 0
    support_resolution: list[str] = Field(default_factory=list)
    support_duration: list[int] = Field(default_factory=list)
    config_json: dict = Field(default_factory=dict)
    price_config_json: dict = Field(default_factory=dict)
    remark: str = ""


class StatusPayload(BaseModel):
    is_enable: bool


@router.get("/list")
async def list_models(
    db: DbSession,
    page: PageParam,
    model_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
) -> dict:
    items, total = await model_service.admin_list_models(
        db, page.page, page.size, model_type=model_type, keyword=keyword
    )
    return ok_page(items, total, page.page, page.size)


@router.post("/create")
async def create_model(db: DbSession, payload: ModelPayload) -> dict:
    model = await model_service.admin_create_model(db, payload.model_dump())
    return ok(model_service.serialize_model_admin(model))


@router.get("/{model_id}")
async def get_model(db: DbSession, model_id: int) -> dict:
    model = await model_service.admin_get_model(db, model_id)
    return ok(model_service.serialize_model_admin(model))


@router.put("/{model_id}")
async def update_model(db: DbSession, model_id: int, payload: ModelPayload) -> dict:
    model = await model_service.admin_update_model(db, model_id, payload.model_dump())
    return ok(model_service.serialize_model_admin(model))


@router.put("/{model_id}/status")
async def set_model_status(db: DbSession, model_id: int, payload: StatusPayload) -> dict:
    model = await model_service.admin_set_model_status(db, model_id, payload.is_enable)
    return ok(model_service.serialize_model_admin(model))
