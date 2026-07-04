"""GrassSea AI — 统一配置管理模块

基于 pydantic-settings，支持环境变量覆盖 (.env 文件)。
所有配置项均通过环境变量注入，不硬编码敏感信息。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # --- JWT ---
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- LLM API Keys (通过环境变量注入) ---
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    CLAUDE_API_KEY: str = ""
    CLAUDE_BASE_URL: str = "https://api.anthropic.com"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # --- Embedding ---
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIM: int = 3072
    LOCAL_EMBEDDING_MODEL: str = "BAAI/bge-large-zh-v1.5"

    # --- Search ---
    BRAVE_SEARCH_API_KEY: str = ""
    BING_SEARCH_API_KEY: str = ""

    # --- 项目路径 ---
    @property
    def PROJECT_ROOT(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()