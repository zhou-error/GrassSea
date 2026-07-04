"""待办事项模型

表:
  - todo_items: 待办事项表
"""

from __future__ import annotations

import uuid

from sqlalchemy import String, Text, Boolean, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.database import Base
from shared.models.postgres.base import TimestampMixin, UUIDMixin

import enum


class TodoPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TodoStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TodoItem(Base, UUIDMixin, TimestampMixin):
    """待办事项表"""
    __tablename__ = "todo_items"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    priority: Mapped[TodoPriority] = mapped_column(
        SAEnum(TodoPriority), default=TodoPriority.MEDIUM, nullable=False
    )
    status: Mapped[TodoStatus] = mapped_column(
        SAEnum(TodoStatus), default=TodoStatus.PENDING, nullable=False, index=True
    )
    due_date: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    source_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_records.id"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<TodoItem(id={self.id}, title='{self.title}', status='{self.status}')>"
