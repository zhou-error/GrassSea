"""数据库一键建表脚本（个人开发环境）

用法（任选其一）:
    .venv\\Scripts\\python.exe scripts/init_db.py
    uv run python scripts/init_db.py

说明:
    - 使用 SQLAlchemy metadata 建表，幂等（已存在的表会跳过）。
    - 先创建 timeseries schema：4 张时序表定义在该 schema 下，缺失会导致整体建表失败。
    - 若实例支持 TimescaleDB，尽力把 4 张时序表转为 hypertable；不支持时自动跳过。
    - 正式的版本化迁移仍走 Alembic: alembic upgrade head
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from shared.models.database import Base, pg_engine  # noqa: E402

import shared.models.postgres  # noqa: F401,E402
import shared.models.timescale  # noqa: F401,E402

TIMESERIES_SCHEMA = "timeseries"
TIMESERIES_TABLES = (
    "token_usage_metrics",
    "api_latency_metrics",
    "tool_call_metrics",
    "session_metrics",
)


async def create_schema_and_tables() -> None:
    async with pg_engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TIMESERIES_SCHEMA}"))
        await conn.run_sync(Base.metadata.create_all)


async def convert_to_hypertables() -> str:
    """尽力把时序表转成 hypertable；非 TimescaleDB 实例直接跳过。"""
    try:
        async with pg_engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
            for table in TIMESERIES_TABLES:
                await conn.execute(
                    text(
                        "SELECT create_hypertable("
                        f"'{TIMESERIES_SCHEMA}.{table}', 'time', "
                        "if_not_exists => TRUE, migrate_data => TRUE)"
                    )
                )
        return "TimescaleDB 超表已就绪"
    except Exception as exc:  # noqa: BLE001
        return f"跳过 TimescaleDB 超表转换（{type(exc).__name__}）"


async def main() -> None:
    await create_schema_and_tables()
    print(f"建表完成，共 {len(Base.metadata.tables)} 张表:")
    for name in sorted(Base.metadata.tables):
        print("  -", name)
    print(await convert_to_hypertables())
    await pg_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
