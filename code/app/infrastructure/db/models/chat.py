from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AiChatSession(Base):
    __tablename__ = "ai_chat_session"

    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_user.id", name="ai_chat_session_user_id_fkey"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="", server_default="")
    context_window_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=4096, server_default=text("4096")
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
            "idx_session_user",
            "user_id",
            text("update_time DESC"),
            postgresql_where=text("is_deleted = false"),
        ),
    )


class AiChatMessage(Base):
    __tablename__ = "ai_chat_message"

    msg_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_chat_session.session_id", name="ai_chat_message_session_id_fkey"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    model_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ai_model.model_id", name="ai_chat_message_model_id_fkey"), nullable=False
    )
    content_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    asset_urls: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    related_task_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    expect_credit: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default=text("0.00")
    )
    system_prompt_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_msg: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("idx_msg_session_time", "session_id", "create_time"),)
