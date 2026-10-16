"""重建 Milvus 知识库集合

用途:
  1. 更换 embedding 模型后维度不匹配；
  2. 集合是旧 schema（缺少 document_id 字段）；
  3. 想清空知识库重来。

⚠️ 会删除集合内全部向量（原始文件需重新上传）。

用法:
    uv run python scripts/reset_knowledge_base.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymilvus import Collection, connections, utility  # noqa: E402

from shared.utils.config import get_settings  # noqa: E402

COLLECTION = "grasssea_knowledge"


def main() -> None:
    settings = get_settings()
    connections.connect(alias="default", host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)

    if utility.has_collection(COLLECTION):
        collection = Collection(COLLECTION)
        rows = collection.num_entities
        utility.drop_collection(COLLECTION)
        print(f"已删除集合 {COLLECTION}（原有 {rows} 条向量）")
    else:
        print(f"集合 {COLLECTION} 不存在，无需删除")

    print("集合将在下次上传文档时按新 schema 自动创建。")
    connections.disconnect("default")


if __name__ == "__main__":
    main()
