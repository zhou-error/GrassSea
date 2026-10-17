"""内置向量存储 —— SQLite 持久化 + numpy 精确余弦检索

为什么不用专门的向量库
----------------------
- 零外部依赖：sqlite3 是标准库，numpy 已是项目依赖
- 精确检索：个人知识库规模下（数万条）暴力余弦只需毫秒级，无需 ANN 近似
- 易打包：没有 C++ 扩展，PyInstaller 友好（这是桌面版的硬性要求）

持久化布局：单个 SQLite 文件，向量以 float32 小端字节串存放。
为加速检索，内存中缓存 (ids, 矩阵, 记录) 三元组，写入/删除时失效重建。
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
from pathlib import Path

from shared.utils.logging import get_logger
from shared.vectorstore.base import VectorRecord, VectorStore

logger = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id       TEXT PRIMARY KEY,
    document_id    TEXT NOT NULL DEFAULT '',
    text           TEXT NOT NULL DEFAULT '',
    knowledge_base TEXT NOT NULL DEFAULT '',
    filename       TEXT NOT NULL DEFAULT '',
    chunk_index    INTEGER NOT NULL DEFAULT 0,
    dim            INTEGER NOT NULL,
    embedding      BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_kb  ON chunks(knowledge_base);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
"""


#: 当前 SQLite schema 版本。
#: 改动表结构时：把版本号 +1，并在 _migrate() 里补一段迁移语句。
#: 迁移前会自动把旧库复制成 .bak-<时间戳>，桌面形态没有 DBA 可依赖。
SCHEMA_VERSION = 1


class LocalVectorStore(VectorStore):
    """SQLite + numpy 的内置向量存储"""

    name = "local"

    def __init__(self, settings, collection_name: str = "grasssea_knowledge") -> None:
        super().__init__(settings, collection_name)
        self._db_path: Path | None = None
        # 检索缓存
        self._cache_ids: list[str] = []
        self._cache_matrix = None          # numpy.ndarray[N, dim]
        self._cache_records: list[VectorRecord] = []
        self._lock = asyncio.Lock()
        self._dim: int | None = None

    # ---- 路径 ----

    @staticmethod
    def resolve_db_path(settings) -> Path:
        """解析向量库文件路径（供本类与运维脚本共用，避免路径逻辑重复）"""
        configured = (getattr(settings, "VECTOR_STORE_PATH", "") or "").strip()
        if configured:
            return Path(configured)
        data_dir = (getattr(settings, "DATA_DIR", "") or "").strip()
        base = Path(data_dir) if data_dir else (settings.PROJECT_ROOT / "data")
        return base / "vectorstore" / "knowledge.sqlite3"

    def _resolve_db_path(self) -> Path:
        p = self.resolve_db_path(self.settings)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """按 PRAGMA user_version 升级 schema；升级前自动备份旧库"""
        current = int(conn.execute("PRAGMA user_version").fetchone()[0] or 0)
        if current >= SCHEMA_VERSION:
            return

        # 老库要升级 → 先复制一份，出问题能退回去
        if current > 0 and self._db_path is not None and self._db_path.exists():
            import shutil
            from datetime import datetime

            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = self._db_path.with_name(f"{self._db_path.name}.bak-{stamp}")
            try:
                shutil.copy2(self._db_path, backup)
                logger.info("已备份旧向量库", path=str(backup), from_version=current)
            except Exception as exc:  # noqa: BLE001
                logger.warning("旧向量库备份失败，仍继续迁移", error=str(exc))

        # ---- 迁移区（按需追加）----
        # v0 -> v1：初始版本，建表脚本已由 _SCHEMA 完成，无需 ALTER
        # v1 -> v2：示例 —— 若将来新增字段，写 ALTER TABLE chunks ADD COLUMN xxx TEXT

        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
        logger.info("向量库 schema 已就绪", version=SCHEMA_VERSION, previous=current)

    def _connect(self) -> sqlite3.Connection:
        assert self._db_path is not None
        conn = sqlite3.connect(str(self._db_path), timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ---- 生命周期 ----

    async def initialize(self) -> None:
        try:
            self._db_path = self._resolve_db_path()
            conn = self._connect()
            try:
                conn.executescript(_SCHEMA)
                conn.commit()
                self._migrate(conn)
            finally:
                conn.close()
            self._available = True
            logger.info("内置向量存储已就绪", path=str(self._db_path))
        except Exception as e:  # noqa: BLE001
            self._available = False
            logger.warning("内置向量存储初始化失败", error=str(e))

    @property
    def dim(self) -> int | None:
        """当前索引的向量维度（未知时返回 None），供启动校验使用"""
        return self._dim

    async def close(self) -> None:
        self._cache_ids = []
        self._cache_matrix = None
        self._cache_records = []
        self._available = False

    # ---- 缓存 ----

    def _invalidate_cache(self) -> None:
        self._cache_ids = []
        self._cache_matrix = None
        self._cache_records = []

    def _load_matrix(self) -> None:
        """把全部向量读进内存矩阵（在无事件循环阻塞顾虑的小规模下够用）"""
        if self._cache_matrix is not None or self._db_path is None:
            return
        import numpy as np

        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT chunk_id, document_id, text, knowledge_base, filename, chunk_index, dim, embedding FROM chunks"
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            self._cache_ids, self._cache_records = [], []
            self._cache_matrix = np.zeros((0, self._dim or 1), dtype="float32")
            return

        dim = int(rows[0][6])
        self._dim = dim
        ids: list[str] = []
        records: list[VectorRecord] = []
        buf = np.empty((len(rows), dim), dtype="float32")
        for i, r in enumerate(rows):
            ids.append(r[0])
            buf[i] = np.frombuffer(r[7], dtype="float32", count=dim)
            records.append(VectorRecord(
                chunk_id=r[0], text=r[2], document_id=r[1],
                knowledge_base=r[3], filename=r[4], chunk_index=int(r[5]),
            ))
        self._cache_ids, self._cache_matrix, self._cache_records = ids, buf, records

    # ---- 写入 ----

    async def upsert(self, records: list[VectorRecord], embeddings: list[list[float]]) -> int:
        if not records:
            return 0
        if self._db_path is None:
            await self.initialize()

        import numpy as np

        dim = len(embeddings[0])
        async with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute("SELECT dim FROM chunks LIMIT 1").fetchone()
                if existing is not None and int(existing[0]) != dim:
                    raise RuntimeError(
                        f"内置向量库当前维度为 {int(existing[0])}，而向量后端输出 {dim} 维。"
                        "更换 embedding 模型后必须重建索引（uv run python scripts/reset_knowledge_base.py）后重新入库。"
                    )
                payload = [
                    (
                        r.chunk_id, r.document_id, r.text, r.knowledge_base,
                        r.filename, r.chunk_index, dim,
                        np.asarray(emb, dtype="float32").tobytes(),
                    )
                    for r, emb in zip(records, embeddings)
                ]
                conn.executemany(
                    "INSERT OR REPLACE INTO chunks "
                    "(chunk_id, document_id, text, knowledge_base, filename, chunk_index, dim, embedding) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    payload,
                )
                conn.commit()
            finally:
                conn.close()
            self._invalidate_cache()
            self._dim = dim
        return len(records)

    # ---- 检索 ----

    async def search(
        self,
        embedding: list[float],
        top_k: int,
        knowledge_bases: list[str] | None = None,
    ) -> list[VectorRecord]:
        import numpy as np

        if self._db_path is None:
            return []
        async with self._lock:
            self._load_matrix()
            if not self._cache_ids:
                return []
            matrix = self._cache_matrix
            q = np.asarray(embedding, dtype="float32")
            if q.shape[0] != matrix.shape[1]:
                logger.warning(
                    "查询向量维度与索引不一致，可能更换过 embedding 模型",
                    query_dim=int(q.shape[0]), index_dim=int(matrix.shape[1]),
                )
                return []
            # 余弦相似度（向量已归一化时等价于点积；此处显式归一化以稳妥）
            qn = q / (np.linalg.norm(q) + 1e-9)
            mn = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9)
            sims = mn @ qn

            order = np.argsort(-sims)
            results: list[VectorRecord] = []
            for idx in order:
                rec = self._cache_records[int(idx)]
                if knowledge_bases and rec.knowledge_base not in knowledge_bases:
                    continue
                results.append(VectorRecord(
                    chunk_id=rec.chunk_id, text=rec.text, document_id=rec.document_id,
                    knowledge_base=rec.knowledge_base, filename=rec.filename,
                    chunk_index=rec.chunk_index, score=float(sims[int(idx)]),
                ))
                if len(results) >= top_k:
                    break
            return results

    async def fetch_all(self, limit: int = 16384) -> list[VectorRecord]:
        if self._db_path is None:
            return []
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT chunk_id, document_id, text, knowledge_base, filename, chunk_index "
                "FROM chunks LIMIT ?", (limit,),
            ).fetchall()
        finally:
            conn.close()
        return [
            VectorRecord(chunk_id=r[0], document_id=r[1], text=r[2],
                         knowledge_base=r[3], filename=r[4], chunk_index=int(r[5]))
            for r in rows
        ]

    async def delete_document(self, document_id: str) -> int:
        if self._db_path is None:
            return 0
        async with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
                conn.commit()
                deleted = int(cur.rowcount or 0)
            finally:
                conn.close()
            self._invalidate_cache()
        return deleted

    async def count(self) -> int:
        if self._db_path is None:
            return 0
        conn = self._connect()
        try:
            return int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        except Exception:  # noqa: BLE001
            return 0
        finally:
            conn.close()
