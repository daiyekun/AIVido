from __future__ import annotations

import logging
from typing import Any

from app.infrastructure.gateway.base import AdapterResult
from app.infrastructure.gateway.errors import AdapterNotSupportedError
from app.infrastructure.gateway.registry import resolve_adapter

logger = logging.getLogger("ainew.gateway")


async def dispatch_model_call(
    model_conf: dict[str, Any], task_type: str, params: dict[str, Any], trace_id: str
) -> AdapterResult:
    """业务层唯一入口：业务只传模型配置快照 + task_type，由注册表分发到适配器能力方法。"""
    adapter_key = str(model_conf.get("adapter_key") or "")
    adapter = resolve_adapter(adapter_key, model_conf)
    if not adapter.supports(task_type):
        raise AdapterNotSupportedError(f"模型不支持能力: {task_type}")
    method = getattr(adapter, task_type)
    return await method(params, trace_id)
