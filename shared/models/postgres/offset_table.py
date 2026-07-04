"""型值表模型

表:
  - offset_tables: 型值表元数据
  - offset_data: 型值数据点
"""

from __future__ import annotations

import uuid

from sqlalchemy import String, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.database import Base
from shared.models.postgres.base import TimestampMixin, UUIDMixin


class OffsetTable(Base, UUIDMixin, TimestampMixin):
    """型值表元数据"""
    __tablename__ = "offset_tables"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    ship_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 型值表元信息
    num_stations: Mapped[int] = mapped_column(Integer, nullable=True)  # 站数
    num_waterlines: Mapped[int] = mapped_column(Integer, nullable=True)  # 水线数
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # MinIO 路径
    # JSON 格式的完整型值数据 (备选方案，小数据量时直接用 JSONB)
    offset_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<OffsetTable(id={self.id}, name='{self.name}')>"
