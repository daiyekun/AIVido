from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import generate, model, task, upload, user
from app.api.v1.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(user.router)
api_router.include_router(model.router)
api_router.include_router(upload.router)
api_router.include_router(generate.router)
api_router.include_router(task.router)
api_router.include_router(admin_router)
