from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import BinaryIO
from uuid import uuid4

from minio import Minio

from app.core.config import settings

logger = logging.getLogger("ainew.storage")

_client: Minio | None = None

BUCKETS: tuple[str, ...] = ("ai-input", "ai-output", "ai-thumb", "ai-backup")


def get_minio() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def ensure_buckets() -> None:
    client = get_minio()
    for bucket in BUCKETS:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info("minio_bucket_created", extra={"bucket": bucket})


def build_object_key(user_id: int, prefix: str, ext: str) -> str:
    now = datetime.now(timezone.utc)
    return f"{user_id}/{now.year:04d}/{now.month:02d}/{now.day:02d}/{prefix}-{uuid4().hex}.{ext}"


async def upload_stream(
    bucket: str, object_key: str, fileobj: BinaryIO, length: int, content_type: str
) -> None:
    client = get_minio()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: client.put_object(bucket, object_key, fileobj, length, content_type=content_type),
    )


def presigned_get(bucket: str, object_key: str, expires_minutes: int | None = None) -> str:
    client = get_minio()
    expires = timedelta(minutes=expires_minutes or settings.signed_url_expire_minutes)
    return client.presigned_get_object(bucket, object_key, expires=expires)
