"""智能体基础协议定义

严格遵循《项目框架设计文档》2.3.2 节的接口规范。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Protocol


class AgentStatus(str, Enum):
    """智能体状态"""
    UNREGISTERED = "unregistered"
    REGISTERED = "registered"
    IDLE = "idle"
    WORKING = "working"
    UNHEALTHY = "unhealthy"
    DESTROYED = "destroyed"


@dataclass
class AgentCapability:
    """能力声明"""
    name: str                              # 能力名称
    description: str                       # 能力描述
    input_schema: dict                     # 输入 JSON Schema
    output_schema: dict                    # 输出 JSON Schema
    tools: list[str] = field(default_factory=list)  # 关联工具 ID 列表
    estimated_latency_ms: int = 500        # 预估延迟（毫秒）


@dataclass
class AgentMetadata:
    """智能体元信息"""
    agent_id: str                          # 唯一标识
    name: str                              # 显示名称
    role: str                              # 角色描述
    capabilities: list[AgentCapability] = field(default_factory=list)
    model_preference: str = "deepseek-chat"  # 偏好的 LLM 模型
    max_concurrent_tasks: int = 5          # 最大并发任务数
    version: str = "0.1.0"                 # 版本号


@dataclass
class AgentCallbacks:
    """智能体回调接口"""
    on_progress: Any = None   # 进度回调 (task_id, progress)
    on_message: Any = None    # 消息推送回调 (task_id, message)
    on_error: Any = None      # 错误回调 (task_id, error)


class BaseAgent(ABC):
    """智能体抽象基类

    每个业务智能体需继承此类，实现 handle_task 方法。
    """

    def __init__(self, metadata: AgentMetadata):
        self._metadata = metadata
        self._status = AgentStatus.UNREGISTERED

    @property
    def metadata(self) -> AgentMetadata:
        """返回智能体元信息"""
        return self._metadata

    @property
    def status(self) -> AgentStatus:
        """返回当前状态"""
        return self._status

    @abstractmethod
    async def handle_task(
        self,
        task: dict[str, Any],          # 任务描述（标准化格式）
        context: dict[str, Any],       # 上下文信息
        callbacks: AgentCallbacks,     # 回调接口
    ) -> dict[str, Any]:
        """执行任务并返回结果"""
        ...

    async def health_check(self) -> bool:
        """健康检查"""
        return True

    def set_status(self, status: AgentStatus) -> None:
        """更新状态"""
        self._status = status


# Agent 注册中心接口
class AgentRegistry(Protocol):
    """智能体注册中心协议"""

    async def register(self, agent: BaseAgent) -> bool:
        """注册智能体"""
        ...

    async def deregister(self, agent_id: str) -> bool:
        """注销智能体"""
        ...

    async def discover(self, capability: str) -> list[AgentMetadata]:
        """按能力发现智能体"""
        ...

    async def heartbeat(self, agent_id: str) -> bool:
        """心跳上报"""
        ...

    async def get_agent(self, agent_id: str) -> AgentMetadata | None:
        """获取智能体信息"""
        ...
