"""文档预处理流水线

支持 PDF, TXT, Markdown 文件解析。
按语义分块 (chunk_size=512, overlap=64)。
向量写入通过 shared.vectorstore 抽象层完成，后端由 VECTOR_BACKEND 决定（local / milvus）。
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import Optional

from shared.utils.config import Settings
from shared.utils.embedding import get_embedder
from shared.vectorstore import VectorRecord, get_vector_store
from shared.utils.logging import get_logger

logger = get_logger(__name__)


class DocumentChunk:
    """文档分块"""
    def __init__(
        self,
        chunk_id: str,
        text: str,
        metadata: dict,
        chunk_index: int,
    ):
        self.chunk_id = chunk_id
        self.text = text
        self.metadata = metadata
        self.chunk_index = chunk_index


class DocumentIngestionPipeline:
    """文档预处理流水线

    步骤：解析 → 清洗 → 分块 → 向量化 → 索引
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.chunk_size = 512
        self.chunk_overlap = 64
        self._embedding_client = None
        # 向量后端由配置决定，上层不再直接依赖 pymilvus
        self._store = get_vector_store(settings)

    async def initialize(self) -> None:
        """初始化向量存储与 Embedding 后端"""
        await self._store.initialize()

        logger.info(
            "Document ingestion pipeline initialized",
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            embedding_model=self.settings.EMBEDDING_MODEL,
            vector_backend=self._store.name,
        )

    async def close(self) -> None:
        """清理资源"""
        await self._store.close()

    async def process_and_index(
        self,
        document_id: str,
        filename: str,
        content: bytes,
        content_type: str,
        knowledge_base: str = "项目知识库",
    ) -> int:
        """处理文档并索引到向量存储

        Args:
            document_id: 文档唯一 ID
            filename: 原始文件名
            content: 文件内容 (bytes)
            content_type: 文件类型 (pdf/txt/md)
            knowledge_base: 所属知识库

        Returns:
            生成的 chunk 数量
        """
        # Step 1: 解析文档为纯文本
        text = await self._parse_document(content, content_type)

        # Step 2: 文本清洗
        text = self._clean_text(text)

        # Step 3: 语义分块
        chunks = self._chunk_text(
            text,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            document_id=document_id,
            filename=filename,
            knowledge_base=knowledge_base,
        )

        # Step 4: 生成 Embedding 并写入向量存储
        await self._index_chunks(chunks)

        logger.info(
            "Document processed",
            doc_id=document_id,
            filename=filename,
            chunks=len(chunks),
            kb=knowledge_base,
        )

        return len(chunks)

    async def _parse_document(self, content: bytes, content_type: str) -> str:
        """解析文档为纯文本"""
        if content_type == "txt":
            return content.decode("utf-8", errors="replace")

        elif content_type in ("md", "markdown"):
            return content.decode("utf-8", errors="replace")

        elif content_type == "pdf":
            return await self._parse_pdf(content)

        else:
            raise ValueError(f"Unsupported content type: {content_type}")

    async def _parse_pdf(self, content: bytes) -> str:
        """解析 PDF 文件"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=content, filetype="pdf")
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE))
            doc.close()
            return "\n\n".join(text_parts)
        except ImportError:
            # 降级：使用 PyPDF2
            from PyPDF2 import PdfReader
            reader = PdfReader(BytesIO(content))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n\n".join(text_parts)

    def _clean_text(self, text: str) -> str:
        """清洗文本"""
        # 合并多余空白
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        # 合并空格
        text = re.sub(r"[ \t]{3,}", "  ", text)
        # 去除首尾空白
        text = text.strip()
        return text

    def _chunk_text(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
        document_id: str,
        filename: str,
        knowledge_base: str,
    ) -> list[DocumentChunk]:
        """按语义分块

        策略：
        1. 优先按段落/章节自然边界切分
        2. 保持 chunk_size=512 tokens（约 1000-1500 中文字符）
        3. overlap=64 tokens（约 100-150 中文字符）
        """
        chunks = []
        # 按段落切分
        paragraphs = re.split(r"\n\n+", text)

        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果当前 chunk + 新段落超出限制，保存当前 chunk
            if len(current_chunk) + len(para) > chunk_size * 2.5:  # ~chars per token
                if current_chunk:
                    chunk = DocumentChunk(
                        chunk_id=f"{document_id}_chunk_{chunk_index}",
                        text=current_chunk.strip(),
                        metadata={
                            "document_id": document_id,
                            "filename": filename,
                            "knowledge_base": knowledge_base,
                            "chunk_index": chunk_index,
                        },
                        chunk_index=chunk_index,
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                    # 保留 overlap
                    overlap_text = current_chunk[-int(chunk_overlap * 2.5):]
                    current_chunk = overlap_text + "\n\n" + para
                else:
                    current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        # 保存最后一个 chunk
        if current_chunk.strip():
            chunk = DocumentChunk(
                chunk_id=f"{document_id}_chunk_{chunk_index}",
                text=current_chunk.strip(),
                metadata={
                    "document_id": document_id,
                    "filename": filename,
                    "knowledge_base": knowledge_base,
                    "chunk_index": chunk_index,
                },
                chunk_index=chunk_index,
            )
            chunks.append(chunk)

        return chunks

    async def _index_chunks(self, chunks: list[DocumentChunk]) -> None:
        """将 chunk 向量化并写入向量存储（后端无关）"""
        if not chunks:
            return

        embeddings = await self._generate_embeddings([c.text for c in chunks])

        records = [
            VectorRecord(
                chunk_id=c.chunk_id,
                text=c.text,
                document_id=str(c.metadata.get("document_id", "")),
                knowledge_base=str(c.metadata.get("knowledge_base", "")),
                filename=str(c.metadata.get("filename", "")),
                chunk_index=c.chunk_index,
            )
            for c in chunks
        ]
        written = await self._store.upsert(records, embeddings)
        logger.debug("分块已写入向量存储", count=written, backend=self._store.name)

    async def _generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """批量生成 Embedding

        使用配置的 EMBEDDING_MODEL（默认 text-embedding-3-large）。
        """
        embedder = get_embedder(self.settings)
        logger.debug("Generating embeddings", count=len(texts), backend=embedder.name)
        return await embedder.embed(texts)
