from __future__ import annotations

from typing import Any

from app.infrastructure.gateway.base import AdapterResult, BaseModelAdapter
from app.infrastructure.gateway.registry import register_adapter


@register_adapter("stub")
class StubAdapter(BaseModelAdapter):
    """桩适配器：用于验证网关框架「新增适配器 + 注册即可调用」，不发起真实请求。"""

    async def txt2img(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        return AdapterResult(provider_task_id="stub-txt2img", raw={"stub": True, "trace_id": trace_id})

    async def img2img(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        return AdapterResult(provider_task_id="stub-img2img", raw={"stub": True, "trace_id": trace_id})
