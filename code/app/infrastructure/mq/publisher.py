from __future__ import annotations

import logging
from typing import Any

from amqp.exceptions import ChannelError, MessageNacked
from kombu.exceptions import OperationalError

from app.core.exceptions import ParamError, QueueSubmitFailedError
from app.core.tracing import current_trace_id, start_span
from app.infrastructure.mq.topology import (
    BIZ_TYPES,
    DLQ_NAME,
    DLQ_ROUTING_KEY,
    EXCHANGE_DLX,
    EXCHANGE_RETRY,
    EXCHANGE_TASK,
    TASK_QUEUES,
    TASK_ENTRY_NAMES,
    TASK_ROUTING_KEYS,
    is_routable,
    retry_queue_name,
    retry_routing_key,
    retry_tier,
)

logger = logging.getLogger("ainew.mq")

_PUBLISH_ERRORS: tuple[type[BaseException], ...] = (
    ChannelError,
    MessageNacked,
    OperationalError,
    OSError,
    TimeoutError,
    TypeError,
    ValueError,
)


def _require_biz(biz: str) -> None:
    if biz not in BIZ_TYPES:
        raise ParamError(f"未知业务类型: {biz}")


def _celery_app() -> Any:
    from app.workers.celery_app import celery_app

    return celery_app


def _send(
    *,
    task_name: str,
    biz: str,
    exchange: str,
    routing_key: str,
    destination_queue: str,
    task_kwargs: dict[str, Any] | None,
    retry_count: int,
    publish_retry: bool,
) -> str:
    from celery.exceptions import QueueNotFound

    queue = TASK_QUEUES[biz]
    if not is_routable(exchange, routing_key):
        logger.error(
            "mq_publish_unroutable",
            extra={
                "queue": destination_queue,
                "routing_key": routing_key,
                "retry_count": retry_count,
                "error_msg": "routing key has no binding on exchange",
            },
        )
        raise QueueSubmitFailedError("消息路由不可达")

    headers: dict[str, Any] = {}
    trace_id = current_trace_id()
    if trace_id:
        headers["trace_id"] = trace_id

    options: dict[str, Any] = {
        "exchange": exchange,
        "routing_key": routing_key,
        "queue": queue,
        "mandatory": True,
        "headers": headers or None,
        "retry": publish_retry,
    }

    try:
        result = _celery_app().send_task(task_name, kwargs=task_kwargs or {}, **options)
    except QueueNotFound as exc:
        logger.error(
            "mq_publish_failed",
            extra={
                "queue": destination_queue,
                "routing_key": routing_key,
                "retry_count": retry_count,
                "error_msg": str(exc) or type(exc).__name__,
            },
        )
        raise QueueSubmitFailedError("队列提交失败") from exc
    except _PUBLISH_ERRORS as exc:
        logger.error(
            "mq_publish_failed",
            extra={
                "queue": destination_queue,
                "routing_key": routing_key,
                "retry_count": retry_count,
                "error_msg": str(exc) or type(exc).__name__,
            },
        )
        raise QueueSubmitFailedError("队列提交失败") from exc

    logger.info(
        "mq_publish_ok",
        extra={
            "queue": destination_queue,
            "routing_key": routing_key,
            "retry_count": retry_count,
            "task_id": result.id,
        },
    )
    return result.id


def publish_task(
    task_name: str | None = None,
    *,
    biz: str,
    task_kwargs: dict[str, Any] | None = None,
    retry_count: int = 0,
) -> str:
    """发布业务任务到 gen.task.exchange，mandatory + confirm 模式，不可路由立即报错。"""
    _require_biz(biz)
    routing_key = TASK_ROUTING_KEYS[biz]
    destination_queue = TASK_QUEUES[biz]
    name = task_name or TASK_ENTRY_NAMES[biz]
    with start_span(
        "publish_task",
        {"queue": destination_queue, "routing_key": routing_key, "retry_count": retry_count},
    ):
        return _send(
            task_name=name,
            biz=biz,
            exchange=EXCHANGE_TASK,
            routing_key=routing_key,
            destination_queue=destination_queue,
            task_kwargs=task_kwargs,
            retry_count=retry_count,
            publish_retry=True,
        )


def publish_retry(
    task_name: str | None = None,
    *,
    biz: str,
    task_kwargs: dict[str, Any] | None = None,
    retry_count: int = 1,
) -> str:
    """按重试档位投递到 gen.retry.exchange，TTL 到期后由死信配置精确回投业务队列。"""
    _require_biz(biz)
    tier = retry_tier(retry_count)
    routing_key = retry_routing_key(biz, tier)
    destination_queue = retry_queue_name(biz, tier)
    name = task_name or TASK_ENTRY_NAMES[biz]
    with start_span(
        "publish_task",
        {"queue": destination_queue, "routing_key": routing_key, "retry_count": retry_count},
    ):
        return _send(
            task_name=name,
            biz=biz,
            exchange=EXCHANGE_RETRY,
            routing_key=routing_key,
            destination_queue=destination_queue,
            task_kwargs=task_kwargs,
            retry_count=retry_count,
            publish_retry=False,
        )


def publish_to_dlq(
    task_name: str | None = None,
    *,
    biz: str,
    task_kwargs: dict[str, Any] | None = None,
    retry_count: int = 0,
) -> str:
    """重试耗尽或终态错误转 q.gen.dlq，等待人工介入与告警。"""
    _require_biz(biz)
    destination_queue = DLQ_NAME
    name = task_name or TASK_ENTRY_NAMES[biz]
    with start_span(
        "publish_task",
        {"queue": destination_queue, "routing_key": DLQ_ROUTING_KEY, "retry_count": retry_count},
    ):
        return _send(
            task_name=name,
            biz=biz,
            exchange=EXCHANGE_DLX,
            routing_key=DLQ_ROUTING_KEY,
            destination_queue=destination_queue,
            task_kwargs=task_kwargs,
            retry_count=retry_count,
            publish_retry=False,
        )
