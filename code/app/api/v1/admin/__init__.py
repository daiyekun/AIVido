from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.api.v1.admin import model, prompt

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

router.include_router(model.router)
router.include_router(prompt.router)
