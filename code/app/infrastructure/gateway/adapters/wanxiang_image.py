from __future__ import annotations

import logging
import os
from typing import Any

from app.infrastructure.gateway.base import AdapterResult, BaseModelAdapter
from app.infrastructure.gateway.client import gateway_client
from app.infrastructure.gateway.errors import ModelCallHttpError
from app.infrastructure.gateway.registry import register_adapter

logger = logging.getLogger("ainew.gateway")

DEFAULT_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-image-3.0"
DEFAULT_SIZE = "1024x1024"

# qwen-image 系列 OpenAI 兼容接口（同步、非流式）。
IMAGES_PATH = "/images/generations"


@register_adapter("wanxiang_image")
class WanxiangImageAdapter(BaseModelAdapter):
    """阿里云百炼千问图像模型适配器（qwen-image 系列，OpenAI 兼容 images 接口）。

    config_json 约定：
      - api_key_env:    环境变量名（如 WANXIANG_API_KEY），真实密钥不入库
      - api_base:       可选，默认 https://dashscope.aliyuncs.com/compatible-mode/v1
      - model:          可选，默认 qwen-image-3.0
      - size:           可选，默认 1024x1024（提交时被请求 resolution 覆盖）
      - enable_thinking: 可选，默认 False（开启会显著增加生成耗时）

    文生图：POST /images/generations（参数平铺）→ 解析 data[0].url → 下载字节。
    """

    @property
    def api_base(self) -> str:
        return str(self.config.get("api_base") or DEFAULT_API_BASE)

    @property
    def model(self) -> str:
        return str(self.config.get("model") or DEFAULT_MODEL)

    def _api_key(self) -> str:
        env_name = str(self.config.get("api_key_env") or "")
        if not env_name:
            raise ModelCallHttpError("缺少 api_key_env 配置", 500)
        key = os.environ.get(env_name)
        if not key:
            raise ModelCallHttpError(f"环境变量 {env_name} 未配置", 500)
        return key

    def _normalize_size(self, size: str) -> str:
        return size.replace("*", "x")

    async def _download(self, url: str, trace_id: str) -> bytes:
        resp = await gateway_client.request("GET", url, capability="image")
        return resp.content

    async def txt2img(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        api_key = self._api_key()
        prompt = str(params.get("prompt") or "")
        negative = str(params.get("negative_prompt") or "")
        size = self._normalize_size(
            str(params.get("resolution") or self.config.get("size") or DEFAULT_SIZE)
        )
        enable_thinking = bool(self.config.get("enable_thinking", False))

        body: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "n": 1,
            "prompt_extend": True,
            "enable_thinking": enable_thinking,
            "watermark": False,
        }
        if negative:
            body["negative_prompt"] = negative

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        resp = await gateway_client.request(
            "POST",
            f"{self.api_base}{IMAGES_PATH}",
            capability="image",
            headers=headers,
            json=body,
        )
        data = resp.json()

        items = data.get("data") or []
        image_url = items[0].get("url") if items else None
        if not image_url:
            err = data.get("error") or {}
            raise ModelCallHttpError(
                f"生成失败: {err.get('message') or data}", resp.status_code
            )

        image_bytes = await self._download(image_url, trace_id)
        request_id = resp.headers.get("x-request-id") or ""
        logger.info("qwen_image_generated", extra={"trace_id": trace_id})
        return AdapterResult(
            provider_task_id=request_id,
            raw={"image_bytes": image_bytes, "image_url": image_url},
        )
