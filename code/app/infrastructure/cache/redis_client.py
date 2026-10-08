from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import settings

_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def cache_get(key: str) -> str | None:
    value = await get_redis().get(key)
    return value if isinstance(value, str) else None


async def cache_set(key: str, value: str, ex: int | None = None) -> None:
    await get_redis().set(key, value, ex=ex)


async def cache_delete(*keys: str) -> None:
    if keys:
        await get_redis().delete(*keys)


async def cache_exists(key: str) -> bool:
    return bool(await get_redis().exists(key))
