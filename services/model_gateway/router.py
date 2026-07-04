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

    async def complete(
        self, route: ModelRouteResult, stream: bool = False
    ) -> dict:
        """非流式调用 LLM"""
        if route.provider == "deepseek":
            return await self._call_deepseek(route, stream=False)
        elif route.provider == "anthropic":
            return await self._call_claude(route, stream=False)
        else:
            raise ValueError(f"Unknown provider: {route.provider}")

    async def complete_stream(
        self, route: ModelRouteResult
    ) -> AsyncIterator[dict]:
        """流式调用 LLM"""
        if route.provider == "deepseek":
            async for chunk in self._call_deepseek_stream(route):
                yield chunk
        elif route.provider == "anthropic":
            async for chunk in self._call_claude_stream(route):
                yield chunk
        else:
            raise ValueError(f"Unknown provider: {route.provider}")

    async def _call_deepseek(
        self, route: ModelRouteResult, stream: bool = False
    ) -> dict:
        """调用 DeepSeek API (OpenAI 兼容)"""
        url = f"{route.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {route.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": route.model,
            "messages": [{"role": "user", "content": "ping"}],  # 占位
            "stream": stream,
        }

        response = await self._http_client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]

        return {
            "content": choice["message"]["content"],
            "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
            "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
        }

    async def _call_deepseek_stream(
        self, route: ModelRouteResult
    ) -> AsyncIterator[dict]:
        """DeepSeek 流式调用"""
        url = f"{route.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {route.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": route.model,
            "messages": [{"role": "user", "content": "ping"}],
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

    async def _call_claude(
        self, route: ModelRouteResult, stream: bool = False
    ) -> dict:
        """调用 Claude API (Anthropic)"""
        url = f"{route.base_url}/v1/messages"
        headers = {
            "x-api-key": route.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": route.model.replace("claude-", "claude-"),
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": "ping"}],
        }

        response = await self._http_client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        content_blocks = data.get("content", [{}])
        text = "".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        )

        return {
            "content": text,
            "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
            "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
        }

    async def _call_claude_stream(
        self, route: ModelRouteResult
    ) -> AsyncIterator[dict]:
        """Claude 流式调用"""
        url = f"{route.base_url}/v1/messages"
        headers = {
            "x-api-key": route.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": route.model.replace("claude-", "claude-"),
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": "ping"}],
            "stream": True,
        }

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
