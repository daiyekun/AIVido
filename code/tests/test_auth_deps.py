from __future__ import annotations

import pytest

from app.api.deps import require_admin
from app.core.exceptions import ForbiddenError


class FakeUser:
    def __init__(self, is_admin: bool):
        self.is_admin = is_admin


@pytest.mark.asyncio
async def test_require_admin_allows_admin():
    user = await require_admin(FakeUser(True))
    assert user.is_admin is True


@pytest.mark.asyncio
async def test_require_admin_rejects_non_admin():
    with pytest.raises(ForbiddenError):
        await require_admin(FakeUser(False))
