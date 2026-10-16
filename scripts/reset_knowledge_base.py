"""重建知识库索引

用途:
  1. 更换 embedding 模型后维度不匹配；
  2. 索引是旧 schema；
  3. 想清空知识库重来。

⚠️ 会删除索引中的全部向量（原始文件需要重新上传）。

后端由 VECTOR_BACKEND 决定：
  - local （默认）：删除内置 SQLite 向量库文件
  - milvus        ：删除 Milvus 集合

用法:
    uv run python scripts/reset_knowledge_base.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.utils.config import get_settings  # noqa: E402
from shared.vectorstore import VECTOR_COLLECTION  # noqa: E402


def reset_local(db_path: Path) -> None:
    """删除内置向量库文件（含 WAL/SHM 附属文件）"""
    if not db_path.exists():
        print(f"内置向量库不存在，无需删除：{db_path}")
        return
    removed = 0
    for suffix in ("", "-wal", "-shm"):
        f = Path(str(db_path) + suffix)
        if f.exists():
            f.unlink()
            removed += 1
    print(f"已删除内置向量库（{removed} 个文件）：{db_path}")


def reset_milvus(host: str, port: int) -> None:
    """删除 Milvus 集合"""
    from pymilvus import Collection, connections, utility

    connections.connect(alias="default", host=host, port=port)
    try:
        if utility.has_collection(VECTOR_COLLECTION):
            rows = Collection(VECTOR_COLLECTION).num_entities
            utility.drop_collection(VECTOR_COLLECTION)
            print(f"已删除集合 {VECTOR_COLLECTION}（原有 {rows} 条向量）")
        else:
            print(f"集合 {VECTOR_COLLECTION} 不存在，无需删除")
    finally:
        connections.disconnect("default")


def main() -> None:
    settings = get_settings()
    backend = (getattr(settings, "VECTOR_BACKEND", "") or "local").strip().lower()
    print(f"向量后端：{backend}")

    if backend == "milvus":
        reset_milvus(settings.MILVUS_HOST, settings.MILVUS_PORT)
        print("集合将在下次上传文档时按新 schema 自动创建。")
    else:
        from shared.vectorstore.local import LocalVectorStore

        reset_local(LocalVectorStore.resolve_db_path(settings))
        print("数据表将在下次服务启动时自动创建。")


if __name__ == "__main__":
    main()
