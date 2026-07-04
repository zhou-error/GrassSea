"""项目模型

表:
  - projects: 项目表
  - project_members: 项目成员关联表
"""

from __future__ import annotations

from sqlalchemy import String, Text, Table, Column, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.database import Base
from shared.models.postgres.base import TimestampMixin, UUIDMixin

import enum


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    COMPLETED = "completed"


# 项目-成员关联表
project_members = Table(
    "project_members",
    Base.metadata,
    Column("project_id", UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(50), nullable=False, default="engineer"),  # project_lead / engineer / guest
)


class Project(Base, UUIDMixin, TimestampMixin):
    """项目表"""
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus), default=ProjectStatus.ACTIVE, nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    ship_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ship_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, code='{self.code}', name='{self.name}')>"
