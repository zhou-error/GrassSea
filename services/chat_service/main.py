"""对话服务 (Chat Service) — 前端 API 网关，提供路由转发到各后端服务。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx

import asyncio
import os

from services.chat_service.attachments import MAX_TEXT_CHARS, process_upload
from shared.utils import workspace as ws
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


# ============================================================
# 桌面模式：工作文件夹
# 仅在 DESKTOP_MODE=true（app.launcher --desktop）时可用。
# 工作文件夹状态保存在 shared.utils.workspace 模块级变量中，
# 桌面模式下四个服务同进程，因此 chat_service 设置后 agent_service 的工具能直接读到。
# ============================================================


def _require_desktop() -> None:
    if not settings.DESKTOP_MODE:
        raise HTTPException(
            status_code=403,
            detail="工作文件夹功能仅在桌面模式下可用（请用 app.launcher --desktop 启动）",
        )


@app.get("/desktop/status")
async def desktop_status():
    """桌面模式状态"""
    root = ws.get_root()
    return {
        "desktop_mode": settings.DESKTOP_MODE,
        "workspace_selected": root is not None,
        "workspace_root": str(root) if root else "",
    }


@app.get("/workspace")
async def workspace_info():
    """当前工作文件夹与目录树摘要"""
    _require_desktop()
    root = ws.get_root()
    if root is None:
        return {"selected": False, "root": "", "tree": [], "truncated": False}
    info = ws.tree(max_depth=2, max_entries=200)
    return {"selected": True, "root": info["root"], "tree": info["lines"], "truncated": info["truncated"]}


@app.get("/workspace/list")
async def workspace_list(path: str = ""):
    """列出工作文件夹中的目录（只列一层）"""
    _require_desktop()
    try:
        return ws.list_dir(path)
    except ws.WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/workspace/set")
async def workspace_set(payload: dict):
    """直接设置工作文件夹（手动输入路径或前端传入选中的路径）"""
    _require_desktop()
    path = str((payload or {}).get("path") or "")
    try:
        root = ws.set_root(path)
    except ws.WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    info = ws.tree(max_depth=2, max_entries=200)
    return {"selected": True, "root": str(root), "tree": info["lines"], "truncated": info["truncated"]}


@app.post("/workspace/select")
async def workspace_select():
    """弹出系统原生文件夹选择对话框

    tkinter 的对话框是阻塞调用，放到线程中执行以免卡住事件循环。
    """
    _require_desktop()

    def _pick() -> str:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:  # noqa: BLE001
            pass
        try:
            chosen = filedialog.askdirectory(title="选择 GrassSea 工作文件夹")
        finally:
            root.destroy()
        return chosen or ""

    try:
        chosen = await asyncio.to_thread(_pick)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"无法打开文件夹对话框：{exc}") from exc

    if not chosen:
        return {"selected": False, "root": "", "tree": [], "truncated": False, "cancelled": True}

    try:
        root = ws.set_root(chosen)
    except ws.WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    info = ws.tree(max_depth=2, max_entries=200)
    return {"selected": True, "root": str(root), "tree": info["lines"], "truncated": info["truncated"]}


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
