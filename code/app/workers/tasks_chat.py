from __future__ import annotations

import logging
from typing import Any

from app.workers.celery_app import celery_app

logger = logging.getLogger("ainew.worker")


@celery_app.task(name="workers.tasks_chat.run_chat_task", bind=True)
def run_chat_task(
    self: Any,
    task_id: str = "",
    trace_id: str = "",
    retry_count: int = 0,
    **extra: Any,
) -> dict[str, Any]:
    """对话任务入口：阶段一仅完成接收、trace 透传与日志验证，阶段二接入真实执行器。"""
    headers = self.request.headers or {}
    resolved_trace = trace_id or str(headers.get("trace_id", ""))
    resolved_task_id = task_id or str(self.request.id or "")
    logger.info(
        "task_received",
        extra={
            "task_id": resolved_task_id,
            "queue": "q.gen.chat",
            "retry_count": retry_count,
            "trace_id": resolved_trace,
        },
    )
    return {"ok": True, "queue": "q.gen.chat", "task_id": resolved_task_id}
