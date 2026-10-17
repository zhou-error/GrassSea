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
from services.agent_service.tool_loop import ToolCallLoop
from services.chat_service.attachments import build_context
from shared.utils.config import coerce_setting, get_settings
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
tool_call_loop: ToolCallLoop | None = None
active_connections: dict[str, WebSocket] = {}


async def _validate_registration_consistency(agent_registry, registered_tools, exposed_tools) -> None:
    """校验 planner / 工具白名单 与注册表是否一致，不一致只告警不阻断

    这是「重命名后静默失效」的唯一防线：planner 用字面量引用 agent_id 与 tool_id，
    一旦注册表里没有对应项，任务会安静地被标成 skipped，用户与开发者都难以定位。
    """
    try:
        agents = await agent_registry.list_agents()
    except Exception:  # noqa: BLE001
        agents = []
    registered_agent_ids = {a.get("agent_id") for a in agents}
    registered_tool_ids = {m.tool_id for m in registered_tools}
    exposed_ids = {m.tool_id for m in exposed_tools}

    problems: list[str] = []

    # planner 的能力路由
    for _keywords, agent_id, action in getattr(TaskPlanner, "AGENT_ROUTES", []):
        if registered_agent_ids and agent_id not in registered_agent_ids:
            problems.append(f"planner.AGENT_ROUTES 引用了未注册的 agent: {agent_id}")

    for action, tool_id in getattr(TaskPlanner, "TOOL_FOR_ACTION", {}).items():
        if tool_id not in registered_tool_ids:
            problems.append(f"planner.TOOL_FOR_ACTION 引用了未注册的工具: {tool_id}（action={action}）")

    for tool_id in getattr(TaskPlanner, "IMPLEMENTED_TOOLS", set()):
        if tool_id not in registered_tool_ids:
            problems.append(f"planner.IMPLEMENTED_TOOLS 引用了未注册的工具: {tool_id}")

    # 模型可见白名单
    for tool_id in sorted(exposed_ids):
        if tool_id not in registered_tool_ids:
            problems.append(f"MODEL_EXPOSED_TOOLS 引用了未注册的工具: {tool_id}")

    if problems:
        for p in problems:
            logger.error("启动一致性校验失败", problem=p)
        print("\n[警告] 启动一致性校验发现问题（详见日志）：", flush=True)
        for p in problems:
            print(f"  - {p}", flush=True)
        print("", flush=True)
    else:
        logger.info(
            "启动一致性校验通过",
            agents=len(registered_agent_ids),
            tools=len(registered_tool_ids),
            exposed=len(exposed_ids),
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global intent_classifier, task_planner, agent_registry, tool_registry, task_executor, tool_call_loop
    setup_logging(level="DEBUG" if settings.APP_DEBUG else "INFO")
    logger.info("Agent Service starting...")

    intent_classifier = IntentClassifier(settings)
    task_planner = TaskPlanner(settings)
    agent_registry = AgentRegistry()
    tool_registry = await build_tool_registry()
    task_executor = TaskExecutor(settings, agent_registry, tool_registry)
    # 模型自主工具调用循环（需要 tool_registry 已就绪）
    tool_call_loop = ToolCallLoop(settings, tool_registry)

    await agent_registry.initialize()
    await intent_classifier.initialize()

    registered_tools = await tool_registry.list_tools()
    exposed_tools = await tool_call_loop.list_exposed_tools()

    # ---- 启动一致性校验 ----
    # planner 里的 agent_id / tool_id 全是字面量；重命名后只会表现为运行时静默 skipped，
    # 桌面形态又没有监控兜底，因此必须在启动时把不一致喊出来。
    await _validate_registration_consistency(agent_registry, registered_tools, exposed_tools)
    logger.info(
        "Agent Service started",
        port=settings.AGENT_SERVICE_PORT,
        registered_tools=len(registered_tools),
        tool_calling_enabled=settings.TOOL_CALLING_ENABLED,
        exposed_to_model=len(exposed_tools),
    )
    yield
    logger.info("Agent Service shutting down...")


app = FastAPI(title="GrassSea Agent Orchestration Service", version="0.1.0", lifespan=lifespan)


# ==== 请求/响应模型 ====

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    # 附件描述符列表（来自 chat_service 的 POST /attachments）
    # 结构：{attachment_id, filename, media_type, size, kind, chars, text, truncated, note}
    attachments: list[dict] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session_id: str
    intent: str
    answer: str
    task_id: Optional[str] = None
    sources: list = Field(default_factory=list)
    # 模型自主调用工具时产生的调用轨迹（供前端展示"调用了什么、结果如何"）
    tool_trace: list[dict] = Field(default_factory=list)


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


@app.get("/tools")
async def list_tool_definitions():
    """列出全部工具，并标出哪些已暴露给模型自主调用

    exposed_to_model=true 的工具，模型可以在对话中自行决定调用（function calling）。
    """
    if not tool_registry:
        return {"total": 0, "tools": [], "tool_calling_enabled": False}

    manifests = await tool_registry.list_tools()
    exposed: set[str] = set()
    if tool_call_loop:
        exposed = {m.tool_id for m in await tool_call_loop.list_exposed_tools()}

    tools = [
        {
            "tool_id": m.tool_id,
            "name": m.name,
            "description": m.description,
            "category": m.category.value,
            "input_schema": m.input_schema,
            "output_schema": m.output_schema,
            "timeout_ms": m.timeout_ms,
            "version": m.version,
            "exposed_to_model": m.tool_id in exposed,
        }
        for m in manifests
    ]
    return {
        "total": len(tools),
        "tool_calling_enabled": settings.TOOL_CALLING_ENABLED,
        "exposed_to_model": len(exposed),
        "tools": tools,
    }


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
    rejected: list[str] = []
    for key, value in config.items():
        # 按字段类型转换：否则 {"TOOL_CALLING_ENABLED": "false"} 会被设成
        # 字符串 "false"（真值），开关看起来关了其实没关。
        coerced = coerce_setting(settings, key, value)
        if coerced is None:
            if not hasattr(settings, key):
                rejected.append(key)
            else:
                rejected.append(f"{key}（值无法转换为 {key} 要求的类型）")
            continue
        old_value = getattr(settings, key, "")
        setattr(settings, key, coerced)
        os.environ[key] = str(coerced)
        if old_value != coerced:
            updated = True
        logger.info("Agent config reloaded", key=key, changed=(old_value != coerced), value_type=type(coerced).__name__)
    if rejected:
        logger.warning("部分配置项被拒绝", keys=rejected)

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


def _merge_notes(answer: str, notes: list[str]) -> str:
    """把附件的如实说明追加到回答末尾（不放正文里，避免模型改写或忽略）"""
    if not notes:
        return answer
    lines = "\n".join(f"- {n}" for n in notes)
    return f"{answer}\n\n---\n> ℹ️ 附件说明\n{lines}"


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """对话入口 — 附件注入 → 意图识别 → 路由 → 执行"""
    trace_id = str(uuid.uuid4())[:8]
    set_trace_id(trace_id)
    session_id = request.session_id or f"sess_{trace_id}"

    # 0. 附件注入：把正文拼进消息，并收集需要如实告知用户的说明
    attachment_context, attachment_notes = build_context(request.attachments)
    if attachment_context:
        message = f"{request.message}\n\n===== 附件内容 =====\n{attachment_context}"
        logger.info(
            "Attachments injected",
            count=len(request.attachments),
            context_chars=len(attachment_context),
            notes=len(attachment_notes),
        )
    else:
        message = request.message

    has_attachment_text = any((a.get("text") or "").strip() for a in request.attachments)

    # 1. 意图识别
    intent_result = await intent_classifier.classify(message)
    logger.info("Intent classified", intent=intent_result.intent_type, confidence=intent_result.confidence, session=session_id)

    # 2. 按意图路由
    if intent_result.intent_type == IntentType.CHITCHAT:
        answer = await _handle_chitchat(message)
        return ChatResponse(
            session_id=session_id,
            intent="chitchat",
            answer=_merge_notes(answer, attachment_notes),
        )

    elif intent_result.intent_type == IntentType.KNOWLEDGE_QUERY:
        # 用户附了材料时以附件为准直接作答，不做向量检索
        if has_attachment_text:
            logger.info("Attachments present, answering from attachments", session=session_id)
            answer = await _handle_with_attachments(message)
            return ChatResponse(
                session_id=session_id,
                intent="knowledge_query",
                answer=_merge_notes(answer, attachment_notes),
            )
        result = await _handle_knowledge_query(message, session_id)
        return ChatResponse(
            session_id=session_id,
            intent="knowledge_query",
            answer=_merge_notes(result["answer"], attachment_notes),
            sources=result.get("sources", []),
        )

    elif intent_result.intent_type in (IntentType.TOOL_CALL, IntentType.PROFESSIONAL_TASK):
        # 3.1 优先尝试「模型自主决定调用工具」
        #     模型会拿到工具清单与 JSON Schema，自行选择调用哪个、传什么参数，
        #     结果回灌后给出最终回答；全过程记录在 tool_trace 中。
        loop_result = (
            await tool_call_loop.run(message, session_id, request.user_id)
            if tool_call_loop
            else {"ok": False, "reason": "tool_call_loop_unavailable"}
        )
        if loop_result.get("ok"):
            return ChatResponse(
                session_id=session_id,
                intent=intent_result.intent_type,
                answer=_merge_notes(loop_result.get("answer") or "", attachment_notes),
                tool_trace=loop_result.get("tool_trace") or [],
            )

        # 3.2 回落：规则规划 + DAG 异步执行（保留既有能力，不因模型不可用而失效）
        logger.info(
            "Tool-call loop unavailable, falling back to rule planner",
            reason=loop_result.get("reason"),
            session=session_id,
        )
        task = await task_planner.plan(message, intent_result)
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
        task = await task_planner.plan_multi_agent(message, intent_result)
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
    answer = await _handle_chitchat(message)
    return ChatResponse(
        session_id=session_id,
        intent="unknown",
        answer=_merge_notes(answer, attachment_notes),
    )


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


async def _handle_with_attachments(message: str) -> str:
    """基于用户提供的附件直接作答（不走向量检索）

    用户上传材料时，材料本身就是权威上下文；再去做知识库检索只会得到
    "根据现有资料无法回答"，因此这里直接让模型阅读附件内容作答。
    """
    import httpx

    if not settings.DEEPSEEK_API_KEY:
        return "已收到附件，但当前未配置大模型 API Key，无法解析附件内容。"

    system = (
        "你是 GrassSea AI，专注于船舶与海洋工程领域。"
        "用户提供了附件，请**仅依据附件内容**回答问题，并在引用时注明来自哪个附件。"
        "附件中若没有相关信息，如实说明，不要编造。"
    )
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{settings.DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": message},
                ],
                "max_tokens": 3000,
                "temperature": 0.3,
            },
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
