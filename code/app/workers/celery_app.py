from __future__ import annotations

from typing import Any

from celery import Celery, signals
from kombu import Exchange, Queue

from app.core.config import settings
from app.infrastructure.mq.topology import (
    BIZ_TYPES,
    EXCHANGE_TASK,
    MAIN_QUEUE_ARGS,
    TASK_QUEUES,
    TASK_ROUTING_KEYS,
)

celery_app = Celery("ainew", broker=settings.mq_url, backend=None)


def _build_task_queues() -> tuple[Queue, ...]:
    exchange = Exchange(EXCHANGE_TASK, type="direct", durable=True)
    return tuple(
        Queue(
            TASK_QUEUES[biz],
            exchange=exchange,
            routing_key=TASK_ROUTING_KEYS[biz],
            queue_arguments=MAIN_QUEUE_ARGS[TASK_QUEUES[biz]],
        )
        for biz in BIZ_TYPES
    )


celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    broker_transport_options={
        "visibility_timeout": settings.task_visibility_timeout,
        "confirm_publish": True,
        "max_retries": 3,
        "interval_start": 0,
        "interval_step": 0.5,
    },
    broker_connection_retry_on_startup=True,
    broker_heartbeat=30,
    task_default_exchange=EXCHANGE_TASK,
    task_default_exchange_type="direct",
    task_default_queue=TASK_QUEUES["image"],
    task_default_routing_key=TASK_ROUTING_KEYS["image"],
    task_queues=_build_task_queues(),
    task_create_missing_queues=False,
    task_routes={
        "workers.tasks_image.*": {
            "exchange": EXCHANGE_TASK,
            "exchange_type": "direct",
            "routing_key": TASK_ROUTING_KEYS["image"],
            "queue": TASK_QUEUES["image"],
        },
        "workers.tasks_video.*": {
            "exchange": EXCHANGE_TASK,
            "exchange_type": "direct",
            "routing_key": TASK_ROUTING_KEYS["video"],
            "queue": TASK_QUEUES["video"],
        },
        "workers.tasks_chat.*": {
            "exchange": EXCHANGE_TASK,
            "exchange_type": "direct",
            "routing_key": TASK_ROUTING_KEYS["chat"],
            "queue": TASK_QUEUES["chat"],
        },
    },
    task_time_limit=900,
    task_soft_time_limit=840,
    task_acks_on_failure_or_timeout=False,
    task_publish_retry=True,
)

celery_app.autodiscover_tasks(["app.workers"], related_name=None)


def _on_worker_process_init(**kwargs: Any) -> None:
    from app.core.logging import setup_logging
    from app.core.tracing import init_tracing

    setup_logging(service_name="ainew-worker")
    init_tracing(service_name="ainew-worker")


signals.worker_process_init.connect(_on_worker_process_init, weak=False)
