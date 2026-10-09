from __future__ import annotations

import struct
import zlib
from typing import Any

from app.infrastructure.gateway.base import AdapterResult, BaseModelAdapter
from app.infrastructure.gateway.registry import register_adapter


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def make_stub_png(width: int = 128, height: int = 128, rgb: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(rgb) * width
    raw = row * height
    idat = zlib.compress(raw)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


@register_adapter("stub_image")
class StubImageAdapter(BaseModelAdapter):
    """图片桩适配器：模拟文生图/图生图，返回一张真实 PNG 字节，用于端到端跑通链路。"""

    async def txt2img(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        image = make_stub_png(rgb=(0, 120, 200))
        return AdapterResult(
            provider_task_id=f"stub-txt2img-{trace_id[:8]}",
            raw={"image_bytes": image, "prompt": params.get("prompt", "")},
        )

    async def img2img(self, params: dict[str, Any], trace_id: str) -> AdapterResult:
        image = make_stub_png(rgb=(200, 80, 0))
        return AdapterResult(
            provider_task_id=f"stub-img2img-{trace_id[:8]}",
            raw={"image_bytes": image, "prompt": params.get("prompt", "")},
        )
