"""知识库服务 (Knowledge Service)

提供 RAG 检索增强生成能力。
- 文档上传与预处理
- 向量化索引
- 混合检索（稠密 + 稀疏）
- 重排序
- 答案生成（带引用标注）
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from services.knowledge_service.ingestion import DocumentIngestionPipeline
from services.knowledge_service.retrieval import HybridRetriever
from services.knowledge_service.reranker import Reranker
from services.knowledge_service.generator import AnswerGenerator
from shared.utils.config import get_settings
from shared.utils.logging import get_logger, setup_logging, set_trace_id

logger = get_logger(__name__)
settings = get_settings()

# 全局组件
ingestion_pipeline: DocumentIngestionPipeline | None = None
retriever: HybridRetriever | None = None
reranker: Reranker | None = None
generator: AnswerGenerator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    global ingestion_pipeline, retriever, reranker, generator
    setup_logging(level="DEBUG" if settings.APP_DEBUG else "INFO")
    logger.info("Knowledge Service starting...")

    ingestion_pipeline = DocumentIngestionPipeline(settings)
    retriever = HybridRetriever(settings)
    reranker = Reranker()
    generator = AnswerGenerator(settings)

    await ingestion_pipeline.initialize()
    await retriever.initialize()

    logger.info("Knowledge Service started", port=settings.KNOWLEDGE_SERVICE_PORT)
    yield

    logger.info("Knowledge Service shutting down...")
    if ingestion_pipeline:
        await ingestion_pipeline.close()
    if retriever:
        await retriever.close()


app = FastAPI(
    title="GrassSea Knowledge Service",
    version="0.1.0",
    lifespan=lifespan,
)


# ---- 请求/响应模型 ----

class RAGQueryRequest(BaseModel):
    """RAG 查询请求"""
    query: str = Field(..., description="用户查询文本")
    top_k: int = Field(default=5, ge=1, le=20)
    knowledge_bases: list[str] = Field(
        default=["规范标准库", "船舶设计库"],
        description="检索的知识库列表"
    )
    stream: bool = Field(default=False)
    include_sources: bool = Field(default=True)


class SearchResult(BaseModel):
    """单条检索结果"""
    chunk_id: str
    text: str
    score: float
    source: dict = Field(default_factory=dict)
    chunk_index: int = 0


class RAGQueryResponse(BaseModel):
    """RAG 查询响应"""
    query: str
    answer: str
    sources: list[SearchResult] = Field(default_factory=list)
    retrieval_time_ms: float = 0
    generation_time_ms: float = 0


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""
    document_id: str
    filename: str
    status: str
    chunks_count: int = 0


# ---- 端点 ----

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "knowledge-service",
        "version": settings.APP_VERSION,
    }


@app.post("/rag/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest):
    """RAG 检索问答

    完整的 RAG 流程：检索 → 重排序 → 生成
    """
    trace_id = str(uuid.uuid4())[:8]
    set_trace_id(trace_id)

    import time

    # Step 1: 混合检索
    t0 = time.time()
    search_results = await retriever.hybrid_search(
        query=request.query,
        top_k=request.top_k * 4,  # 先取 Top-20，再重排序
        knowledge_bases=request.knowledge_bases,
    )
    retrieval_time = (time.time() - t0) * 1000

    # Step 2: 重排序
    t0 = time.time()
    if request.top_k < len(search_results):
        search_results = await reranker.rerank(
            query=request.query,
            candidates=search_results,
            top_k=request.top_k,
        )
    rerank_time = (time.time() - t0) * 1000

    # Step 3: 构建上下文并生成答案
    t0 = time.time()
    answer = await generator.generate(
        query=request.query,
        contexts=[r.text for r in search_results],
        sources=search_results if request.include_sources else [],
    )
    generation_time = (time.time() - t0) * 1000

    logger.info(
        "RAG query completed",
        query=request.query[:100],
        retrieved=len(search_results),
        retrieval_ms=round(retrieval_time, 1),
        generation_ms=round(generation_time, 1),
    )

    return RAGQueryResponse(
        query=request.query,
        answer=answer,
        sources=search_results if request.include_sources else [],
        retrieval_time_ms=retrieval_time + rerank_time,
        generation_time_ms=generation_time,
    )


@app.post("/rag/documents", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    knowledge_base: str = Query(default="项目知识库"),
):
    """上传文档并触发索引

    支持格式: PDF, TXT, Markdown
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # 检查文件类型
    allowed_extensions = {".pdf", ".txt", ".md", ".markdown"}
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {allowed_extensions}",
        )

    # 读取文件内容
    content = await file.read()

    # 文档预处理与索引
    doc_id = str(uuid.uuid4())
    chunks_count = await ingestion_pipeline.process_and_index(
        document_id=doc_id,
        filename=file.filename,
        content=content,
        content_type=ext.lstrip("."),
        knowledge_base=knowledge_base,
    )

    logger.info(
        "Document indexed",
        doc_id=doc_id,
        filename=file.filename,
        chunks=chunks_count,
        kb=knowledge_base,
    )

    return DocumentUploadResponse(
        document_id=doc_id,
        filename=file.filename,
        status="indexed",
        chunks_count=chunks_count,
    )


@app.get("/rag/documents/{document_id}/status")
async def get_document_status(document_id: str):
    """查询文档索引状态"""
    return {
        "document_id": document_id,
        "status": "indexed",  # pending / indexing / indexed / failed
    }
