"""对话服务 (Chat Service) — 前端 API 网关，提供路由转发到各后端服务。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx

import asyncio
import os
from pathlib import Path

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


@app.middleware("http")
async def _strip_api_prefix(request: Request, call_next):
    """桌面模式下剥离 /api 前缀

    Docker 形态由 nginx 去掉 /api 再转发；桌面模式没有 nginx，
    前端仍以 /api 为前缀调用，因此这里补上同样的处理。
    """
    if settings.DESKTOP_MODE and request.scope.get("path", "").startswith("/api/"):
        request.scope["path"] = request.scope["path"][4:]
        raw = request.scope.get("raw_path")
        if raw:
            request.scope["raw_path"] = raw[4:]
    return await call_next(request)


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


@app.get("/doc/status")
async def doc_status():
    """Word/PDF 文档能力状态：转换引擎、模板路径、输出目录"""
    from shared.utils.docx_render import template_paths
    from shared.utils.pdf_convert import available_converters
    from tools.doc._common import output_root

    name = (getattr(settings, "DOC_DEFAULT_TEMPLATE", "") or "report").strip() or "report"
    paths = template_paths(name)
    try:
        out_dir = str(output_root())
    except Exception:  # noqa: BLE001
        out_dir = ""
    return {
        "pdf_converter": (getattr(settings, "PDF_CONVERTER", "auto") or "auto"),
        "converters": available_converters(),
        "template": paths,
        "output_dir": out_dir,
        "desktop_mode": settings.DESKTOP_MODE,
    }


@app.post("/doc/open-folder")
async def doc_open_folder(payload: dict):
    """在系统文件管理器中打开模板目录（仅桌面模式）"""
    _require_desktop()
    import os
    import subprocess
    import sys

    from shared.utils.docx_render import template_paths

    target = str((payload or {}).get("path") or "").strip()
    if not target:
        name = (getattr(settings, "DOC_DEFAULT_TEMPLATE", "") or "report").strip() or "report"
        target = template_paths(name)["base_dir"]
    folder = Path(target)
    if not folder.exists():
        raise HTTPException(status_code=404, detail=f"目录不存在：{target}")
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(folder))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"无法打开目录：{exc}") from exc
    return {"status": "ok", "path": str(folder)}


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


# ============================================================
# 前端静态托管（桌面模式）
# Docker 形态下前端由 nginx 托管，这里只是为了 app.launcher --desktop 时
# 能在同一端口上同时提供界面与 API。必须放在所有 API 路由之后注册。
# ============================================================
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if (_FRONTEND_DIST / "index.html").exists():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    _ASSETS = _FRONTEND_DIST / "assets"
    if _ASSETS.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_ASSETS)), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """SPA 前端路由回退：静态文件命中则返回，否则一律回到 index.html"""
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_FRONTEND_DIST / "index.html"))

    logger.info("前端静态资源已挂载", dist=str(_FRONTEND_DIST))
else:
    logger.info("未发现前端构建产物（frontend/dist），仅提供 API")
