"""用户与权限模型 (RBAC)

表:
  - users: 用户表
  - roles: 角色表
  - user_roles: 用户-角色关联表
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, Table, Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.database import Base
from shared.models.postgres.base import TimestampMixin, UUIDMixin

# 用户-角色关联表 (多对多)
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base, UUIDMixin, TimestampMixin):
    """用户表"""
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 关联
    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary=user_roles, back_populates="users", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"


class Role(Base, UUIDMixin, TimestampMixin):
    """角色表 (RBAC)"""
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    permissions: Mapped[str] = mapped_column(String(2000), nullable=False)  # JSON array string
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)  # 系统内置角色不可删除

    # 关联
    users: Mapped[list["User"]] = relationship(
        "User", secondary=user_roles, back_populates="roles", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name='{self.name}')>"
