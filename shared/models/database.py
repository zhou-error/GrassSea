"""数据库连接管理模块（全部惰性化）

为什么必须惰性
--------------
本模块被 ORM 模型（shared/models/postgres/*、shared/models/timescale/*）导入以获取 Base；
而 agent_service 又通过 ORM 模型（如 task.py）**间接**导入本模块。
若在导入期就创建连接/引擎，则桌面模式下（VECTOR_BACKEND=local，没有
PostgreSQL / MongoDB / Redis）服务会在启动时直接失败。

因此这里遵守两条规则：
1. 导入期不建立任何连接；pg_engine 通过 PEP 562 的模块级 __getattr__ 延迟创建。
2. 外部驱动（asyncpg / motor / redis / pymilvus）一律在函数内延迟导入。

桌面模式完全不触碰 PostgreSQL / MongoDB / Redis；
服务器模式（docker compose）行为与改造前一致。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator

from sqlalchemy.orm import DeclarativeBase

from shared.utils.config import get_settings

if TYPE_CHECKING:  # 仅用于类型检查，运行时不导入驱动
    from motor.motor_asyncio import AsyncIOMotorDatabase

settings = get_settings()


# ============================================================
# 声明式基类（唯一在导入期可用的符号，被所有 ORM 模型使用）
# ============================================================
class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""

    pass


# ============================================================
# PostgreSQL (SQLAlchemy Async) —— 延迟创建
# ============================================================
_pg_engine: Any = None
_pg_session_factory: Any = None


def _build_pg_engine() -> Any:
    from sqlalchemy.ext.asyncio import create_async_engine

    return create_async_engine(
        settings.POSTGRES_URI,
        echo=settings.APP_DEBUG,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )


def get_pg_engine() -> Any:
    """获取（必要时创建）PostgreSQL 异步引擎"""
    global _pg_engine
    if _pg_engine is None:
        _pg_engine = _build_pg_engine()
    return _pg_engine


def get_pg_session_factory() -> Any:
    """获取（必要时创建）异步会话工厂"""
    global _pg_session_factory
    if _pg_session_factory is None:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        _pg_session_factory = async_sessionmaker(
            get_pg_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _pg_session_factory


def __getattr__(name: str) -> Any:
    """PEP 562：让 pg_engine / pg_session_factory 在首次访问时才创建

    保证 §from shared.models.database import Base§ 不产生任何连接副作用，
    同时让 scripts/init_db.py、scripts/seed_data.py 里的旧写法继续可用。
    """
    if name == "pg_engine":
        return get_pg_engine()
    if name == "pg_session_factory":
        return get_pg_session_factory()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


async def get_pg_session() -> AsyncGenerator[Any, None]:
    """获取 PostgreSQL 异步会话（用于 FastAPI 依赖注入）"""
    async with get_pg_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ============================================================
# MongoDB (Motor) —— 驱动延迟导入
# ============================================================
mongo_client: Any = None
mongo_db: "AsyncIOMotorDatabase | None" = None


async def init_mongodb() -> None:
    """初始化 MongoDB 连接"""
    global mongo_client, mongo_db
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_client = AsyncIOMotorClient(settings.MONGODB_URI)
    mongo_db = mongo_client[settings.MONGODB_DB]
    await mongo_client.admin.command("ping")


async def close_mongodb() -> None:
    """关闭 MongoDB 连接"""
    global mongo_client, mongo_db
    if mongo_client:
        mongo_client.close()
        mongo_client = None
        mongo_db = None


def get_mongo_db() -> "AsyncIOMotorDatabase":
    """获取 MongoDB 数据库实例"""
    if mongo_db is None:
        raise RuntimeError("MongoDB not initialized. Call init_mongodb() first.")
    return mongo_db


# ============================================================
# Redis —— 驱动延迟导入
# ============================================================
redis_client: Any = None


async def init_redis() -> None:
    """初始化 Redis 连接"""
    global redis_client
    from redis.asyncio import Redis

    redis_client = Redis.from_url(settings.REDIS_URI, encoding="utf-8", decode_responses=True)
    await redis_client.ping()


async def close_redis() -> None:
    """关闭 Redis 连接"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


def get_redis() -> Any:
    """获取 Redis 客户端"""
    if redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return redis_client


# ============================================================
# Milvus —— 仅在 VECTOR_BACKEND=milvus 时才会用到
# 注意：向量存取请统一走 shared.vectorstore，这里的方法仅供历史脚本使用。
# ============================================================
def init_milvus() -> None:
    """初始化 Milvus 连接（旧 API，推荐改用 shared.vectorstore）"""
    from pymilvus import connections

    connections.connect(alias="default", host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)


def close_milvus() -> None:
    """关闭 Milvus 连接"""
    from pymilvus import connections

    connections.disconnect("default")
