"""GrassSea AI — 统一配置管理模块

基于 pydantic-settings，支持环境变量覆盖 (.env 文件)。
所有配置项均通过环境变量注入，不硬编码敏感信息。
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env.example 中的占位值，绝不能当作真实密钥使用
_PLACEHOLDER_RE = re.compile(r"^(your[-_]|change[-_]?me|placeholder|xxx+|sk-xxx|test[-_]?key)", re.I)


def is_usable_key(value: str | None) -> bool:
    """判断配置项是否为真实可用的密钥（占位符一律视为未配置）"""
    if not value:
        return False
    return not _PLACEHOLDER_RE.match(value.strip())


class Settings(BaseSettings):
    """应用全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- 应用 ---
    APP_NAME: str = "GrassSea"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_SECRET_KEY: str = "change-me-in-production"

    # --- 服务端口 ---
    API_GATEWAY_PORT: int = 8000
    CHAT_SERVICE_PORT: int = 8001
    AGENT_SERVICE_PORT: int = 8002
    KNOWLEDGE_SERVICE_PORT: int = 8003
    MODEL_GATEWAY_PORT: int = 8004

    # --- PostgreSQL 15 + TimescaleDB ---
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "grasssea"
    POSTGRES_PASSWORD: str = "grasssea"
    POSTGRES_DB: str = "grasssea"

    @property
    def POSTGRES_URI(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def POSTGRES_SYNC_URI(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- MongoDB 7 ---
    MONGODB_HOST: str = "localhost"
    MONGODB_PORT: int = 27017
    MONGODB_USER: str = "grasssea"
    MONGODB_PASSWORD: str = "grasssea"
    MONGODB_DB: str = "grasssea"

    @property
    def MONGODB_URI(self) -> str:
        return (
            f"mongodb://{self.MONGODB_USER}:{self.MONGODB_PASSWORD}"
            f"@{self.MONGODB_HOST}:{self.MONGODB_PORT}/{self.MONGODB_DB}"
        )

    # --- Redis 7 ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    @property
    def REDIS_URI(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # --- Milvus 2.4+ ---
    # --- 向量存储后端 ---
    # local = 内置 SQLite + numpy 精确检索，零外部依赖（桌面/个人使用默认）
    # milvus = Milvus 2.4，适合服务器部署与超大规模
    VECTOR_BACKEND: str = "local"
    # 向量库数据文件路径（留空则使用 <DATA_DIR>/vectorstore/knowledge.sqlite3）
    VECTOR_STORE_PATH: str = ""
    # 本地数据目录（留空则使用 <项目根>/data）；桌面版会指向用户可写目录
    DATA_DIR: str = ""

    # --- Milvus（仅 VECTOR_BACKEND=milvus 时使用）---
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530

    @property
    def MILVUS_URI(self) -> str:
        return f"http://{self.MILVUS_HOST}:{self.MILVUS_PORT}"

    # --- MinIO ---
    MINIO_HOST: str = "localhost"
    MINIO_PORT: int = 9000
    MINIO_CONSOLE_PORT: int = 9001
    MINIO_ACCESS_KEY: str = "grasssea-admin"
    MINIO_SECRET_KEY: str = "grasssea-admin-secret"
    MINIO_BUCKET: str = "grasssea-files"

    @property
    def MINIO_URI(self) -> str:
        return f"http://{self.MINIO_HOST}:{self.MINIO_PORT}"

    # --- RabbitMQ ---
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_MGMT_PORT: int = 15672
    RABBITMQ_USER: str = "grasssea"
    RABBITMQ_PASSWORD: str = "grasssea"

    @property
    def RABBITMQ_URI(self) -> str:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

    # --- Neo4j ---
    NEO4J_HOST: str = "localhost"
    NEO4J_PORT: int = 7687
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "grasssea-neo4j"

    @property
    def NEO4J_URI(self) -> str:
        return f"bolt://{self.NEO4J_HOST}:{self.NEO4J_PORT}"

    # --- Celery ---
    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.RABBITMQ_URI

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"

    # --- LLM API Keys (通过环境变量注入) ---
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    CLAUDE_API_KEY: str = ""
    CLAUDE_BASE_URL: str = "https://api.anthropic.com"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # --- Embedding ---
    # 向量后端: auto(推荐) | local | openai | hash
    EMBEDDING_PROVIDER: str = "auto"
    # openai 后端使用的模型与维度
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIM: int = 3072
    # local 后端使用的本地模型（bge-small-zh-v1.5 约 95MB / 512 维，推荐个人使用）
    LOCAL_EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    # 本地模型缓存目录（留空则用 <项目根>/docker-data/fastembed）
    LOCAL_EMBEDDING_CACHE: str = ""
    # HuggingFace 站点（国内建议镜像；留空则使用官方 huggingface.co）
    HF_ENDPOINT: str = "https://hf-mirror.com"

    # --- Search ---
    BRAVE_SEARCH_API_KEY: str = ""
    BING_SEARCH_API_KEY: str = ""

    # --- Word / PDF 文档生成 ---
    # PDF 转换引擎: auto(默认，先 Word 后 LibreOffice) | word | libreoffice | none
    PDF_CONVERTER: str = "auto"
    # 默认排版模板名（对应 <DATA_DIR>/templates/<name>.yaml）
    DOC_DEFAULT_TEMPLATE: str = "report"
    # 未选工作文件夹时，生成文档的落盘目录（留空则 <DATA_DIR>/outputs）
    DOC_OUTPUT_DIR: str = ""

    # --- 桌面模式与工作文件夹 ---
    # 桌面模式开关：由 app.launcher --desktop 置为 true；
    # 开启后才会启用工作文件夹读写与原生对话框等本机能力
    DESKTOP_MODE: bool = False
    # 预置的工作文件夹（留空则由用户在界面上选择）
    WORKSPACE_ROOT: str = ""

    # --- 工具调用（由模型自主决定调用哪个工具）---
    # 总开关：关闭后 /chat 回到原有的规则规划路径
    TOOL_CALLING_ENABLED: bool = True
    # 最多几轮「模型思考 → 调用工具 → 结果回灌」
    TOOL_CALL_MAX_ROUNDS: int = 6
    # 整个工具调用循环的总超时（秒）
    TOOL_CALL_TIMEOUT_SECONDS: int = 120
    # 工具调用使用的模型
    TOOL_CALL_MODEL: str = "deepseek-chat"
    # 是否把未实现的工具也暴露给模型（默认否：避免模型浪费轮次）
    TOOL_CALL_EXPOSE_UNIMPLEMENTED: bool = False

    # --- 内部服务 URL（Docker 中自动覆盖为容器名）---
    MODEL_GATEWAY_URL: str = "http://localhost:8004"
    AGENT_SERVICE_URL: str = "http://localhost:8002"
    KNOWLEDGE_SERVICE_URL: str = "http://localhost:8003"

    # --- 项目路径 ---
    @property
    def PROJECT_ROOT(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例

    会先把 Fernet 加密存储中的敏感 Key 注入进程环境。
    此前只有 chat-service 加载密钥，其余服务独立启动时拿不到
    LLM Key，只能退化为离线回答（Docker 里靠启动时的跨服务推送兜底）。
    环境变量优先级高于 .env，因此这里能覆盖 .env 中的占位符。
    """
    try:
        from shared.utils.secrets import load_secrets

        for key, value in load_secrets().items():
            # 必须覆盖环境中的占位符（compose 会把 .env 的占位值传进来）
            if is_usable_key(value) and not is_usable_key(os.environ.get(key, "")):
                os.environ[key] = value
    except Exception:  # noqa: BLE001
        # 密钥不可用时保持静默，配置仍可正常加载
        pass

    return Settings()