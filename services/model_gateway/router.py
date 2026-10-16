"""模型路由器

按任务类型 + 成本 + 延迟自动选择最优模型。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

from shared.utils.config import Settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ModelRouteRequest:
    """模型路由请求"""
    model: str = "deepseek-chat"
    messages: list[dict] = field(default_factory=list)
    task_type: str = "simple_chat"
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class ModelRouteResult:
    """模型路由结果"""
    model: str
    provider: str
    api_key: str
    base_url: str
    task_type: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


# 任务类型 → 模型路由表 (主模型, 备选模型)
TASK_MODEL_MAP = {
    "simple_chat": ("deepseek-chat", "claude-haiku"),
    "knowledge_qa": ("deepseek-chat", "claude-sonnet"),
    "complex_reasoning": ("deepseek-reasoner", "claude-opus-4-8"),
    "code_generation": ("deepseek-coder", "claude-sonnet"),
    "intent_classification": ("qwen2.5-7b", "deepseek-chat"),
    "report_generation": ("claude-opus-4-8", "deepseek-reasoner"),
}


class ModelRouter:
    """模型路由管理器"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._http_client: httpx.AsyncClient | None = None
        self.model_map: dict[str, dict[str, str]] = {}

    async def initialize(self) -> None:
        """初始化 HTTP 客户端和模型配置"""
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
        )

        # 配置可用模型
        if self.settings.DEEPSEEK_API_KEY:
            self.model_map["deepseek-chat"] = {
                "provider": "deepseek",
                "api_key": self.settings.DEEPSEEK_API_KEY,
                "base_url": self.settings.DEEPSEEK_BASE_URL.rstrip("/"),
            }
            self.model_map["deepseek-reasoner"] = {
                "provider": "deepseek",
                "api_key": self.settings.DEEPSEEK_API_KEY,
                "base_url": self.settings.DEEPSEEK_BASE_URL.rstrip("/"),
            }
            self.model_map["deepseek-coder"] = {
                "provider": "deepseek",
                "api_key": self.settings.DEEPSEEK_API_KEY,
                "base_url": self.settings.DEEPSEEK_BASE_URL.rstrip("/"),
            }

        if self.settings.CLAUDE_API_KEY:
            self.model_map["claude-haiku"] = {
                "provider": "anthropic",
                "api_key": self.settings.CLAUDE_API_KEY,
                "base_url": self.settings.CLAUDE_BASE_URL.rstrip("/"),
            }
            self.model_map["claude-sonnet"] = {
                "provider": "anthropic",
                "api_key": self.settings.CLAUDE_API_KEY,
                "base_url": self.settings.CLAUDE_BASE_URL.rstrip("/"),
            }
            self.model_map["claude-opus-4-8"] = {
                "provider": "anthropic",
                "api_key": self.settings.CLAUDE_API_KEY,
                "base_url": self.settings.CLAUDE_BASE_URL.rstrip("/"),
            }

        logger.info("Model router initialized", models=list(self.model_map.keys()))

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        if self._http_client:
            await self._http_client.aclose()

    async def route(self, request: ModelRouteRequest) -> ModelRouteResult:
        """路由请求到合适的模型

        规则：
        1. 如果用户指定了 model 且可用，直接使用
        2. 否则按任务类型选择主模型
        3. 主模型不可用时降级到备选
        """
        model_name = request.model

        # 检查用户指定的模型是否可用
        if model_name in self.model_map:
            model_config = self.model_map[model_name]
            return ModelRouteResult(
                model=model_name,
                provider=model_config["provider"],
                api_key=model_config["api_key"],
                base_url=model_config["base_url"],
                task_type=request.task_type,
            )

        # 按任务类型路由
        primary, fallback = TASK_MODEL_MAP.get(
            request.task_type, ("deepseek-chat", "claude-haiku")
        )

        if primary in self.model_map:
            model_config = self.model_map[primary]
            return ModelRouteResult(
                model=primary,
                provider=model_config["provider"],
                api_key=model_config["api_key"],
                base_url=model_config["base_url"],
                task_type=request.task_type,
            )

        if fallback in self.model_map:
            model_config = self.model_map[fallback]
            logger.warning(
                "Model fallback",
                primary=primary,
                fallback=fallback,
                task_type=request.task_type,
            )
            return ModelRouteResult(
                model=fallback,
                provider=model_config["provider"],
                api_key=model_config["api_key"],
                base_url=model_config["base_url"],
                task_type=request.task_type,
            )

        raise ValueError(f"No available model for task '{request.task_type}'")

    # 支持工具调用的 provider（其余 provider 会忽略 tools 参数）
    TOOL_CAPABLE_PROVIDERS = {"deepseek"}

    async def complete(
        self,
        route: ModelRouteResult,
        stream: bool = False,
        messages: list[dict] | None = None,
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """非流式调用 LLM

        messages / tools 由此处透传给上游；tools 为 OpenAI function-calling 格式。
        返回统一字典：content / tool_calls / finish_reason / prompt_tokens / completion_tokens。
        """
        if tools and route.provider not in self.TOOL_CAPABLE_PROVIDERS:
            logger.warning(
                "Provider does not support tool calling, tools ignored",
                provider=route.provider,
            )
            tools = None

        if route.provider == "deepseek":
            return await self._call_deepseek(
                route, stream=False, messages=messages, tools=tools,
                temperature=temperature, max_tokens=max_tokens,
            )
        elif route.provider == "anthropic":
            return await self._call_claude(
                route, stream=False, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
            )
        else:
            raise ValueError(f"Unknown provider: {route.provider}")

    async def complete_stream(
        self,
        route: ModelRouteResult,
        messages: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        """流式调用 LLM"""
        if route.provider == "deepseek":
            async for chunk in self._call_deepseek_stream(route, messages=messages):
                yield chunk
        elif route.provider == "anthropic":
            async for chunk in self._call_claude_stream(route, messages=messages):
                yield chunk
        else:
            raise ValueError(f"Unknown provider: {route.provider}")

    async def _call_deepseek(
        self,
        route: ModelRouteResult,
        stream: bool = False,
        messages: list[dict] | None = None,
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """调用 DeepSeek API (OpenAI 兼容)

        此前该实现写死了 {"role": "user", "content": "ping"} 占位消息，
        真实请求内容从未送达模型。现已改为透传调用方消息。
        tools 为 OpenAI function-calling 格式；上游不支持时自动去掉并重试一次。
        """
        url = f"{route.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {route.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": route.model,
            "messages": messages or [{"role": "user", "content": "ping"}],
            "stream": stream,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        response = await self._http_client.post(url, json=payload, headers=headers)

        # 降级：上游不认识 tools 参数时，去掉后重试一次，保证不破坏基础对话
        if response.status_code >= 400 and "tools" in payload:
            logger.warning(
                "Upstream rejected tools, retrying without them",
                status=response.status_code,
                body=response.text[:200],
            )
            payload.pop("tools", None)
            payload.pop("tool_choice", None)
            response = await self._http_client.post(url, json=payload, headers=headers)

        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        message = choice.get("message") or {}

        return {
            "content": message.get("content") or "",
            "tool_calls": message.get("tool_calls") or [],
            "finish_reason": choice.get("finish_reason", "stop"),
            "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
            "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
        }

    async def _call_deepseek_stream(
        self, route: ModelRouteResult, messages: list[dict] | None = None
    ) -> AsyncIterator[dict]:
        """DeepSeek 流式调用（同样透传真实消息）"""
        url = f"{route.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {route.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": route.model,
            "messages": messages or [{"role": "user", "content": "ping"}],
            "stream": True,
        }

        async with self._http_client.stream(
            "POST", url, json=payload, headers=headers
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    import json
                    data = json.loads(data_str)
                    choice = data.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    yield {"content": delta.get("content", "")}

    @staticmethod
    def _to_anthropic_messages(messages: list[dict] | None) -> tuple[str, list[dict]]:
        """把 OpenAI 风格消息转成 Anthropic 格式

        Anthropic 要求 system 独立成参数，且 messages 只含 user/assistant。
        这里做最小可用转换：抽取 system，其余按角色映射，忽略 tool 消息。
        """
        if not messages:
            return "", [{"role": "user", "content": "ping"}]
        system_parts: list[str] = []
        converted: list[dict] = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content") or ""
            if role == "system":
                system_parts.append(content)
            elif role in ("user", "assistant"):
                converted.append({"role": role, "content": content})
            elif role == "tool":
                # 工具结果以 user 消息形式回灌，保证上下文不丢
                converted.append({"role": "user", "content": f"[工具返回] {content}"})
        if not converted:
            converted = [{"role": "user", "content": "ping"}]
        return "\n\n".join(system_parts), converted

    async def _call_claude(
        self,
        route: ModelRouteResult,
        stream: bool = False,
        messages: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """调用 Claude API (Anthropic)

        注意：Anthropic 分支当前不支持 tools（工具调用仅 deepseek provider 可用），
        调用方 complete() 已在入口处剥离 tools 并告警。
        """
        url = f"{route.base_url}/v1/messages"
        headers = {
            "x-api-key": route.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        system_prompt, anthropic_messages = self._to_anthropic_messages(messages)
        payload = {
            "model": route.model,
            "max_tokens": max_tokens or 4096,
            "messages": anthropic_messages,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if temperature is not None:
            payload["temperature"] = temperature

        response = await self._http_client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        content_blocks = data.get("content", [{}])
        text = "".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        )

        return {
            "content": text,
            "tool_calls": [],
            "finish_reason": data.get("stop_reason", "stop"),
            "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
            "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
        }

    async def _call_claude_stream(
        self, route: ModelRouteResult, messages: list[dict] | None = None
    ) -> AsyncIterator[dict]:
        """Claude 流式调用"""
        url = f"{route.base_url}/v1/messages"
        headers = {
            "x-api-key": route.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        system_prompt, anthropic_messages = self._to_anthropic_messages(messages)
        payload = {
            "model": route.model,
            "max_tokens": 4096,
            "messages": anthropic_messages,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with self._http_client.stream(
            "POST", url, json=payload, headers=headers
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    import json
                    data = json.loads(data_str)
                    if data.get("type") == "content_block_delta":
                        delta = data.get("delta", {})
                        yield {"content": delta.get("text", "")}
