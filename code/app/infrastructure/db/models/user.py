from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Identity,
    Numeric,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class SysUser(Base):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    jwt_salt: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    credit_balance: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default=text("0.00")
    )
    user_type: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default=text("1"))
    enterprise_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", server_default=""
    )
    business_license_no: Mapped[str] = mapped_column(
        String(128), nullable=False, default="", server_default=""
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uk_sys_user_phone",
            "phone",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )
