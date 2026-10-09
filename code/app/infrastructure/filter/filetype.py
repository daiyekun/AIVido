from __future__ import annotations

from app.core.exceptions import FileTypeNotSupportedError

IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp")
VIDEO_EXTENSIONS = ("mp4", "mov")


def _detect_image(header: bytes) -> str | None:
    if header[:3] == b"\xff\xd8\xff":
        return "jpg"
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


def _detect_video(header: bytes) -> str | None:
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "mp4"
    return None


def sniff_media_type(header: bytes) -> str:
    if _detect_image(header):
        return "image"
    if _detect_video(header):
        return "video"
    raise FileTypeNotSupportedError()


def resolve_extension(header: bytes, media_type: str) -> str:
    if media_type == "image":
        ext = _detect_image(header)
        if ext is not None:
            return ext
    if media_type == "video":
        ext = _detect_video(header)
        if ext is not None:
            return ext
    raise FileTypeNotSupportedError()


def extension_whitelisted(filename: str | None, media_type: str) -> bool:
    if not filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if media_type == "image":
        return ext in IMAGE_EXTENSIONS
    if media_type == "video":
        return ext in VIDEO_EXTENSIONS
    return False
