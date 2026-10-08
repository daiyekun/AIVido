from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token, extract_bearer_token, token_denylist_key
from app.infrastructure.cache.redis_client import cache_exists
from app.infrastructure.db.models.user import SysUser
from app.infrastructure.db.repositories.user import get_user_by_id
from app.infrastructure.db.session import get_session


@dataclass(frozen=True)
class PageParams:
    page: int
    size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


def get_page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageParams:
    return PageParams(page=page, size=size)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> SysUser:
    token = extract_bearer_token(authorization)
    payload = decode_access_token(token, settings.jwt_secret)
    if await cache_exists(token_denylist_key(token)):
        raise UnauthorizedError("登录状态已失效")
    user = await get_user_by_id(db, payload.user_id)
    if user is None:
        raise UnauthorizedError()
    if payload.salt != user.jwt_salt:
        raise UnauthorizedError("登录状态已失效")
    return user


async def require_admin(user: Annotated[SysUser, Depends(get_current_user)]) -> SysUser:
    if not user.is_admin:
        raise ForbiddenError()
    return user


DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[SysUser, Depends(get_current_user)]
AdminUser = Annotated[SysUser, Depends(require_admin)]
PageParam = Annotated[PageParams, Depends(get_page_params)]
