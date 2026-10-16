"""模型网关服务 (Model Gateway)

提供 OpenAI 兼容的 /v1/chat/completions 接口。
统一管理多模型路由、Token 统计、流式输出。
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from services.model_gateway.router import ModelRouter, ModelRouteRequest
from services.model_gateway.token_tracker import TokenTracker
from shared.utils.config import get_settings
from shared.utils.logging import get_logger, setup_logging, set_trace_id

logger = get_logger(__name__)
settings = get_settings()

# 全局组件
model_router: ModelRouter | None = None
token_tracker: TokenTracker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    global model_router, token_tracker
    setup_logging(level="DEBUG" if settings.APP_DEBUG else "INFO")
    logger.info("Model Gateway starting...")

    model_router = ModelRouter(settings)
    await model_router.initialize()

    token_tracker = TokenTracker()

    logger.info("Model Gateway started", port=settings.MODEL_GATEWAY_PORT)
    yield

    logger.info("Model Gateway shutting down...")
    if model_router:
        await model_router.close()


app = FastAPI(
    title="GrassSea Model Gateway",
    version="0.1.0",
    lifespan=lifespan,
)


# ---- 请求/响应模型 ----

class ChatMessage(BaseModel):
    """OpenAI 风格消息

    扩展字段用于 function calling 往返：
    - assistant 返回 tool_calls 时 content 可为空
    - role="tool" 的消息需带 tool_call_id 指回是哪次调用
    """
    role: str = "user"
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    tool_call_id: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str = "deepseek-chat"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    user: Optional[str] = None
    # --- function calling ---
    tools: Optional[list[dict]] = None
    tool_choice: Optional[str] = None


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatUsage


# ---- 端点 ----

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "model-gateway",
        "version": settings.APP_VERSION,
    }


@app.get("/version")
async def version():
    """版本信息"""
    return {
        "service": "model-gateway",
        "version": settings.APP_VERSION,
        "supported_models": list(model_router.model_map.keys()) if model_router else [],
    }


@app.get("/admin/models")
async def list_models():
    """查看当前已注册的模型及其状态"""
    if not model_router:
        return {"models": [], "message": "Model router not initialized"}
    models = []
    for name, config in model_router.model_map.items():
        models.append({
            "name": name,
            "provider": config["provider"],
            "has_key": bool(config.get("api_key")),
            "base_url": config.get("base_url", ""),
        })
    return {
        "models": models,
        "count": len(models),
    }


@app.post("/admin/reload")
async def reload_config(config: dict[str, str]):
    """运行时重载模型配置，无需重启容器。

    接受部分更新：{"DEEPSEEK_API_KEY": "sk-xxx", "CLAUDE_API_KEY": "sk-xxx", ...}

    会重新初始化模型路由器，使新 API Key 立即生效。
    """
    global model_router

    updated_keys = []
    for key, value in config.items():
        if hasattr(settings, key):
            old_value = getattr(settings, key, "")
            setattr(settings, key, value)
            os.environ[key] = value
            if old_value != value:
                updated_keys.append(key)
            logger.info("Config reloaded", key=key, changed=(old_value != value))

    if not updated_keys:
        return {
            "status": "ok",
            "models": list(model_router.model_map.keys()) if model_router else [],
            "message": "No changes detected",
        }

    # 重新初始化模型路由器
    if model_router:
        await model_router.close()

    model_router = ModelRouter(settings)
    await model_router.initialize()

    new_models = list(model_router.model_map.keys())
    logger.info("Model router reloaded", models=new_models)

    return {
        "status": "ok",
        "models": new_models,
        "message": f"配置已更新，模型已重载: {new_models}",
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, http_request: Request):
    """OpenAI 兼容的 Chat Completions 接口

    支持流式 (SSE) 和非流式输出。
    """
    trace_id = str(uuid.uuid4())[:8]
    set_trace_id(trace_id)

    start_time = time.time()

    # 模型路由
    route_request = ModelRouteRequest(
        model=request.model,
        messages=[m.model_dump() for m in request.messages],
        task_type="simple_chat",
    )

    try:
        route_result = await model_router.route(route_request)
    except ValueError as e:
        logger.error("Model routing failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        "Chat request",
        model=route_result.model,
        stream=request.stream,
        trace_id=trace_id,
    )

    if request.stream:
        return StreamingResponse(
            _stream_response(request, route_result, trace_id, start_time),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Trace-Id": trace_id,
            },
        )
    else:
        return await _sync_response(request, route_result, trace_id, start_time)


async def _sync_response(
    request: ChatCompletionRequest,
    route_result,
    trace_id: str,
    start_time: float,
) -> ChatCompletionResponse:
    """非流式响应（透传真实消息与工具定义）"""
    try:
        completion = await model_router.complete(
            route_result,
            stream=False,
            messages=[m.model_dump(exclude_none=True) for m in request.messages],
            tools=request.tools,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        content = completion.get("content", "")
        tool_calls = completion.get("tool_calls") or []
        finish_reason = completion.get("finish_reason") or ("tool_calls" if tool_calls else "stop")
    except Exception as e:
        logger.error("LLM call failed", error=str(e))
        raise HTTPException(status_code=502, detail=f"LLM service error: {str(e)}")

    elapsed_ms = (time.time() - start_time) * 1000

    # Token 统计
    prompt_tokens = completion.get("prompt_tokens", 0)
    completion_tokens = completion.get("completion_tokens", 0)

    if token_tracker:
        await token_tracker.record(
            user_id=request.user or "anonymous",
            session_id=trace_id,
            model=route_result.model,
            task_type=route_result.task_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=elapsed_ms,
        )

    return ChatCompletionResponse(
        id=f"chatcmpl-{trace_id}",
        created=int(time.time()),
        model=route_result.model,
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(
                    role="assistant",
                    content=content or None,
                    tool_calls=tool_calls or None,
                ),
                finish_reason=finish_reason,
            )
        ],
        usage=ChatUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


async def _stream_response(
    request: ChatCompletionRequest,
    route_result,
    trace_id: str,
    start_time: float,
):
    """流式响应生成器 (SSE)"""
    try:
        async for chunk in model_router.complete_stream(
            route_result,
            messages=[m.model_dump(exclude_none=True) for m in request.messages],
        ):
            content = chunk.get("content", "")
            if content:
                data = {
                    "id": f"chatcmpl-{trace_id}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": route_result.model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": content},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {__import__('json').dumps(data)}\n\n"

        # 最终帧
        elapsed_ms = (time.time() - start_time) * 1000

        # 记录 Token 统计
        if token_tracker:
            await token_tracker.record(
                user_id=request.user or "anonymous",
                session_id=trace_id,
                model=route_result.model,
                task_type=route_result.task_type,
                prompt_tokens=route_result.prompt_tokens or 0,
                completion_tokens=route_result.completion_tokens or 0,
                latency_ms=elapsed_ms,
            )

        final_data = {
            "id": f"chatcmpl-{trace_id}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": route_result.model,
            "choices": [
                {"index": 0, "delta": {}, "finish_reason": "stop"}
            ],
        }
        yield f"data: {__import__('json').dumps(final_data)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error("Streaming error", error=str(e))
        error_data = {"error": {"message": str(e), "type": "stream_error"}}
        yield f"data: {__import__('json').dumps(error_data)}\n\n"
        yield "data: [DONE]\n\n"
