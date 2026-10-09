from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.exceptions import FileTooLargeError, FileTypeNotSupportedError, ParamError
from app.core.response import ok
from app.infrastructure.filter import filetype
from app.infrastructure.storage import minio_client

router = APIRouter(prefix="/upload", tags=["upload"])

_HEADER_BYTES = 512


@router.post("")
async def upload_asset(
    user: CurrentUser,
    gen_type: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    if gen_type not in ("image", "video"):
        raise ParamError("gen_type 非法")

    if not filetype.extension_whitelisted(file.filename, gen_type):
        raise FileTypeNotSupportedError()

    header = await file.read(_HEADER_BYTES)
    await file.seek(0)
    if filetype.sniff_media_type(header) != gen_type:
        raise FileTypeNotSupportedError()

    size = getattr(file, "size", None)
    if size is None:
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)

    if gen_type == "image":
        max_bytes = settings.upload_image_max_mb * 1024 * 1024
    else:
        max_bytes = settings.upload_video_max_mb * 1024 * 1024
    if size <= 0 or size > max_bytes:
        raise FileTooLargeError()

    ext = filetype.resolve_extension(header, gen_type)
    object_key = minio_client.build_object_key(user.id, "in", ext)
    await minio_client.upload_stream(
        settings.minio_bucket_input, object_key, file.file, size, file.content_type
    )
    url = minio_client.presigned_get(settings.minio_bucket_input, object_key)

    return ok(
        {
            "object_key": object_key,
            "media_type": gen_type,
            "size_bytes": size,
            "url": url,
        }
    )
