"""向量存储抽象层 —— 按配置选择后端

支持的后端（VECTOR_BACKEND）：
- §local§  ：内置 SQLite + numpy 暴力余弦检索，零外部依赖（桌面模式默认）
- §milvus§ ：Milvus 2.4，适合服务器部署与超大规模

上层代码（knowledge_service 的 ingestion / retrieval）只依赖 §VectorStore§ 协议，
不直接引用任何具体后端，因此切换后端只需改一个环境变量。
"""

from __future__ import annotations

from shared.utils.config import Settings
from shared.vectorstore.base import VectorRecord, VectorStore

__all__ = ["VectorRecord", "VectorStore", "get_vector_store", "VECTOR_COLLECTION"]

# 集合/表名在两种后端中保持一致，便于迁移时对照
VECTOR_COLLECTION = "grasssea_knowledge"


def get_vector_store(settings: Settings) -> VectorStore:
    """按配置构造向量存储实例（不建立连接，需再调用 initialize）"""
    backend = (getattr(settings, "VECTOR_BACKEND", "") or "local").strip().lower()

    if backend == "milvus":
        from shared.vectorstore.milvus import MilvusVectorStore

        return MilvusVectorStore(settings, VECTOR_COLLECTION)

    if backend == "local":
        from shared.vectorstore.local import LocalVectorStore

        return LocalVectorStore(settings, VECTOR_COLLECTION)

    # 未知取值时回退到零依赖后端，保证服务仍可用
    from shared.vectorstore.local import LocalVectorStore

    return LocalVectorStore(settings, VECTOR_COLLECTION)
