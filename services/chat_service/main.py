"""对话服务 (Chat Service) — 前端 API 网关

提供认证 + 路由转发到各后端服务。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx

from services.chat_service.auth import router as auth_router
from services.chat_service.config_api import router as config_router
from shared.utils.config import get_settings
from shared.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(level="DEBUG" if settings.APP_DEBUG else "INFO")
    logger.info("Chat Service starting...")
    yield


app = FastAPI(title="GrassSea Chat Service", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册认证路由
app.include_router(auth_router)
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
            f"http://localhost:8002/chat", json=body,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.post("/rag/query")
async def proxy_rag_query(request: Request):
    """转发 RAG 查询到知识库服务 (8003)"""
    body = await request.json()
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"http://localhost:8003/rag/query", json=body,
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
            f"http://localhost:8003/rag/documents",
            data=data, files=files,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.get("/task/{task_id}/status")
async def proxy_task_status(task_id: str):
    """转发任务状态查询到智能体编排服务 (8002)"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"http://localhost:8002/task/{task_id}/status")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
