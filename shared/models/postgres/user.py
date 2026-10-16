"""用户模型

表:
  - users: 用户表

说明:
  projects / task_records / todo_items / offset_tables / project_members
  均以外键引用 users.id，此前该表缺失导致建表失败。
  当前项目定位为个人使用，登录与鉴权尚未实现，此表只保证数据模型完整。
"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.database import Base
from shared.models.postgres.base import TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin):
    """用户表"""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="admin", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"
