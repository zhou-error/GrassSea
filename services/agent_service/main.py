"""智能体编排服务 (Agent Orchestration Service)

提供:
  - 智能体注册中心
  - 任务编排 API (/chat, /task/{id}/status)
  - WebSocket 进度推送
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from services.agent_service.intent import IntentClassifier, IntentType
from services.agent_service.planner import TaskPlanner
from services.agent_service.fsm import SessionFSM, SessionState
from services.agent_service.registry import AgentRegistry
from services.agent_service.executor import TaskExecutor
from shared.utils.config import get_settings
from shared.utils.logging import get_logger, setup_logging, set_trace_id
from tools.base.registry import ToolRegistry
from tools.bootstrap import build_tool_registry

logger = get_logger(__name__)
settings = get_settings()

intent_classifier: IntentClassifier | None = None
task_planner: TaskPlanner | None = None
agent_registry: AgentRegistry | None = None
tool_registry: ToolRegistry | None = None
task_executor: TaskExecutor | None = None
active_connections: dict[str, WebSocket] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global intent_classifier, task_planner, agent_registry, tool_registry, task_executor
    setup_logging(level="DEBUG" if settings.APP_DEBUG else "INFO")
    logger.info("Agent Service starting...")

    intent_classifier = IntentClassifier(settings)
    task_planner = TaskPlanner(settings)
    agent_registry = AgentRegistry()
    tool_registry = await build_tool_registry()
    task_executor = TaskExecutor(settings, agent_registry, tool_registry)

    await agent_registry.initialize()
    await intent_classifier.initialize()

    registered_tools = await tool_registry.list_tools()
    logger.info(
        "Agent Service started",
        port=settings.AGENT_SERVICE_PORT,
        registered_tools=len(registered_tools),
    )
    yield
    logger.info("Agent Service shutting down...")


app = FastAPI(title="GrassSea Agent Orchestration Service", version="0.1.0", lifespan=lifespan)


# ==== 请求/响应模型 ====

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    attachments: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session_id: str
    intent: str
    answer: str
    task_id: Optional[str] = None
    sources: list = Field(default_factory=list)


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: float = 0.0
    result: Optional[dict] = None
    error: Optional[str] = None
    steps: list = Field(default_factory=list)


# ==== 端点 ====

@app.get("/health")
async def health():
    agents = await agent_registry.list_agents() if agent_registry else []
    tools = await tool_registry.list_tools() if tool_registry else []
    return {
        "status": "healthy", "service": "agent-service",
        "version": settings.APP_VERSION,
        "registered_agents": len(agents),
        "registered_tools": len(tools),
    }


@app.get("/tasks")
async def list_tasks():
    """列出内存中的任务（最新在前）"""
    tasks = await task_executor.list_tasks() if task_executor else []
    return {"total": len(tasks), "tasks": tasks}


@app.get("/agents")
async def list_agents():
    """列出已注册智能体"""
    agents = await agent_registry.list_agents() if agent_registry else []
    return {"total": len(agents), "agents": agents}


@app.get("/admin/status")
async def admin_status():
    """查看当前配置状态"""
    return {
        "service": "agent-service",
        "deepseek_configured": bool(settings.DEEPSEEK_API_KEY),
        "claude_configured": bool(settings.CLAUDE_API_KEY),
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "model_gateway_url": getattr(settings, "MODEL_GATEWAY_URL", ""),
    }


@app.post("/admin/reload")
async def reload_config(config: dict[str, str]):
    """运行时重载配置，无需重启容器。

    接受部分更新：{"DEEPSEEK_API_KEY": "sk-xxx", ...}
    会重新初始化意图分类器和任务规划器。
    """
    global intent_classifier, task_planner

    updated = False
    for key, value in config.items():
        if hasattr(settings, key):
            old_value = getattr(settings, key, "")
            setattr(settings, key, value)
            os.environ[key] = value
            if old_value != value:
                updated = True
            logger.info("Agent config reloaded", key=key, changed=(old_value != value))

    if updated:
        intent_classifier = IntentClassifier(settings)
        await intent_classifier.initialize()
        task_planner = TaskPlanner(settings)
        logger.info("Agent intent classifier & planner re-initialized")

    return {
        "status": "ok",
        "deepseek_configured": bool(settings.DEEPSEEK_API_KEY),
        "claude_configured": bool(settings.CLAUDE_API_KEY),
        "message": "配置已更新" if updated else "无变化",
    }


# 意图 -> 中文名称
_INTENT_LABELS = {
    "chitchat": "闲聊",
    "knowledge_query": "知识查询",
    "tool_call": "工具调用",
    "professional_task": "专业任务",
    "sub_agent_orchestration": "多智能体协同",
}


def _describe_plan(task: dict) -> str:
    """把执行计划渲染成可读的多行文本"""
    steps = task.get("steps") or []
    if not steps:
        return "（无可执行步骤）"
    lines = []
    for idx, step in enumerate(steps, 1):
        desc = step.get("description") or step.get("action") or ""
        deps = step.get("dependencies") or []
        suffix = ("（依赖 " + "、".join(deps) + "）") if deps else ""
        lines.append(f"  {idx}. {desc}{suffix}")
    return "\n".join(lines)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """对话入口 — 意图识别 → 路由 → 执行"""
    trace_id = str(uuid.uuid4())[:8]
    set_trace_id(trace_id)
    session_id = request.session_id or f"sess_{trace_id}"

    # 1. 意图识别
    intent_result = await intent_classifier.classify(request.message)
    logger.info("Intent classified", intent=intent_result.intent_type, confidence=intent_result.confidence, session=session_id)

    # 2. 按意图路由
    if intent_result.intent_type == IntentType.CHITCHAT:
        answer = await _handle_chitchat(request.message)
        return ChatResponse(session_id=session_id, intent="chitchat", answer=answer)

    elif intent_result.intent_type == IntentType.KNOWLEDGE_QUERY:
        result = await _handle_knowledge_query(request.message, session_id)
        return ChatResponse(session_id=session_id, intent="knowledge_query", answer=result["answer"], sources=result.get("sources", []))

    elif intent_result.intent_type in (IntentType.TOOL_CALL, IntentType.PROFESSIONAL_TASK):
        # 任务规划
        task = await task_planner.plan(request.message, intent_result)
        # 异步执行
        await task_executor.execute_async(task, session_id, request.user_id)
        intent_label = _INTENT_LABELS.get(
            intent_result.intent_type.value, intent_result.intent_type.value
        )
        return ChatResponse(
            session_id=session_id,
            intent=intent_result.intent_type,
            answer=(
                f"已创建{intent_label} {task['task_id']}\n"
                f"执行计划共 {len(task.get('steps', []))} 步：\n"
                f"{_describe_plan(task)}\n\n"
                "正在执行，进度会实时刷新；完成后会给出各步结果。"
            ),
            task_id=task["task_id"],
        )

    elif intent_result.intent_type == IntentType.SUB_AGENT_ORCHESTRATION:
        task = await task_planner.plan_multi_agent(request.message, intent_result)
        await task_executor.execute_async(task, session_id, request.user_id)
        return ChatResponse(
            session_id=session_id,
            intent="sub_agent_orchestration",
            answer=(
                f"已创建多智能体协同任务 {task['task_id']}\n"
                f"执行计划共 {len(task.get('steps', []))} 步：\n"
                f"{_describe_plan(task)}\n\n"
                "正在执行，进度会实时刷新；完成后会给出各步结果。"
            ),
            task_id=task["task_id"],
        )

    # 兜底
    answer = await _handle_chitchat(request.message)
    return ChatResponse(session_id=session_id, intent="unknown", answer=answer)


@app.get("/task/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """查询任务状态"""
    status = await task_executor.get_status(task_id) if task_executor else None
    if status is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(**status)


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket 连接 — 实时推送任务进度和流式输出"""
    await websocket.accept()
    active_connections[session_id] = websocket
    logger.info("WebSocket connected", session_id=session_id)
    try:
        while True:
            data = await websocket.receive_text()
            # 处理客户端消息（如取消任务）
            import json
            msg = json.loads(data)
            if msg.get("action") == "cancel":
                await task_executor.cancel_task(msg.get("task_id"))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", session_id=session_id)
    finally:
        active_connections.pop(session_id, None)


# ==== 内部处理函数 ====

async def _handle_chitchat(message: str) -> str:
    """处理闲聊 — 直接调用 LLM"""
    import httpx
    if not settings.DEEPSEEK_API_KEY:
        return "您好！我是 GrassSea AI 助手，专注于船舶与海洋工程领域。请问有什么可以帮助您的？"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": message}], "max_tokens": 1024},
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _handle_knowledge_query(message: str, session_id: str) -> dict:
    """处理知识查询 — 调用 RAG 引擎"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.KNOWLEDGE_SERVICE_URL}/rag/query",
                json={"query": message, "top_k": 5},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {"answer": data["answer"], "sources": data.get("sources", [])}
    except Exception as e:
        logger.error("RAG query failed", error=str(e))
    return {"answer": "知识库服务暂时不可用，请稍后重试。", "sources": []}
