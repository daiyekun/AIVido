from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any

from app.infrastructure.gateway.errors import AdapterNotSupportedError


@dataclass
class AdapterResult:
    content_text: str | None = None
    asset_urls: list[str] = field(default_factory=list)
    provider_task_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_text": self.content_text,
            "asset_urls": self.asset_urls,
            "provider_task_id": self.provider_task_id,
            "raw": self.raw,
        }


class BaseModelAdapter(ABC):
    """模型适配器抽象基类。新增厂商只需实现本类并注册，业务侧零改动。

    能力方法统一为 async：真实厂商调用走统一异步 HTTP 客户端（超时/重试/埋点）。
    """

    def __init__(self, model_conf: dict[str, Any]):
        self.model_conf = model_conf
        self.config = model_conf.get("config_json") or {}

    def supports(self, task_type: str) -> bool:
        method = getattr(self, task_type, None)
        if not callable(method):
            return False
        base_method = getattr(BaseModelAdapter, task_type, None)
        if base_method is None:
            return True
        return method.__func__ is not base_method

    async def txt2img(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        raise AdapterNotSupportedError("txt2img")

    async def img2img(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        raise AdapterNotSupportedError("img2img")

    async def txt2vid(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        raise AdapterNotSupportedError("txt2vid")

    async def img2vid(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        raise AdapterNotSupportedError("img2vid")

    async def vid2vid(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        raise AdapterNotSupportedError("vid2vid")

    async def vid_edit(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        raise AdapterNotSupportedError("vid_edit")

    async def chat_completion(
        self, messages: list[dict[str, Any]], params: dict[str, Any], trace_id: str
    ) -> AdapterResult:
        raise AdapterNotSupportedError("chat_completion")
