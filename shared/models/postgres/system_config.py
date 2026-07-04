"""系统配置模型

表:
  - system_configs: 系统配置项表 (Key-Value)
"""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.database import Base
from shared.models.postgres.base import TimestampMixin, UUIDMixin


class SystemConfig(Base, UUIDMixin, TimestampMixin):
    """系统配置项表"""
    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str] = mapped_column(String(100), default="general", nullable=False)

    def __repr__(self) -> str:
        return f"<SystemConfig(key='{self.key}', value='{self.value[:50]}...')>"
