"""TimescaleDB 时序指标模型

使用 hypertable 存储以下时序数据:
  - Token 用量统计
  - API 调用延迟
  - 工具调用频次
  - 会话统计

表在 timeseries schema 下。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.database import Base

# TimescaleDB 扩展在初始化脚本中已启用
# hypertable 通过 Alembic 迁移或原始 SQL 创建


class TokenUsageMetric(Base):
    """Token 用量统计 (hypertable)"""
    __tablename__ = "token_usage_metrics"
    __table_args__ = {"schema": "timeseries"}

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<TokenUsage(time={self.time}, model='{self.model}', total={self.total_tokens})>"


class APILatencyMetric(Base):
    """API 调用延迟统计 (hypertable)"""
    __tablename__ = "api_latency_metrics"
    __table_args__ = {"schema": "timeseries"}

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, default=200)

    def __repr__(self) -> str:
        return f"<APILatency(time={self.time}, endpoint='{self.endpoint}', latency={self.latency_ms}ms)>"


class ToolCallMetric(Base):
    """工具调用频次统计 (hypertable)"""
    __tablename__ = "tool_call_metrics"
    __table_args__ = {"schema": "timeseries"}

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    tool_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), nullable=True)
    task_id: Mapped[str] = mapped_column(String(100), nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0)
    success: Mapped[bool] = mapped_column(Integer, default=1)  # 1=成功, 0=失败

    def __repr__(self) -> str:
        return f"<ToolCall(time={self.time}, tool='{self.tool_id}', success={self.success})>"


class SessionMetric(Base):
    """会话统计 (hypertable)"""
    __tablename__ = "session_metrics"
    __table_args__ = {"schema": "timeseries"}

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    intent: Mapped[str] = mapped_column(String(50), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0)
    token_total: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<SessionMetric(time={self.time}, session='{self.session_id}')>"
