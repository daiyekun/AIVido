from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Identity,
    Numeric,
    SmallInteger,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AiCreditLog(Base):
    __tablename__ = "ai_credit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_user.id", name="ai_credit_log_user_id_fkey"), nullable=False
    )
    task_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    msg_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    change_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    change_value: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default="0.00"
    )
    remark: Mapped[str] = mapped_column(String(512), nullable=False, default="", server_default="")
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("idx_credit_user_time", "user_id", text("create_time DESC")),)
