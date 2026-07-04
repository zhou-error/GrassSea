"""混合检索模块

实现双路检索：
  - 稠密向量检索 (Milvus COSINE similarity)
  - 稀疏检索 (BM25 via pyserini / 简易 TF-IDF)
  - 融合策略：dense × 0.7 + sparse × 0.3
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Optional

from shared.utils.config import Settings
from shared.utils.logging import get_logger

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

    稠密向量检索 (Milvus) + BM25 稀疏检索 → 融合排序
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.dense_weight = 0.7
        self.sparse_weight = 0.3
        self._bm25_index: dict = {}  # 简易内存 BM25 索引
        self._http_client = None

    async def initialize(self) -> None:
        """初始化 Milvus 连接和 BM25 索引"""
        from pymilvus import connections, Collection, utility

        try:
            connections.connect(
                alias="retriever",
                host=self.settings.MILVUS_HOST,
                port=self.settings.MILVUS_PORT,
            )
            logger.info("Milvus connected for retrieval")
        except Exception as e:
            logger.warning("Milvus connection failed, using fallback", error=str(e))

        # 加载 collection
        self._collection_name = "grasssea_knowledge"
        if utility.has_collection(self._collection_name):
            self._collection = Collection(name=self._collection_name)
            self._collection.load()
        else:
            logger.warning("Milvus collection not found, will create on first insert")
            self._collection = None

        logger.info("Hybrid retriever initialized")

    async def close(self) -> None:
        """清理资源"""
        from pymilvus import connections
        try:
            connections.disconnect("retriever")
        except Exception:
            pass

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
        """稠密向量检索 (Milvus)"""
        if self._collection is None:
            return []

        # 生成查询 embedding
        query_embedding = await self._generate_query_embedding(query)

        # Milvus 搜索
        try:
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 16},
            }

            # 构建过滤表达式
            expr = None
            if knowledge_bases:
                kb_conditions = [f'knowledge_base == "{kb}"' for kb in knowledge_bases]
                expr = " or ".join(kb_conditions)

            results = self._collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["text", "knowledge_base", "filename", "chunk_index"],
            )

            search_results = []
            for hits in results:
                for hit in hits:
                    search_results.append(SearchResult(
                        chunk_id=hit.id,
                        text=hit.entity.get("text", ""),
                        score=float(hit.distance),
                        source={
                            "knowledge_base": hit.entity.get("knowledge_base", ""),
                            "filename": hit.entity.get("filename", ""),
                            "chunk_index": hit.entity.get("chunk_index", 0),
                        },
                        chunk_index=hit.entity.get("chunk_index", 0),
                    ))

            return search_results
        except Exception as e:
            logger.error("Milvus search error", error=str(e))
            return []

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
        """生成查询 embedding"""
        if not self.settings.OPENAI_API_KEY:
            import hashlib
            h = hashlib.sha256(query.encode()).digest()
            vec = [float(b) / 255.0 for b in h[:self.settings.EMBEDDING_DIM]]
            if len(vec) < self.settings.EMBEDDING_DIM:
                vec += [0.0] * (self.settings.EMBEDDING_DIM - len(vec))
            return vec[:self.settings.EMBEDDING_DIM]

        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.settings.OPENAI_BASE_URL}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.EMBEDDING_MODEL,
                    "input": [query],
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]

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
