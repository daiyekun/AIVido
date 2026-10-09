from __future__ import annotations

import asyncio
import io
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.domain.task_machine import FAILED, RUNNING, SUCCESS, TERMINAL_STATES
from app.infrastructure.db.models.task import AiGenerateTask
from app.infrastructure.gateway.client import gateway_client
from app.infrastructure.gateway.errors import GatewayError, error_code_of, is_retryable
from app.infrastructure.mq.publisher import publish_retry, publish_to_dlq
from app.infrastructure.storage import minio_client
from app.infrastructure.storage.thumbnail import make_thumbnail, thumb_key_from_output_key
from app.services.gateway_service import dispatch_model_call
from app.workers.celery_app import celery_app

logger = logging.getLogger("ainew.worker")


def _build_output_key(user_id: int, task_id: str, ext: str) -> str:
    now = datetime.now(timezone.utc)
    return f"{user_id}/{now.year:04d}/{now.month:02d}/{now.day:02d}/{task_id}.{ext}"


async def _upload_output_bytes(
    bucket: str, object_key: str, data: bytes, content_type: str = "image/png"
) -> None:
    client = minio_client.get_minio()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: client.put_object(
            bucket, object_key, io.BytesIO(data), len(data), content_type=content_type
        ),
    )


async def _upload_thumbnail(task_id: str, output_key: str, image_bytes: bytes) -> None:
    """生成缩略图并写入 ai-thumb；失败仅告警，不阻断任务成功。"""
    try:
        thumb_bytes = await asyncio.to_thread(make_thumbnail, image_bytes)
        thumb_key = thumb_key_from_output_key(output_key)
        await _upload_output_bytes(
            settings.minio_bucket_thumb, thumb_key, thumb_bytes, content_type="image/jpeg"
        )
        logger.info("thumbnail_created", extra={"task_id": task_id, "thumb_key": thumb_key})
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "thumbnail_failed", extra={"task_id": task_id, "error_msg": str(exc)}
        )


async def _execute(task_id: str, trace_id: str, retry_count: int) -> None:
    engine = create_async_engine(settings.database_url)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                uuid_task_id = UUID(task_id)
            except (ValueError, TypeError):
                logger.warning("task_id_invalid", extra={"task_id": task_id})
                return

            result = await session.execute(
                select(AiGenerateTask).where(AiGenerateTask.task_id == uuid_task_id)
            )
            task = result.scalar_one_or_none()
            if task is None:
                logger.warning("task_not_found", extra={"task_id": task_id})
                return
            if task.status in TERMINAL_STATES:
                logger.info("task_already_terminal", extra={"task_id": task_id, "status": task.status})
                return

            task.status = RUNNING
            if task.started_at is None:
                task.started_at = datetime.now(timezone.utc)
            task.retry_count = retry_count
            await session.commit()

            snapshot = task.snapshot_config or {}
            model_conf = snapshot.get("model") or {}
            input_params = task.input_params or {}
            sp = snapshot.get("system_prompt")

            params = dict(input_params)
            if sp:
                params["system_prompt"] = sp.get("system_content", "")

            max_retry = len(settings.retry_delays)

            try:
                adapter_result = await dispatch_model_call(model_conf, task.task_type, params, trace_id)
                keys: list[str] = []
                image_bytes = (adapter_result.raw or {}).get("image_bytes")
                if image_bytes:
                    key = _build_output_key(task.user_id, str(task.task_id), "png")
                    await _upload_output_bytes(settings.minio_bucket_output, key, image_bytes)
                    keys.append(key)
                    await _upload_thumbnail(str(task.task_id), key, image_bytes)
                task.output_asset_urls = keys
                task.status = SUCCESS
                task.finished_at = datetime.now(timezone.utc)
                await session.commit()
                logger.info(
                    "task_succeeded",
                    extra={"task_id": task_id, "task_type": task.task_type, "outputs": len(keys)},
                )
            except GatewayError as exc:
                err_code = error_code_of(exc)
                if is_retryable(exc) and retry_count < max_retry:
                    new_retry = retry_count + 1
                    task.retry_count = new_retry
                    task.error_code = err_code
                    task.error_msg = str(exc)
                    await session.commit()
                    await asyncio.to_thread(
                        publish_retry,
                        biz="image",
                        retry_count=new_retry,
                        task_kwargs={
                            "task_id": task_id,
                            "trace_id": trace_id,
                            "retry_count": new_retry,
                        },
                    )
                    logger.info(
                        "task_retry_scheduled",
                        extra={"task_id": task_id, "retry_count": new_retry},
                    )
                else:
                    task.status = FAILED
                    task.error_code = err_code
                    task.error_msg = str(exc)
                    task.finished_at = datetime.now(timezone.utc)
                    await session.commit()
                    if is_retryable(exc):
                        await asyncio.to_thread(
                            publish_to_dlq,
                            biz="image",
                            task_kwargs={
                                "task_id": task_id,
                                "trace_id": trace_id,
                                "retry_count": retry_count,
                            },
                        )
                    logger.error(
                        "task_failed",
                        extra={"task_id": task_id, "error_code": err_code, "error_msg": str(exc)},
                    )
            except Exception as exc:  # noqa: BLE001
                task.status = FAILED
                task.error_code = "50001"
                task.error_msg = str(exc)
                task.finished_at = datetime.now(timezone.utc)
                await session.commit()
                logger.exception("task_unexpected_error", extra={"task_id": task_id})
    finally:
        await engine.dispose()
        await gateway_client.close()


@celery_app.task(name="workers.tasks_image.run_image_task", bind=True)
def run_image_task(self: Any, task_id: str = "", trace_id: str = "", retry_count: int = 0, **extra: Any) -> dict[str, Any]:
    headers = self.request.headers or {}
    resolved_trace = trace_id or str(headers.get("trace_id", ""))
    resolved_task_id = task_id or str(self.request.id or "")
    logger.info(
        "task_received",
        extra={
            "task_id": resolved_task_id,
            "queue": "q.gen.image",
            "retry_count": retry_count,
            "trace_id": resolved_trace,
        },
    )
    asyncio.run(_execute(resolved_task_id, resolved_trace, int(retry_count)))
    return {"ok": True, "queue": "q.gen.image", "task_id": resolved_task_id}
