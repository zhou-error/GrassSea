"""任务记录模型

表:
  - task_records: 任务执行记录表
"""

from __future__ import annotations

import uuid

from sqlalchemy import String, Text, Float, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.database import Base
from shared.models.postgres.base import TimestampMixin, UUIDMixin

import enum


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_USER = "waiting_user"


class TaskType(str, enum.Enum):
    SIMPLE_CHAT = "simple_chat"
    KNOWLEDGE_QA = "knowledge_qa"
    TOOL_CALL = "tool_call"
    PROFESSIONAL_TASK = "professional_task"
    SUB_AGENT_ORCHESTRATION = "sub_agent_orchestration"


class TaskRecord(Base, UUIDMixin, TimestampMixin):
    """任务执行记录表"""
    __tablename__ = "task_records"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True
    )
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    task_type: Mapped[TaskType] = mapped_column(SAEnum(TaskType), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=True)
    input_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    dag_definition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # DAG 结构
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    def __repr__(self) -> str:
        return f"<TaskRecord(id={self.id}, type='{self.task_type}', status='{self.status}')>"
