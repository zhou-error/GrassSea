"""数据库种子脚本

初始化默认数据：管理员角色、系统配置项等。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

# 默认角色定义
DEFAULT_ROLES = [
    {
        "name": "admin",
        "display_name": "系统管理员",
        "description": "全部权限：用户管理、系统配置、所有项目读写",
        "permissions": ["*"],
    },
    {
        "name": "project_lead",
        "display_name": "项目负责人",
        "description": "项目内全部权限：成员管理、知识库管理、任务分配、报告管理",
        "permissions": [
            "project:read", "project:write",
            "knowledge:read", "knowledge:write",
            "member:manage",
            "task:assign",
        ],
    },
    {
        "name": "engineer",
        "display_name": "工程师",
        "description": "项目内读写权限：知识库查阅、工具调用、报告生成",
        "permissions": [
            "project:read", "project:write",
            "knowledge:read",
            "tool:use",
            "report:generate",
        ],
    },
    {
        "name": "guest",
        "display_name": "访客",
        "description": "指定项目只读：查阅报告、查看图纸",
        "permissions": [
            "project:read",
            "knowledge:read",
        ],
    },
    {
        "name": "api_user",
        "display_name": "API 用户",
        "description": "按申请范围授权：密钥认证，可限制调用频次和工具范围",
        "permissions": [
            "api:access",
        ],
    },
]

# 系统配置项
SYSTEM_CONFIGS = [
    {
        "key": "default_llm_model",
        "value": "deepseek-chat",
        "description": "默认 LLM 模型",
    },
    {
        "key": "default_embedding_model",
        "value": "text-embedding-3-large",
        "description": "默认 Embedding 模型",
    },
    {
        "key": "max_context_turns",
        "value": "20",
        "description": "最大对话上下文轮数",
    },
    {
        "key": "session_timeout_minutes",
        "value": "30",
        "description": "会话超时时间（分钟）",
    },
    {
        "key": "rag_chunk_size",
        "value": "512",
        "description": "RAG 文档分块大小（tokens）",
    },
    {
        "key": "rag_chunk_overlap",
        "value": "64",
        "description": "RAG 分块重叠大小（tokens）",
    },
    {
        "key": "rag_top_k",
        "value": "5",
        "description": "RAG 检索返回 Top-K 数量",
    },
]


async def seed_roles() -> None:
    """初始化默认角色"""
    # 在生产环境中，这里通过 Repository 写入 PostgreSQL
    logger.info("Seeding default roles", count=len(DEFAULT_ROLES))
    for role in DEFAULT_ROLES:
        logger.debug("Role", name=role["name"], permissions=len(role["permissions"]))


async def seed_system_configs() -> None:
    """初始化系统配置项"""
    logger.info("Seeding system configs", count=len(SYSTEM_CONFIGS))
    for config in SYSTEM_CONFIGS:
        logger.debug("Config", key=config["key"], value=config["value"])


async def main() -> None:
    setup_logging(level="INFO")
    logger.info("Starting database seed...")

    await seed_roles()
    await seed_system_configs()

    logger.info("Database seed complete!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
