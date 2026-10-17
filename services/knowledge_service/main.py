"""知识库服务 (Knowledge Service)

提供 RAG 检索增强生成能力。
- 文档上传与预处理
- 向量化索引
- 混合检索（稠密 + 稀疏）
- 重排序
- 答案生成（带引用标注）
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field

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
async def _check_vector_dimension() -> None:
    """比对已存向量维度与当前 embedding 后端维度，不一致则明确提示"""
    try:
        from shared.utils.embedding import get_embedder

        stored_dim = 0
        try:
            stored_dim = int(getattr(retriever._store, "dim", None) or 0)
        except Exception:  # noqa: BLE001
            stored_dim = 0
        if not stored_dim:
            records = await retriever._store.fetch_all(limit=1)
            if not records:
                return  # 空库，无需校验
            stored_dim = 0
            return

        embedder = get_embedder(settings)
        probe = await embedder.embed_one("dimension probe")
        current_dim = len(probe)

        if current_dim != stored_dim:
            msg = (
                f"向量维度不一致：索引中已存 {stored_dim} 维，当前 embedding 后端输出 {current_dim} 维。"
                "请执行 uv run python scripts/reset_knowledge_base.py 后重新上传文档。"
            )
            logger.error("向量维度校验失败", stored_dim=stored_dim, current_dim=current_dim)
            print(f"\n[警告] {msg}\n", flush=True)
        else:
            logger.info("向量维度校验通过", dim=current_dim)
    except Exception as exc:  # noqa: BLE001
        logger.warning("向量维度校验未能执行", error=str(exc))


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

    # 启动时校验向量维度：换过 embedding 模型只会在检索时报错，且报错不直观
    await _check_vector_dimension()

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
    knowledge_bases: list[str] | None = Field(
        default=None,
        description="限定的知识库列表；留空表示检索全部知识库"
    )
    stream: bool = Field(default=False)
    include_sources: bool = Field(default=True)


class SearchResult(BaseModel):
    """单条检索结果

    注意：retrieval.py 里同名的是普通类，这里必须允许按属性读取，
    否则 /rag/query 在检索到结果时会因模型校验失败而 500。
    """
    model_config = ConfigDict(from_attributes=True)

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

class DocumentItem(BaseModel):
    """已入库文档"""
    document_id: str
    filename: str
    knowledge_base: str = ""
    chunks: int = 0
    status: str = "indexed"


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    total: int
    documents: list[DocumentItem] = Field(default_factory=list)


class DeleteDocumentResponse(BaseModel):
    """删除文档响应"""
    document_id: str
    deleted_chunks: int
    status: str


# ---- 端点 ----

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "knowledge-service",
        "version": settings.APP_VERSION,
    }


@app.get("/admin/status")
async def admin_status():
    """查看当前配置状态"""
    return {
        "service": "knowledge-service",
        "deepseek_configured": bool(settings.DEEPSEEK_API_KEY),
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "embedding_model": settings.EMBEDDING_MODEL,
        "model_gateway_url": getattr(settings, "MODEL_GATEWAY_URL", ""),
    }


@app.post("/admin/reload")
async def reload_config(config: dict[str, str]):
    """运行时重载配置，无需重启容器。

    接受部分更新：{"DEEPSEEK_API_KEY": "sk-xxx", "OPENAI_API_KEY": "sk-xxx", ...}
    会重新初始化检索器和生成器。
    """
    global retriever, generator, ingestion_pipeline

    updated = False
    for key, value in config.items():
        if hasattr(settings, key):
            old_value = getattr(settings, key, "")
            setattr(settings, key, value)
            os.environ[key] = value
            if old_value != value:
                updated = True
            logger.info("Knowledge config reloaded", key=key, changed=(old_value != value))

    if updated:
        retriever = HybridRetriever(settings)
        await retriever.initialize()
        generator = AnswerGenerator(settings)
        ingestion_pipeline = DocumentIngestionPipeline(settings)
        await ingestion_pipeline.initialize()
        logger.info("Knowledge components re-initialized")

    return {
        "status": "ok",
        "deepseek_configured": bool(settings.DEEPSEEK_API_KEY),
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "message": "配置已更新" if updated else "无变化",
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

@app.get("/rag/documents", response_model=DocumentListResponse)
async def list_documents(knowledge_base: str | None = Query(default=None)):
    """列出已索引文档（按 document_id 聚合）"""
    if retriever is None:
        raise HTTPException(status_code=503, detail="Retriever not ready")
    documents = await retriever.list_documents(knowledge_base=knowledge_base)
    return DocumentListResponse(total=len(documents), documents=documents)


@app.delete("/rag/documents/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(document_id: str):
    """删除指定文档及其全部 chunk"""
    if retriever is None:
        raise HTTPException(status_code=503, detail="Retriever not ready")
    deleted = await retriever.delete_document(document_id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return DeleteDocumentResponse(
        document_id=document_id,
        deleted_chunks=deleted,
        status="deleted",
    )


@app.get("/rag/documents/{document_id}/status")
async def get_document_status(document_id: str):
    """查询文档索引状态"""
    return {
        "document_id": document_id,
        "status": "indexed",  # pending / indexing / indexed / failed
    }
