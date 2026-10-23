"""LLM 端口

对应实现：services/model_gateway（远端 API）。未来接本地推理（如 DeepInfer、
vLLM、Ollama）时实现同一端口即可，上层工具循环无需改动。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ToolCall:
    """模型请求调用的一次工具"""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class Completion:
    """一次补全结果

    契约：
    - content 与 tool_calls 至少有一个非空；
    - tool_calls 非空时，content 允许为空字符串；
    - usage 可能缺失（供应商差异），不得据此做逻辑判断。
    """

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMPort(Protocol):
    """模型调用契约

    实现方必须保证：
    1. tools 以 OpenAI function-calling 格式透传（含 name/description/parameters）；
    2. 上游失败时抛异常或返回带 code 的错误，**不得**返回伪造 content；
    3. 支持 tools=None 的纯文本调用（收尾阶段用）。
    """

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Completion:
        ...
