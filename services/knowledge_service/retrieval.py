"""混合检索模块

实现双路检索：
  - 稠密向量检索 (向量后端余弦相似度，local 或 milvus)
  - 稀疏检索 (BM25 via pyserini / 简易 TF-IDF)
  - 融合策略：dense × 0.7 + sparse × 0.3
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Optional

from shared.utils.config import Settings
from shared.utils.embedding import get_embedder
from shared.utils.logging import get_logger
from shared.vectorstore import get_vector_store

logger = get_logger(__name__)


class SearchResult:
    """检索结果"""
    def __init__(
        self,
        chunk_id: str,
        text: str,
        score: float,
        source: dict | None = None,
        chunk_index: int = 0,
    ):
        self.chunk_id = chunk_id
        self.text = text
        self.score = score
        self.source = source or {}
        self.chunk_index = chunk_index


class HybridRetriever:
    """混合检索器

    稠密向量检索（可插拔后端）+ BM25 稀疏检索 → 融合排序
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.dense_weight = 0.7
        self.sparse_weight = 0.3
        self._bm25_index: dict = {}  # 简易内存 BM25 索引
        self._indexed_count = 0       # 已建索引的 chunk 数（用于自愈判断）
        # 向量后端由配置决定（local / milvus），本模块不直接依赖 pymilvus
        self._store = get_vector_store(settings)
        self._http_client = None

    async def initialize(self) -> None:
        """初始化向量存储与 BM25 索引"""
        await self._store.initialize()
        logger.info("Hybrid retriever initialized", vector_backend=self._store.name)

    async def close(self) -> None:
        """清理资源"""
        await self._store.close()

    async def hybrid_search(
        self,
        query: str,
        top_k: int = 20,
        knowledge_bases: list[str] | None = None,
    ) -> list[SearchResult]:
        """双路混合检索

        Args:
            query: 查询文本
            top_k: 返回结果数（重排序前）
            knowledge_bases: 限定的知识库列表

        Returns:
            融合排序后的检索结果
        """
        # 稀疏索引为空或记录数变化时自动重建（后端无关）
        await self._ensure_sparse_index()

        # 并行执行两路检索
        dense_results = await self._dense_search(query, top_k, knowledge_bases)
        sparse_results = await self._sparse_search(query, top_k, knowledge_bases)

        # 融合分数
        merged = self._merge_results(dense_results, sparse_results)

        # 按融合分数降序排列
        merged.sort(key=lambda x: x.score, reverse=True)

        return merged[:top_k]

    async def _dense_search(
        self,
        query: str,
        top_k: int,
        knowledge_bases: list[str] | None,
    ) -> list[SearchResult]:
        """稠密向量检索（后端无关，由 VECTOR_BACKEND 决定实现）"""
        query_embedding = await self._generate_query_embedding(query)
        try:
            hits = await self._store.search(query_embedding, top_k, knowledge_bases)
        except Exception as e:  # noqa: BLE001
            logger.error("向量检索失败", error=str(e), backend=self._store.name)
            return []

        return [
            SearchResult(
                chunk_id=h.chunk_id,
                text=h.text,
                score=h.score,
                source={
                    "knowledge_base": h.knowledge_base,
                    "filename": h.filename,
                    "chunk_index": h.chunk_index,
                },
                chunk_index=h.chunk_index,
            )
            for h in hits
        ]

    async def _sparse_search(
        self,
        query: str,
        top_k: int,
        knowledge_bases: list[str] | None,
    ) -> list[SearchResult]:
        """稀疏检索 (简易 BM25)

        使用内存 TF-IDF + BM25 评分。
        生产环境可替换为 pyserini / Elasticsearch。
        """
        # 简化 BM25 实现 — 基于已索引的 chunk 构建临时索引
        # 生产环境应使用持久化的倒排索引

        if not self._bm25_index:
            return []

        # 分词（中英文混合）
        tokens = self._tokenize(query)

        # BM25 评分
        k1 = 1.5
        b = 0.75
        scores = defaultdict(float)

        total_docs = self._bm25_index.get("_doc_count", 1)
        avg_dl = self._bm25_index.get("_avg_dl", 100)

        for token in tokens:
            posting_list = self._bm25_index.get(token, {})
            idf = math.log((total_docs - len(posting_list) + 0.5) / (len(posting_list) + 0.5) + 1)

            for doc_id, tf in posting_list.items():
                doc_len = self._bm25_index.get(f"_len_{doc_id}", avg_dl)
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * doc_len / avg_dl)
                scores[doc_id] += idf * numerator / denominator

        # 按分数排序
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for doc_id, score in sorted_docs:
            doc_info = self._bm25_index.get(f"_doc_{doc_id}", {})
            if doc_info:
                results.append(SearchResult(
                    chunk_id=doc_id,
                    text=doc_info.get("text", ""),
                    score=score,
                    source=doc_info.get("source", {}),
                    chunk_index=doc_info.get("chunk_index", 0),
                ))

        return results

    async def _generate_query_embedding(self, query: str) -> list[float]:
        """生成查询向量

        必须与入库共用 shared.utils.embedding 的同一后端，
        否则存入与查询的向量空间不一致，稠密检索将完全失效。
        """
        return await get_embedder(self.settings).embed_one(query)

    async def list_documents(self, knowledge_base: str | None = None) -> list[dict]:
        """列出已入库文档（按 document_id 聚合）"""
        try:
            records = await self._store.fetch_all(limit=16384)
        except Exception as e:  # noqa: BLE001
            logger.warning("文档列表查询失败", error=str(e))
            return []

        grouped: dict[str, dict] = {}
        for rec in records:
            if knowledge_base and rec.knowledge_base != knowledge_base:
                continue
            doc_id = rec.document_id or ""
            if not doc_id:
                # 兼容早期数据：chunk id 形如 <document_id>_chunk_<n>
                doc_id = rec.chunk_id.rsplit("_chunk_", 1)[0] if "_chunk_" in rec.chunk_id else rec.chunk_id
            entry = grouped.setdefault(
                doc_id,
                {
                    "document_id": doc_id,
                    "filename": rec.filename or "(未知文件)",
                    "knowledge_base": rec.knowledge_base,
                    "chunks": 0,
                    "status": "indexed",
                },
            )
            entry["chunks"] += 1
        return sorted(grouped.values(), key=lambda d: d["filename"])

    async def delete_document(self, document_id: str) -> int:
        """删除某文档的全部 chunk，返回删除条数"""
        try:
            deleted = await self._store.delete_document(document_id)
        except Exception as e:  # noqa: BLE001
            logger.error("删除文档失败", document_id=document_id, error=str(e))
            raise
        # 让稀疏索引在下次检索时重建
        self._bm25_index = {}
        self._indexed_count = 0
        return deleted

    async def _ensure_sparse_index(self) -> None:
        """稀疏索引缺失或记录数变化时自动重建（无需外部触发）

        改造前这里读的是 Milvus 的 num_entities；现在统一走向量存储的 count()，
        两种后端行为一致。
        """
        try:
            total = await self._store.count()
        except Exception:  # noqa: BLE001
            total = 0
        if self._bm25_index and total == self._indexed_count:
            return
        await self._rebuild_sparse_index()

    async def _rebuild_sparse_index(self) -> None:
        """拉取全部分块构建内存 BM25 索引（后端无关）

        此前 _bm25_index 从未被填充，稀疏检索恒为空，混合检索实际退化为纯稠密检索。
        """
        try:
            records = await self._store.fetch_all(limit=16384)
        except Exception as e:  # noqa: BLE001
            logger.warning("BM25 索引构建失败", error=str(e))
            return

        index: dict = {}
        total_len = 0
        for rec in records:
            doc_id = rec.chunk_id
            text = rec.text or ""
            tokens = self._tokenize(text)
            index[f"_doc_{doc_id}"] = {
                "text": text,
                "source": {
                    "knowledge_base": rec.knowledge_base,
                    "filename": rec.filename,
                    "chunk_index": rec.chunk_index,
                },
                "chunk_index": rec.chunk_index,
            }
            index[f"_len_{doc_id}"] = len(tokens)
            total_len += len(tokens)
            for token, tf in Counter(tokens).items():
                index.setdefault(token, {})[doc_id] = tf

        index["_doc_count"] = max(len(records), 1)
        index["_avg_dl"] = max(total_len / max(len(records), 1), 1.0)
        self._bm25_index = index
        self._indexed_count = len(records)
        logger.info("BM25 索引已就绪", chunks=len(records))

    def _merge_results(
        self,
        dense: list[SearchResult],
        sparse: list[SearchResult],
    ) -> list[SearchResult]:
        """融合稠密和稀疏检索结果

        dense_score × 0.7 + sparse_score × 0.3
        """
        merged: dict[str, SearchResult] = {}

        # 归一化分数
        max_dense = max((r.score for r in dense), default=1.0) or 1.0
        max_sparse = max((r.score for r in sparse), default=1.0) or 1.0

        for r in dense:
            norm_score = r.score / max_dense
            merged[r.chunk_id] = SearchResult(
                chunk_id=r.chunk_id,
                text=r.text,
                score=norm_score * self.dense_weight,
                source=r.source,
                chunk_index=r.chunk_index,
            )

        for r in sparse:
            norm_score = r.score / max_sparse
            if r.chunk_id in merged:
                merged[r.chunk_id].score += norm_score * self.sparse_weight
            else:
                merged[r.chunk_id] = SearchResult(
                    chunk_id=r.chunk_id,
                    text=r.text,
                    score=norm_score * self.sparse_weight,
                    source=r.source,
                    chunk_index=r.chunk_index,
                )

        return list(merged.values())

    def _tokenize(self, text: str) -> list[str]:
        """简易中英文分词"""
        # 英文
        tokens = re.findall(r"[a-zA-Z]+", text.lower())
        # 中文（二字词）
        chinese = re.findall(r"[一-鿿]", text)
        for i in range(len(chinese) - 1):
            tokens.append(chinese[i] + chinese[i + 1])
        # 单字
        tokens.extend(chinese)
        # 数字
        tokens.extend(re.findall(r"\d+", text))
        return tokens
