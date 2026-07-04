"""工具基础协议定义

严格遵循《项目框架设计文档》2.4.5 节的统一工具接口规范。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolCategory(str, Enum):
    COMPLIANCE = "compliance"        # 合规审查
    CAD = "cad"                      # CAD 操作
    COMPUTATION = "computation"      # 数值计算
    REPORT = "report"                # 报告生成
    FILE = "file"                    # 文件处理
    SEARCH = "search"                # 检索
    EXTERNAL = "external"            # 外部集成


class ToolStatus(str, Enum):
    DEVELOPING = "developing"        # 开发中
    REGISTERED = "registered"        # 已注册
    ONLINE = "online"                # 在线可用
    DEGRADED = "degraded"           # 降级
    OFFLINE = "offline"             # 已下线
    REJECTED = "rejected"           # 校验失败


@dataclass
class ToolManifest:
    """工具注册清单"""
    tool_id: str                     # 工具唯一标识
    name: str                        # 工具名称
    description: str                 # 工具描述
    category: ToolCategory           # 工具分类
    input_schema: dict               # 输入 JSON Schema
    output_schema: dict              # 输出 JSON Schema
    timeout_ms: int = 30000          # 默认超时（毫秒）
    requires_auth: bool = True       # 是否需要鉴权
    rate_limit_per_min: int = 60     # 每分钟限频
    version: str = "0.1.0"           # 版本号


class BaseTool(ABC):
    """工具抽象基类

    所有工具需继承此类，实现 execute 方法。
    """

    def __init__(self, manifest: ToolManifest):
        self._manifest = manifest
        self._status = ToolStatus.DEVELOPING

    @property
    def manifest(self) -> ToolManifest:
        """返回工具元信息"""
        return self._manifest

    @property
    def status(self) -> ToolStatus:
        """返回当前状态"""
        return self._status

    @abstractmethod
    async def execute(
        self,
        params: dict[str, Any],
        context: dict[str, Any],       # 用户会话上下文
    ) -> dict[str, Any]:
        """执行工具并返回结果"""
        ...

    async def validate_params(self, params: dict[str, Any]) -> bool:
        """参数校验（默认通过，子类可覆盖）"""
        return True

    async def health_check(self) -> bool:
        """健康检查"""
        return True

    def set_status(self, status: ToolStatus) -> None:
        """更新工具状态"""
        self._status = status


# 工具注册中心接口
class ToolRegistry(Protocol):
    """工具注册中心协议"""

    async def register(self, tool: BaseTool) -> bool:
        """注册工具"""
        ...

    async def deregister(self, tool_id: str) -> bool:
        """注销工具"""
        ...

    async def get_tool(self, tool_id: str) -> BaseTool | None:
        """获取工具实例"""
        ...

    async def list_tools(
        self, category: ToolCategory | None = None
    ) -> list[ToolManifest]:
        """列出可用工具"""
        ...

    async def health_check_all(self) -> dict[str, bool]:
        """对所有工具进行健康检查"""
        ...
