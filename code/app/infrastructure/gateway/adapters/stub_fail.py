from __future__ import annotations

from typing import Any

from app.infrastructure.gateway.base import AdapterResult, BaseModelAdapter
from app.infrastructure.gateway.errors import AdapterNotSupportedError, ModelCallTimeoutError
from app.infrastructure.gateway.registry import register_adapter


@register_adapter("stub_fail")
class StubFailAdapter(BaseModelAdapter):
    """可重试失败桩：模拟第三方超时，用于验证分级重试链路。"""

    async def txt2img(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        raise ModelCallTimeoutError("模拟第三方超时")

    async def img2img(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        raise ModelCallTimeoutError("模拟第三方超时")


@register_adapter("stub_fail_fatal")
class StubFailFatalAdapter(BaseModelAdapter):
    """终态失败桩：模拟适配器未实现能力，应直接 failed 不重试。"""

    async def txt2img(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        raise AdapterNotSupportedError("txt2img")
