from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.user import SysUser


async def get_user_by_id(session: AsyncSession, user_id: int) -> SysUser | None:
    stmt = select(SysUser).where(SysUser.id == user_id, SysUser.is_deleted.is_(False))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_phone(session: AsyncSession, phone: str) -> SysUser | None:
    stmt = select(SysUser).where(SysUser.phone == phone, SysUser.is_deleted.is_(False))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_users_by_ids(session: AsyncSession, user_ids: list[int]) -> list[SysUser]:
    if not user_ids:
        return []
    stmt = select(SysUser).where(SysUser.id.in_(user_ids), SysUser.is_deleted.is_(False))
    result = await session.execute(stmt)
    return list(result.scalars().all())
