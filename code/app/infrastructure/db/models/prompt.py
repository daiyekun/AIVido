from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Identity,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AiSystemPrompt(Base):
    __tablename__ = "ai_system_prompt"

    prompt_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    prompt_name: Mapped[str] = mapped_column(String(128), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    bind_model_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ai_model.model_id", name="ai_system_prompt_bind_model_id_fkey"), nullable=True
    )
    system_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_enable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    remark: Mapped[str] = mapped_column(String(512), nullable=False, default="", server_default="")
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_prompt_match", "task_type", "is_enable", "bind_model_id", text("sort DESC")),
    )
