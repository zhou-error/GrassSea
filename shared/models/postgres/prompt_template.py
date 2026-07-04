"""Prompt 模板模型

表:
  - prompt_templates: Prompt 模板管理表
"""

from __future__ import annotations

from sqlalchemy import String, Text, Float, Integer, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.database import Base
from shared.models.postgres.base import TimestampMixin, UUIDMixin


class PromptTemplate(Base, UUIDMixin, TimestampMixin):
    """Prompt 模板表"""
    __tablename__ = "prompt_templates"

    template_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    model_family: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # deepseek / claude / gpt / qwen
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)  # 支持 {{variable}}
    few_shot_examples: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    output_format: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # JSON Schema
    token_limit: Mapped[int] = mapped_column(Integer, default=4096)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[str] = mapped_column(
        String(100), default="general", nullable=False
    )  # chat / rag / task_planning / ...

    def __repr__(self) -> str:
        return f"<PromptTemplate(template_id='{self.template_id}', version='{self.version}')>"
