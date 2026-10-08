from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.core.response import ok
from app.services import model_service

router = APIRouter(prefix="/model", tags=["model"])


@router.get("/image/list")
async def list_image_models(db: DbSession) -> dict:
    items = await model_service.list_enabled_models(db, "image")
    return ok(items)


@router.get("/video/list")
async def list_video_models(db: DbSession) -> dict:
    items = await model_service.list_enabled_models(db, "video")
    return ok(items)
