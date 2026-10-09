from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ModelDisabledError,
    ModelNotFoundError,
    ParamError,
    QueueSubmitFailedError,
    TaskNotFoundError,
)
from app.domain.gen_type_resolver import GEN_IMAGE, GEN_VIDEO, resolve_task_type
from app.domain.model_config import ensure_tiers_supported
from app.domain.task_machine import (
    CANCELED,
    PENDING,
    QUEUED,
    assert_transition,
    ensure_cancelable,
)
from app.infrastructure.db.models.credit import AiCreditLog
from app.infrastructure.db.models.task import AiGenerateTask
from app.infrastructure.db.models.user import SysUser
from app.infrastructure.db.repositories import model as model_repo
from app.infrastructure.filter import filetype
from app.infrastructure.filter.sensitive import assert_clean
from app.infrastructure.mq.publisher import publish_task
from app.infrastructure.storage import minio_client
from app.infrastructure.storage.thumbnail import thumb_key_from_output_key
from app.services import billing_service, prompt_service

logger = logging.getLogger("ainew.task")


def _model_conf_dict(model: Any) -> dict[str, Any]:
    return {
        "model_id": model.model_id,
        "model_name": model.model_name,
        "model_type": model.model_type,
        "adapter_key": model.adapter_key,
        "is_enable": model.is_enable,
        "sort": model.sort,
        "support_resolution": model.support_resolution or [],
        "support_duration": model.support_duration or [],
        "config_json": model.config_json or {},
        "price_config_json": model.price_config_json or {},
    }


def media_type_from_object_key(object_key: str) -> str:
    ext = object_key.rsplit(".", 1)[-1].lower() if "." in object_key else ""
    if ext in filetype.IMAGE_EXTENSIONS:
        return "image"
    if ext in filetype.VIDEO_EXTENSIONS:
        return "video"
    raise ParamError("素材类型非法")


async def create_generate_task(
    db: AsyncSession, user: SysUser, payload: dict[str, Any], trace_id: str
) -> dict[str, Any]:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ParamError("提示词不能为空")
    assert_clean(prompt)
    negative = str(payload.get("negative_prompt") or "").strip()
    if negative:
        assert_clean(negative)

    n = payload.get("n") or 1
    if n != 1:
        raise ParamError("MVP 仅支持单次生成 1 个")

    gen_type = payload.get("gen_type")
    if gen_type not in (GEN_IMAGE, GEN_VIDEO):
        raise ParamError("gen_type 非法")

    model = await model_repo.get_model_by_id(db, payload.get("model_id"))
    if model is None:
        raise ModelNotFoundError()
    if not model.is_enable:
        raise ModelDisabledError()

    model_conf = _model_conf_dict(model)

    resolution = payload.get("resolution")
    duration = payload.get("duration")
    if gen_type == GEN_IMAGE and not resolution:
        raise ParamError("分辨率必填")
    ensure_tiers_supported(model_conf, resolution, duration)

    asset_object_key = payload.get("asset_object_key")
    asset_media_type = None
    if asset_object_key:
        if not asset_object_key.startswith(f"{user.id}/"):
            raise ParamError("素材不属于当前用户")
        asset_media_type = media_type_from_object_key(asset_object_key)

    task_type = resolve_task_type(gen_type, asset_media_type, payload.get("video_sub_mode"))

    biz = "image" if gen_type == GEN_IMAGE else "video"

    prompt_match = await prompt_service.match_system_prompt(db, task_type, model.model_id)
    expect_credit = billing_service.estimate_credit(
        model_conf["price_config_json"], resolution, duration
    )

    input_params = {
        "gen_type": gen_type,
        "prompt": prompt,
        "negative_prompt": negative,
        "resolution": resolution,
        "aspect_ratio": payload.get("aspect_ratio"),
        "duration": duration,
        "n": n,
        "denoising_strength": payload.get("denoising_strength"),
        "video_sub_mode": payload.get("video_sub_mode"),
        "extra": payload.get("extra") or {},
        "task_type": task_type,
    }

    snapshot_config = {
        "model": model_conf,
        "system_prompt": (
            {
                "system_prompt_id": prompt_match.prompt_id,
                "system_content": prompt_match.system_content,
            }
            if prompt_match
            else None
        ),
        "task_type": task_type,
    }

    task_id = uuid4()
    task = AiGenerateTask(
        task_id=task_id,
        user_id=user.id,
        model_id=model.model_id,
        task_type=task_type,
        status=PENDING,
        input_params=input_params,
        input_asset_urls=[asset_object_key] if asset_object_key else [],
        output_asset_urls=[],
        expect_credit=expect_credit,
        snapshot_config=snapshot_config,
        system_prompt_id=prompt_match.prompt_id if prompt_match else None,
        retry_count=0,
        error_code="",
        error_msg="",
        trace_id=trace_id,
    )
    db.add(task)
    db.add(
        AiCreditLog(
            user_id=user.id,
            task_id=task_id,
            change_type=1,
            change_value=expect_credit,
            remark=f"{task_type} 预估扣减",
        )
    )
    await db.flush()

    try:
        await asyncio.to_thread(
            publish_task,
            biz=biz,
            task_kwargs={"task_id": str(task_id), "trace_id": trace_id},
        )
    except QueueSubmitFailedError:
        task.status = "failed"
        task.error_code = "40003"
        task.error_msg = "队列提交失败"
        await db.commit()
        raise

    task.status = QUEUED
    await db.commit()

    logger.info(
        "task_created",
        extra={
            "task_id": str(task_id),
            "user_id": user.id,
            "model_id": model.model_id,
            "task_type": task_type,
            "expect_credit": expect_credit,
        },
    )
    return {"task_id": str(task_id), "status": task.status, "expect_credit": float(expect_credit)}


# ---- 任务查询与取消 ----

TASK_LIST_FIELDS = (
    AiGenerateTask.task_id,
    AiGenerateTask.model_id,
    AiGenerateTask.task_type,
    AiGenerateTask.status,
    AiGenerateTask.expect_credit,
    AiGenerateTask.output_asset_urls,
    AiGenerateTask.error_code,
    AiGenerateTask.error_msg,
    AiGenerateTask.trace_id,
    AiGenerateTask.retry_count,
    AiGenerateTask.create_time,
)


def _task_brief(task: AiGenerateTask) -> dict[str, Any]:
    return {
        "task_id": str(task.task_id),
        "model_id": task.model_id,
        "task_type": task.task_type,
        "status": task.status,
        "expect_credit": float(task.expect_credit),
        "output_asset_urls": task.output_asset_urls or [],
        "error_code": task.error_code,
        "error_msg": task.error_msg,
        "trace_id": task.trace_id,
        "retry_count": task.retry_count,
        "create_time": task.create_time.isoformat() if task.create_time else None,
    }


def _presign_outputs(object_keys: list[str]) -> list[str]:
    return [minio_client.presigned_get(settings.minio_bucket_output, key) for key in object_keys]


def _presign_thumbs(object_keys: list[str]) -> list[str]:
    return [
        minio_client.presigned_get(
            settings.minio_bucket_thumb, thumb_key_from_output_key(key), expires_minutes=10
        )
        for key in object_keys
    ]


def serialize_task_detail(task: AiGenerateTask) -> dict[str, Any]:
    return {
        "task_id": str(task.task_id),
        "model_id": task.model_id,
        "task_type": task.task_type,
        "status": task.status,
        "expect_credit": float(task.expect_credit),
        "input_params": task.input_params or {},
        "output_asset_urls": _presign_outputs(task.output_asset_urls or []),
        "output_thumb_urls": _presign_thumbs(task.output_asset_urls or []),
        "error_code": task.error_code,
        "error_msg": task.error_msg,
        "trace_id": task.trace_id,
        "retry_count": task.retry_count,
        "queued_at": task.queued_at.isoformat() if task.queued_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "create_time": task.create_time.isoformat() if task.create_time else None,
    }


async def list_tasks(
    db: AsyncSession, user_id: int, page: int, size: int
) -> tuple[list[dict[str, Any]], int]:
    total = int(
        (
            await db.execute(
                select(func.count()).select_from(AiGenerateTask).where(
                    AiGenerateTask.user_id == user_id
                )
            )
        ).scalar_one()
    )
    result = await db.execute(
        select(*TASK_LIST_FIELDS)
        .where(AiGenerateTask.user_id == user_id)
        .order_by(AiGenerateTask.create_time.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    tasks = result.all()
    items: list[dict[str, Any]] = []
    for row in tasks:
        items.append(
            {
                "task_id": str(row[0]),
                "model_id": row[1],
                "task_type": row[2],
                "status": row[3],
                "expect_credit": float(row[4]),
                "output_asset_urls": _presign_outputs(row[5] or []),
                "output_thumb_urls": _presign_thumbs(row[5] or []),
                "error_code": row[6],
                "error_msg": row[7],
                "trace_id": row[8],
                "retry_count": row[9],
                "create_time": row[10].isoformat() if row[10] else None,
            }
        )
    return items, total


async def get_task(db: AsyncSession, user_id: int, task_id: UUID) -> AiGenerateTask:
    result = await db.execute(
        select(AiGenerateTask).where(
            AiGenerateTask.task_id == task_id, AiGenerateTask.user_id == user_id
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise TaskNotFoundError()
    return task


async def cancel_task(db: AsyncSession, user_id: int, task_id: UUID) -> AiGenerateTask:
    task = await get_task(db, user_id, task_id)
    ensure_cancelable(task.status)
    assert_transition(task.status, CANCELED)
    task.status = CANCELED
    await db.commit()
    await db.refresh(task)
    return task
