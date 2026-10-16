"""向量存储协议与数据结构

设计约定
--------
1. §VectorRecord§ 是后端无关的最小记录：一个文本分块 + 它的元数据 + （可选）向量。
2. §VectorStore§ 只暴露 RAG 真正需要的六个动作：
   upsert / search / fetch_all / delete_document / count / close。
3. 所有方法都不得抛出致命异常：连接类失败应记日志并让 §available§ 为 False，
   使上层可以优雅降级（与项目「诚实失败」约定一致）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class VectorRecord:
    """后端无关的向量记录"""

    chunk_id: str
    text: str
    document_id: str = ""
    knowledge_base: str = ""
    filename: str = ""
    chunk_index: int = 0
    # 检索命中时由后端填充分数（余弦相似度，越大越相关）
    score: float = 0.0
    # 写入时由调用方提供；读取时通常为 None 以省内存
    embedding: list[float] | None = field(default=None, repr=False)


class VectorStore(ABC):
    """向量存储协议

    实现方需保证：
    - §initialize()§ 幂等，失败不抛异常（记录日志即可）
    - §upsert()§ 对相同 chunk_id 为覆盖语义
    - §search()§ 返回按 score 降序的结果，score 为余弦相似度
    - §fetch_all()§ 用于上层重建 BM25 索引与列出文档
    """

    #: 后端标识，用于日志
    name: str = "unknown"

    def __init__(self, settings, collection_name: str = "grasssea_knowledge") -> None:
        self.settings = settings
        self.collection_name = collection_name
        self._available = False

    @property
    def available(self) -> bool:
        """后端当前是否可用（连接成功/表已就绪）"""
        return self._available

    # ---- 生命周期 ----

    @abstractmethod
    async def initialize(self) -> None:
        """建立连接 / 建表。失败时只记日志，不抛异常。"""

    @abstractmethod
    async def close(self) -> None:
        """释放资源"""

    # ---- 写入 ----

    @abstractmethod
    async def upsert(self, records: list[VectorRecord], embeddings: list[list[float]]) -> int:
        """写入或覆盖分块，返回写入条数

        实现方必须校验向量维度一致性：维度不符时抛出 RuntimeError，
        并给出可操作的中文提示（换 embedding 模型后需重建索引）。
        """

    # ---- 读取 ----

    @abstractmethod
    async def search(
        self,
        embedding: list[float],
        top_k: int,
        knowledge_bases: list[str] | None = None,
    ) -> list[VectorRecord]:
        """按向量做相似度检索，返回降序结果"""

    @abstractmethod
    async def fetch_all(self, limit: int = 16384) -> list[VectorRecord]:
        """取出全部记录（不含向量），供上层重建 BM25 索引 / 列文档"""

    @abstractmethod
    async def delete_document(self, document_id: str) -> int:
        """删除某文档的全部分块，返回删除条数"""

    @abstractmethod
    async def count(self) -> int:
        """记录总数；后端不可用时返回 0"""
