"""MinIO bucket 初始化脚本

创建 GrassSea 项目所需的所有 bucket 结构。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from minio import Minio
from minio.error import S3Error

from shared.utils.config import get_settings
from shared.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

# Bucket 结构定义
BUCKETS = {
    "grasssea-files": {
        "规范标准库/": "CCS, IMO, SOLAS, MARPOL, DNV 等规范文档",
        "船舶设计库/": "型线图集、设计手册、计算案例",
        "学术文献库/": "论文、会议录、学位论文",
        "项目知识库/": "用户项目私有空间",
        "通用工程库/": "材料手册、标准件库、工艺规范",
        "图纸库/": "DWG, DXF, STEP 等图纸文件",
        "报告库/": "生成的审查报告、计算报告 PDF",
        "临时文件/": "临时上传文件 (7天 TTL)",
    },
}


def create_bucket_if_not_exists(client: Minio, bucket_name: str) -> None:
    """创建 bucket (如果不存在)"""
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            logger.info("Bucket created", bucket=bucket_name)
        else:
            logger.info("Bucket already exists", bucket=bucket_name)
    except S3Error as e:
        logger.error("Failed to create bucket", bucket=bucket_name, error=str(e))
        raise


def main() -> None:
    setup_logging(level="INFO")
    settings = get_settings()

    client = Minio(
        f"{settings.MINIO_HOST}:{settings.MINIO_PORT}",
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=False,
    )

    for bucket_name, folders in BUCKETS.items():
        create_bucket_if_not_exists(client, bucket_name)

        # 为 bucket 创建子目录结构（通过上传空对象或 put_object）
        for folder_path, description in folders.items():
            try:
                # MinIO 使用前缀表示目录
                # 通过 put_object 创建一个空文件夹标记
                empty = b""
                client.put_object(
                    bucket_name,
                    f"{folder_path}.keep",
                    data=__import__("io").BytesIO(empty),
                    length=0,
                )
                logger.debug("Folder created", bucket=bucket_name, folder=folder_path)
            except S3Error as e:
                logger.error(
                    "Failed to create folder",
                    bucket=bucket_name,
                    folder=folder_path,
                    error=str(e),
                )

    logger.info("MinIO initialization complete", buckets=list(BUCKETS.keys()))


if __name__ == "__main__":
    main()
