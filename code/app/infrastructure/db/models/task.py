from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AiGenerateTask(Base):
    __tablename__ = "ai_generate_task"

    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_user.id", name="ai_generate_task_user_id_fkey"), nullable=False
    )
    model_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ai_model.model_id", name="ai_generate_task_model_id_fkey"), nullable=False
    )
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default=text("'pending'")
    )
    input_params: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    input_asset_urls: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    output_asset_urls: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    expect_credit: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default=text("0.00")
    )
    snapshot_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    system_prompt_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default=text("0")
    )
    error_code: Mapped[str] = mapped_column(String(32), nullable=False, default="", server_default="")
    error_msg: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_task_user_create", "user_id", text("create_time DESC")),
        Index("idx_task_status_time", "status", "create_time"),
        Index("idx_task_trace", "trace_id"),
        Index("idx_task_model_time", "model_id", text("create_time DESC")),
        Index(
            "idx_task_running",
            "status",
            "started_at",
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )
