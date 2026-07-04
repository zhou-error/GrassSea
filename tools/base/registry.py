"""工具注册中心 — 支持热插拔机制

工具生命周期: DEVELOPING → REGISTERED → ONLINE → DEGRADED/OFFLINE
"""

from __future__ import annotations

import time
import asyncio
from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest, ToolStatus
from shared.utils.logging import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """工具注册中心（支持热插拔）"""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._health_interval = 30  # 健康检查间隔

    async def register(self, tool: BaseTool) -> bool:
        """注册工具（自动校验接口兼容性）"""
        manifest = tool.manifest
        if manifest.tool_id in self._tools:
            logger.warning("Tool already registered, replacing", tool_id=manifest.tool_id)
            await self.deregister(manifest.tool_id)

        if not await self._validate_tool(tool):
            tool.set_status(ToolStatus.REJECTED)
            logger.error("Tool validation failed", tool_id=manifest.tool_id)
            return False

        self._tools[manifest.tool_id] = tool
        tool.set_status(ToolStatus.REGISTERED)

        if await tool.health_check():
            tool.set_status(ToolStatus.ONLINE)

        logger.info("Tool registered", tool_id=manifest.tool_id, status=tool.status.value)
        return True

    async def deregister(self, tool_id: str) -> bool:
        """注销工具"""
        if tool_id in self._tools:
            self._tools[tool_id].set_status(ToolStatus.OFFLINE)
            del self._tools[tool_id]
            logger.info("Tool deregistered", tool_id=tool_id)
            return True
        return False

    async def get_tool(self, tool_id: str) -> BaseTool | None:
        """获取工具实例"""
        return self._tools.get(tool_id)

    async def list_tools(self, category: ToolCategory | None = None) -> list[ToolManifest]:
        """列出可用工具"""
        tools = self._tools.values()
        if category:
            tools = [t for t in tools if t.manifest.category == category]
        return [t.manifest for t in tools if t.status == ToolStatus.ONLINE]

    async def execute_tool(self, tool_id: str, params: dict, context: dict) -> dict:
        """执行工具"""
        tool = await self.get_tool(tool_id)
        if not tool:
            return {"status": "error", "message": f"Tool '{tool_id}' not found"}
        if tool.status != ToolStatus.ONLINE:
            return {"status": "error", "message": f"Tool '{tool_id}' is {tool.status.value}"}

        try:
            if not await tool.validate_params(params):
                return {"status": "error", "message": "Parameter validation failed"}
            result = await asyncio.wait_for(
                tool.execute(params, context),
                timeout=tool.manifest.timeout_ms / 1000,
            )
            return result
        except asyncio.TimeoutError:
            logger.warning("Tool execution timeout", tool_id=tool_id)
            return {"status": "error", "message": "Tool execution timeout"}
        except Exception as e:
            logger.error("Tool execution error", tool_id=tool_id, error=str(e))
            return {"status": "error", "message": str(e)}

    async def health_check_all(self) -> dict[str, bool]:
        """对所有工具进行健康检查，自动降级/恢复"""
        results = {}
        for tool_id, tool in list(self._tools.items()):
            try:
                healthy = await tool.health_check()
                results[tool_id] = healthy
                if healthy and tool.status == ToolStatus.DEGRADED:
                    tool.set_status(ToolStatus.ONLINE)
                    logger.info("Tool recovered", tool_id=tool_id)
                elif not healthy and tool.status == ToolStatus.ONLINE:
                    tool.set_status(ToolStatus.DEGRADED)
                    logger.warning("Tool degraded", tool_id=tool_id)
            except Exception:
                results[tool_id] = False
                tool.set_status(ToolStatus.DEGRADED)
        return results

    async def _validate_tool(self, tool: BaseTool) -> bool:
        """校验工具接口兼容性"""
        manifest = tool.manifest
        if not manifest.tool_id or not manifest.name:
            return False
        if not manifest.input_schema or not manifest.output_schema:
            return False
        if manifest.timeout_ms <= 0:
            return False
        return True
