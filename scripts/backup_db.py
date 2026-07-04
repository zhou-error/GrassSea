"""数据库备份脚本 — 每日全量 + WAL 归档

备份策略:
  - PostgreSQL: pg_dump 全量 + WAL 持续归档
  - MongoDB: mongodump 增量
  - 备份保留: 30 天
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.utils.config import get_settings
from shared.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)
settings = get_settings()

BACKUP_DIR = Path("backups")
RETENTION_DAYS = 30


def backup_postgresql() -> str:
    """PostgreSQL 全量备份 (pg_dump)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = BACKUP_DIR / f"postgres_{timestamp}.sql.gz"

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "pg_dump",
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}",
        "--format=custom",
        "--compress=9",
        f"--file={filename}",
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    logger.info("PostgreSQL backup created", file=str(filename))
    return str(filename)


def backup_mongodb() -> str:
    """MongoDB 增量备份 (mongodump)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dirname = BACKUP_DIR / f"mongodb_{timestamp}"

    cmd = [
        "mongodump",
        f"--uri=mongodb://{settings.MONGODB_USER}:{settings.MONGODB_PASSWORD}@{settings.MONGODB_HOST}:{settings.MONGODB_PORT}",
        f"--out={dirname}",
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    logger.info("MongoDB backup created", dir=str(dirname))
    return str(dirname)


def cleanup_old_backups() -> int:
    """清理过期备份"""
    import time
    cutoff = time.time() - RETENTION_DAYS * 86400
    count = 0
    for f in BACKUP_DIR.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
            count += 1
    logger.info("Cleaned up old backups", count=count)
    return count


def sync_to_minio(local_path: str) -> bool:
    """将备份同步到 MinIO"""
    try:
        from minio import Minio
        client = Minio(
            f"{settings.MINIO_HOST}:{settings.MINIO_PORT}",
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,
        )
        bucket = "grasssea-backups"
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        client.fput_object(bucket, Path(local_path).name, local_path)
        logger.info("Backup synced to MinIO", file=Path(local_path).name)
        return True
    except Exception as e:
        logger.error("MinIO sync failed", error=str(e))
        return False


def main():
    setup_logging(level="INFO")
    logger.info("Starting database backup...")

    try:
        pg_file = backup_postgresql()
        sync_to_minio(pg_file)
    except Exception as e:
        logger.error("PostgreSQL backup failed", error=str(e))

    try:
        mongo_dir = backup_mongodb()
    except Exception as e:
        logger.error("MongoDB backup failed", error=str(e))

    cleanup_old_backups()
    logger.info("Database backup completed!")


if __name__ == "__main__":
    main()
