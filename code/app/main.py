from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.response import ok
from app.core.tracing import init_tracing
from app.infrastructure.cache.redis_client import close_redis
from app.infrastructure.db.session import dispose_engine
from app.infrastructure.storage import minio_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        minio_client.ensure_buckets()
    except Exception:
        import logging

        logging.getLogger("ainew").warning("minio_bucket_init_failed", exc_info=True)
    yield
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    setup_logging(service_name=settings.service_name)
    app = FastAPI(
        title="EcomCraft API",
        description="AI 内容生成平台 MVP 后端服务",
        version=settings.app_version,
        lifespan=lifespan,
    )
    init_tracing(app)
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict:
        return ok({"status": "up", "version": settings.app_version})

    return app


app = create_app()
