"""数据库种子脚本（幂等，可重复执行）

写入:
  - system_configs : 7 项系统默认配置
  - users          : 一个默认本地用户
                     （projects / task_records / todo_items / offset_tables
                       的 user_id 为 NOT NULL，没有用户行就无法建业务数据）

用法:
    uv run python scripts/seed_data.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from shared.models.database import pg_engine, pg_session_factory  # noqa: E402
from shared.models.postgres.system_config import SystemConfig  # noqa: E402
from shared.models.postgres.user import User  # noqa: E402
from shared.utils.logging import setup_logging  # noqa: E402

SYSTEM_CONFIGS = [
    {"key": "default_llm_model", "value": "deepseek-chat", "description": "默认 LLM 模型"},
    {"key": "default_embedding_model", "value": "text-embedding-3-large", "description": "默认 Embedding 模型"},
    {"key": "max_context_turns", "value": "20", "description": "最大对话上下文轮数"},
    {"key": "session_timeout_minutes", "value": "30", "description": "会话超时时间（分钟）"},
    {"key": "rag_chunk_size", "value": "512", "description": "RAG 文档分块大小（tokens）"},
    {"key": "rag_chunk_overlap", "value": "64", "description": "RAG 分块重叠大小（tokens）"},
    {"key": "rag_top_k", "value": "5", "description": "RAG 检索返回 Top-K 数量"},
]

DEFAULT_USER = {
    "username": "admin",
    "display_name": "本地用户",
    "role": "admin",
    "is_active": True,
}


async def seed_system_configs(session: AsyncSession) -> tuple[int, int]:
    created = updated = 0
    for cfg in SYSTEM_CONFIGS:
        row = (
            await session.execute(select(SystemConfig).where(SystemConfig.key == cfg["key"]))
        ).scalar_one_or_none()
        if row is None:
            session.add(
                SystemConfig(key=cfg["key"], value=cfg["value"], description=cfg["description"])
            )
            created += 1
            continue
        changed = False
        if row.value != cfg["value"]:
            row.value = cfg["value"]
            changed = True
        if cfg["description"] and row.description != cfg["description"]:
            row.description = cfg["description"]
            changed = True
        if changed:
            updated += 1
    return created, updated


async def seed_default_user(session: AsyncSession) -> tuple[User, bool]:
    user = (
        await session.execute(select(User).where(User.username == DEFAULT_USER["username"]))
    ).scalar_one_or_none()
    if user is not None:
        return user, False
    user = User(**DEFAULT_USER)
    session.add(user)
    await session.flush()
    return user, True


async def main() -> None:
    setup_logging(level="WARNING")
    async with pg_session_factory() as session:
        created, updated = await seed_system_configs(session)
        user, user_created = await seed_default_user(session)
        await session.commit()
        print(f"RESULT system_configs: 新增 {created} 项, 更新 {updated} 项")
        print(f"RESULT users: {'新增' if user_created else '已存在'} {user.username} id={user.id}")
    await pg_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
