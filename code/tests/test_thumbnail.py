from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.infrastructure.gateway.adapters.stub_image import make_stub_png
from app.infrastructure.storage.thumbnail import make_thumbnail, thumb_key_from_output_key


def test_make_thumbnail_scales_down_and_outputs_jpeg():
    png = make_stub_png(width=1024, height=512)
    thumb = make_thumbnail(png, max_edge=256)
    img = Image.open(BytesIO(thumb))
    assert img.format == "JPEG"
    assert max(img.size) <= 256
    assert min(img.size) == 128


def test_thumb_key_from_output_key():
    assert thumb_key_from_output_key("1024/2026/10/08/abc-123.png") == "1024/2026/10/08/abc-123.jpg"
    assert thumb_key_from_output_key("1024/2026/10/08/abc-123.webp") == "1024/2026/10/08/abc-123.jpg"
    assert thumb_key_from_output_key("noext") == "noext.jpg"
