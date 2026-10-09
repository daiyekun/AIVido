from __future__ import annotations

import pytest

from app.core.exceptions import FileTypeNotSupportedError
from app.infrastructure.filter import filetype

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 8
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 8
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 8


def test_sniff_image_jpeg():
    assert filetype.sniff_media_type(JPEG) == "image"


def test_sniff_image_png():
    assert filetype.sniff_media_type(PNG) == "image"


def test_sniff_image_webp():
    assert filetype.sniff_media_type(WEBP) == "image"


def test_sniff_video_mp4():
    assert filetype.sniff_media_type(MP4) == "video"


def test_sniff_unknown_rejected():
    with pytest.raises(FileTypeNotSupportedError):
        filetype.sniff_media_type(b"GIF89a")


def test_extension_whitelist():
    assert filetype.extension_whitelisted("a.jpg", "image")
    assert filetype.extension_whitelisted("a.PNG", "image")
    assert filetype.extension_whitelisted("a.mp4", "video")
    assert filetype.extension_whitelisted("a.mov", "video")
    assert not filetype.extension_whitelisted("a.gif", "image")
    assert not filetype.extension_whitelisted("a.jpg", "video")
    assert not filetype.extension_whitelisted("", "image")


def test_resolve_extension_image():
    assert filetype.resolve_extension(PNG, "image") == "png"
    assert filetype.resolve_extension(JPEG, "image") == "jpg"
