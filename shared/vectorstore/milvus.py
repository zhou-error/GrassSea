"""Milvus 向量存储后端

由原 §ingestion._insert_to_milvus§ 与 §retrieval._dense_search§ 的逻辑迁移而来，
行为与改造前完全一致（含维度校验、旧 schema 检测、COSINE + IVF_FLAT 索引）。

使用场景：服务器 / Docker 部署，或向量规模超出内置 SQLite 后端的适用区间。

启用方式：§VECTOR_BACKEND=milvus§
"""

from __future__ import annotations

from shared.utils.logging import get_logger
from shared.vectorstore.base import VectorRecord, VectorStore

logger = get_logger(__name__)


class MilvusVectorStore(VectorStore):
    """Milvus 2.4 后端"""

    name = "milvus"

    def __init__(self, settings, collection_name: str = "grasssea_knowledge") -> None:
        super().__init__(settings, collection_name)
        self._collection = None
        self._dim: int | None = None

    # ---- 生命周期 ----

    async def initialize(self) -> None:
        from pymilvus import Collection, connections, utility

        try:
            connections.connect(
                alias="default",
                host=self.settings.MILVUS_HOST,
                port=self.settings.MILVUS_PORT,
            )
            self._available = True
            logger.info("Milvus 已连接", host=self.settings.MILVUS_HOST, port=self.settings.MILVUS_PORT)
        except Exception as e:  # noqa: BLE001
            self._available = False
            logger.warning("Milvus 连接失败", error=str(e))
            return

        try:
            if utility.has_collection(self.collection_name):
                self._collection = Collection(name=self.collection_name)
                self._collection.load()
                self._dim = self._read_dim(self._collection)
                logger.info("Milvus 集合已绑定", name=self.collection_name, dim=self._dim)
            else:
                logger.info("Milvus 集合尚不存在，将在首次写入时创建", name=self.collection_name)
        except Exception as e:  # noqa: BLE001
            logger.warning("Milvus 集合绑定失败", error=str(e))
            self._collection = None

    async def close(self) -> None:
        from pymilvus import connections

        try:
            connections.disconnect("default")
        except Exception:  # noqa: BLE001
            pass
        self._collection = None
        self._available = False

    @staticmethod
    def _read_dim(collection) -> int | None:
        try:
            return next(
                (int(f.params["dim"]) for f in collection.schema.fields if f.name == "embedding"),
                None,
            )
        except Exception:  # noqa: BLE001
            return None

    async def _ensure_collection(self):
        """集合在首次写入时才创建，检索前需重新确认绑定"""
        from pymilvus import Collection, utility

        if self._collection is not None:
            return self._collection
        try:
            if not utility.has_collection(self.collection_name):
                return None
            self._collection = Collection(name=self.collection_name)
            self._collection.load()
            self._dim = self._read_dim(self._collection)
            logger.info("Milvus 集合已绑定", name=self.collection_name, dim=self._dim)
        except Exception as e:  # noqa: BLE001
            logger.warning("Milvus 集合绑定失败", error=str(e))
            self._collection = None
        return self._collection

    # ---- 写入 ----

    async def upsert(self, records: list[VectorRecord], embeddings: list[list[float]]) -> int:
        if not records:
            return 0

        from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, utility

        dim = len(embeddings[0])

        if not utility.has_collection(self.collection_name):
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
                FieldSchema(name="knowledge_base", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
            ]
            schema = CollectionSchema(fields, description="GrassSea Knowledge Base")
            collection = Collection(name=self.collection_name, schema=schema)
            collection.create_index(
                field_name="embedding",
                index_params={"metric_type": "COSINE", "index_type": "IVF_FLAT", "params": {"nlist": 128}},
            )
            collection.load()
        else:
            collection = Collection(name=self.collection_name)
            existing_dim = self._read_dim(collection)
            if existing_dim is not None and existing_dim != dim:
                raise RuntimeError(
                    f"Milvus 集合 '{self.collection_name}' 当前维度为 {existing_dim}，"
                    f"而向量后端输出 {dim} 维。更换 embedding 模型后必须重建该集合后重新入库。"
                )
            if "document_id" not in {f.name for f in collection.schema.fields}:
                raise RuntimeError(
                    f"Milvus 集合 '{self.collection_name}' 是旧 schema（缺少 document_id 字段），"
                    "无法支持文档列表与删除。请先执行 "
                    "uv run python scripts/reset_knowledge_base.py 重建集合，再重新上传文档。"
                )
            collection.load()

        collection.insert([
            [r.chunk_id for r in records],
            [r.document_id for r in records],
            [r.text for r in records],
            embeddings,
            [r.knowledge_base for r in records],
            [r.filename for r in records],
            [r.chunk_index for r in records],
        ])
        collection.flush()
        self._collection = collection
        self._dim = dim
        logger.debug("分块已写入 Milvus", count=len(records))
        return len(records)

    # ---- 检索 ----

    async def search(
        self,
        embedding: list[float],
        top_k: int,
        knowledge_bases: list[str] | None = None,
    ) -> list[VectorRecord]:
        collection = await self._ensure_collection()
        if collection is None:
            return []

        expr = None
        if knowledge_bases:
            expr = " or ".join(f'knowledge_base == "{kb}"' for kb in knowledge_bases)

        try:
            results = collection.search(
                data=[embedding],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"nprobe": 16}},
                limit=top_k,
                expr=expr,
                output_fields=["text", "document_id", "knowledge_base", "filename", "chunk_index"],
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Milvus 检索失败", error=str(e))
            return []

        out: list[VectorRecord] = []
        for hits in results:
            for hit in hits:
                ent = hit.entity
                out.append(VectorRecord(
                    chunk_id=str(hit.id),
                    text=ent.get("text", ""),
                    document_id=ent.get("document_id", "") or "",
                    knowledge_base=ent.get("knowledge_base", ""),
                    filename=ent.get("filename", ""),
                    chunk_index=int(ent.get("chunk_index", 0) or 0),
                    score=float(hit.distance),
                ))
        return out

    async def fetch_all(self, limit: int = 16384) -> list[VectorRecord]:
        collection = await self._ensure_collection()
        if collection is None:
            return []
        try:
            rows = collection.query(
                expr='id != ""',
                output_fields=["id", "document_id", "text", "knowledge_base", "filename", "chunk_index"],
                limit=limit,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Milvus 全量读取失败", error=str(e))
            return []
        return [
            VectorRecord(
                chunk_id=str(r.get("id", "")),
                text=r.get("text", "") or "",
                document_id=str(r.get("document_id") or ""),
                knowledge_base=r.get("knowledge_base", ""),
                filename=r.get("filename", ""),
                chunk_index=int(r.get("chunk_index", 0) or 0),
            )
            for r in rows
        ]

    async def delete_document(self, document_id: str) -> int:
        collection = await self._ensure_collection()
        if collection is None:
            return 0
        result = collection.delete(f'document_id == "{document_id}"')
        collection.flush()
        return int(getattr(result, "delete_count", 0) or 0)

    async def count(self) -> int:
        collection = await self._ensure_collection()
        if collection is None:
            return 0
        try:
            return int(collection.num_entities)
        except Exception:  # noqa: BLE001
            return 0
