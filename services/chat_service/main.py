"""对话服务 (Chat Service) — 前端 API 网关，提供路由转发到各后端服务。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx

import os

from services.chat_service.attachments import MAX_TEXT_CHARS, process_upload
from services.chat_service.config_api import router as config_router
from shared.utils.config import get_settings
from shared.utils.logging import get_logger, setup_logging

# Docker 环境中使用服务名，本地开发用 localhost
AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:8002")
KNOWLEDGE_SERVICE_URL = os.getenv("KNOWLEDGE_SERVICE_URL", "http://localhost:8003")

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(level="DEBUG" if settings.APP_DEBUG else "INFO")
    logger.info("Chat Service starting...")

    # 将加密存储的 API Key 推送到下游服务（带重试）
    from services.chat_service.config_api import _propagate_all_secrets
    await _propagate_all_secrets()

    yield


app = FastAPI(title="GrassSea Chat Service", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(config_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "chat-service", "version": settings.APP_VERSION}


# ---- 路由转发 ----

@app.post("/chat")
async def proxy_chat(request: Request):
    """转发对话请求到智能体编排服务 (8002)"""
    body = await request.json()
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{AGENT_SERVICE_URL}/chat", json=body,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.post("/rag/query")
async def proxy_rag_query(request: Request):
    """转发 RAG 查询到知识库服务 (8003)"""
    body = await request.json()
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{KNOWLEDGE_SERVICE_URL}/rag/query", json=body,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.post("/rag/documents")
async def proxy_rag_upload(request: Request):
    """转发文档上传到知识库服务 (8003)"""
    form = await request.form()
    async with httpx.AsyncClient(timeout=120) as client:
        # 重新构建 multipart
        files = {}
        data = {}
        for key, value in form.items():
            if hasattr(value, "filename"):
                files[key] = (value.filename, await value.read(), value.content_type)
            else:
                data[key] = str(value)

        resp = await client.post(
            f"{KNOWLEDGE_SERVICE_URL}/rag/documents",
            params=dict(request.query_params),
            data=data, files=files,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.get("/rag/documents")
async def proxy_rag_documents(request: Request):
    """转发文档列表到知识库服务 (8003)"""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            f"{KNOWLEDGE_SERVICE_URL}/rag/documents",
            params=dict(request.query_params),
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.delete("/rag/documents/{document_id}")
async def proxy_rag_delete(document_id: str):
    """转发文档删除到知识库服务 (8003)"""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.delete(
            f"{KNOWLEDGE_SERVICE_URL}/rag/documents/{document_id}",
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.get("/tasks")
async def proxy_tasks():
    """转发任务列表到智能体编排服务 (8002)"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{AGENT_SERVICE_URL}/tasks")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.get("/agents")
async def proxy_agents():
    """转发智能体列表到智能体编排服务 (8002)"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{AGENT_SERVICE_URL}/agents")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


#: 单个附件大小上限（字节）——防止误传超大文件撑爆内存与上下文
MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024


@app.post("/attachments")
async def upload_attachment(file: UploadFile = File(...)):
    """接收单个附件：落盘 + 提取正文，返回描述符

    前端拿到描述符后，在 POST /chat 的 attachments 字段里回传，
    由智能体编排服务注入模型上下文。图片不会被解析（除非配置了视觉模型）。
    """
    content = await file.read()
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"附件过大：{len(content)} 字节，上限 {MAX_ATTACHMENT_BYTES} 字节",
        )
    if not content:
        raise HTTPException(status_code=400, detail="附件内容为空")

    attachment = process_upload(
        file.filename or "upload.bin",
        content,
        file.content_type or "",
    )
    logger.info(
        "Attachment received",
        filename=attachment.filename,
        kind=attachment.kind,
        size=attachment.size,
        chars=attachment.chars,
    )
    return attachment.to_dict()


@app.get("/attachments/limits")
async def attachment_limits():
    """附件限制说明，供前端展示提示文案"""
    return {
        "max_attachment_bytes": MAX_ATTACHMENT_BYTES,
        "max_text_chars_per_file": MAX_TEXT_CHARS,
        "image_understood": False,
        "note": "当前模型不支持图片理解，图片仅接收与保存，不会被解析。",
    }


@app.get("/tools")
async def proxy_tools():
    """转发工具清单到智能体编排服务 (8002)

    返回每个工具的 schema 与是否已暴露给模型自主调用。
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{AGENT_SERVICE_URL}/tools")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.get("/task/{task_id}/status")
async def proxy_task_status(task_id: str):
    """转发任务状态查询到智能体编排服务 (8002)"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{AGENT_SERVICE_URL}/task/{task_id}/status")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
