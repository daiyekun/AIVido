from __future__ import annotations

import logging
from io import BytesIO

from PIL import Image

logger = logging.getLogger("ainew.thumbnail")

THUMB_MAX_EDGE = 256
THUMB_FORMAT = "JPEG"
THUMB_EXT = "jpg"


def make_thumbnail(data: bytes, max_edge: int = THUMB_MAX_EDGE) -> bytes:
    """将原始图像字节等比缩放到最长边不超过 max_edge，输出 JPEG 字节。"""
    img = Image.open(BytesIO(data))
    img = img.convert("RGB")
    img.thumbnail((max_edge, max_edge))
    buf = BytesIO()
    img.save(buf, format=THUMB_FORMAT)
    return buf.getvalue()


def thumb_key_from_output_key(output_key: str) -> str:
    """由原图 object key 推导缩略图 object key（同 uuid，扩展名固定 .jpg）。"""
    stem = output_key.rsplit(".", 1)[0] if "." in output_key else output_key
    return f"{stem}.{THUMB_EXT}"
