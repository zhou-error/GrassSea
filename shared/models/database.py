"""数据库连接管理模块

管理 PostgreSQL (async), MongoDB (async), Redis, Milvus 连接。
"""

from __future__ import annotations

from typing import AsyncGenerator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from shared.utils.config import get_settings

settings = get_settings()

# ============================================================
# PostgreSQL (SQLAlchemy Async)
# ============================================================
pg_engine = create_async_engine(
    settings.POSTGRES_URI,
    echo=settings.APP_DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

pg_session_factory = async_sessionmaker(
    pg_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


async def get_pg_session() -> AsyncGenerator[AsyncSession, None]:
    """获取 PostgreSQL 异步会话 (用于 FastAPI 依赖注入)"""
    async with pg_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ============================================================
# MongoDB (Motor Async)
# ============================================================
mongo_client: AsyncIOMotorClient | None = None
mongo_db: AsyncIOMotorDatabase | None = None


async def init_mongodb() -> None:
    """初始化 MongoDB 连接"""
    global mongo_client, mongo_db
    mongo_client = AsyncIOMotorClient(settings.MONGODB_URI)
    mongo_db = mongo_client[settings.MONGODB_DB]
    # 验证连接
    await mongo_client.admin.command("ping")


async def close_mongodb() -> None:
    """关闭 MongoDB 连接"""
    global mongo_client
    if mongo_client:
        mongo_client.close()
        mongo_client = None


def get_mongo_db() -> AsyncIOMotorDatabase:
    """获取 MongoDB 数据库实例 (用于 FastAPI 依赖注入)"""
    if mongo_db is None:
        raise RuntimeError("MongoDB not initialized. Call init_mongodb() first.")
    return mongo_db


# ============================================================
# Redis (Async)
# ============================================================
redis_client: Redis | None = None


async def init_redis() -> None:
    """初始化 Redis 连接"""
    global redis_client
    redis_client = Redis.from_url(
        settings.REDIS_URI,
        encoding="utf-8",
        decode_responses=True,
    )
    await redis_client.ping()


async def close_redis() -> None:
    """关闭 Redis 连接"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


def get_redis() -> Redis:
    """获取 Redis 客户端 (用于 FastAPI 依赖注入)"""
    if redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return redis_client


# ============================================================
# Milvus (pymilvus)
# ============================================================
from pymilvus import connections


def init_milvus() -> None:
    """初始化 Milvus 连接"""
    connections.connect(
        alias="default",
        host=settings.MILVUS_HOST,
        port=settings.MILVUS_PORT,
    )


def close_milvus() -> None:
    """关闭 Milvus 连接"""
    connections.disconnect("default")
