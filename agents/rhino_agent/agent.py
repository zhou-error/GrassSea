"""Rhino Agent — 通过本地桥接在 Rhino 8 中建模

诚实性约定：Rhino 未打开或桥接未运行时，工具会返回 bridge_unreachable，
本 Agent 原样转达，不伪造 object_id 或文件路径。
"""

from __future__ import annotations

from agents.rhino_agent.prompts import render as render_system_prompt
from shared.protocols.agent import AgentCallbacks, AgentCapability, AgentMetadata, BaseAgent
from shared.utils.logging import get_logger

logger = get_logger(__name__)

RHINO_AGENT_METADATA = AgentMetadata(
    agent_id="rhino_agent",
    name="Rhino 建模 Agent",
    role="在 Rhino 8 中创建曲线、挤出实体、布尔运算、删除与查询几何",
    capabilities=[
        AgentCapability(
            name="rhino_create",
            description="创建插值曲线并沿曲线平面法向挤出",
            tools=["rhino_bridge"],
            estimated_latency_ms=8000,
        ),
        AgentCapability(
            name="rhino_boolean",
            description="对两个实体做并/差/交（破坏性，需确认）",
            tools=["rhino_bridge"],
            estimated_latency_ms=12000,
        ),
        AgentCapability(
            name="rhino_query",
            description="查询对象的类型、包围盒与面数",
            tools=["rhino_bridge"],
            estimated_latency_ms=3000,
        ),
    ],
    model_preference="deepseek-chat",
    max_concurrent_tasks=2,
    version="0.1.0",
)


class RhinoAgent(BaseAgent):
    """Rhino 建模智能体"""

    def __init__(self) -> None:
        super().__init__(RHINO_AGENT_METADATA)

    @property
    def system_prompt(self) -> str:
        """本 Agent 使用独立系统提示词（不与通用工具循环提示词混用）"""
        return render_system_prompt()

    async def handle_task(self, task: dict, context: dict, callbacks: AgentCallbacks) -> dict:
        action = str(task.get("action") or "")
        inputs = task.get("inputs") or {}
        operation = str(inputs.get("operation") or "").strip()

        if not operation:
            operation = self._guess_operation(action)

        params = inputs.get("params")
        if not isinstance(params, dict):
            params = {k: v for k, v in inputs.items() if k not in ("operation", "params", "bake", "confirm")}

        payload = {
            "operation": operation,
            "params": params,
            "bake": bool(inputs.get("bake", True)),
            "confirm": bool(inputs.get("confirm", False)),
        }

        from tools.cad.rhino_bridge import RhinoBridgeTool

        result = await RhinoBridgeTool().execute(payload, context)
        logger.info(
            "Rhino 任务完成",
            operation=operation,
            status=result.get("status"),
            objects=len(result.get("object_ids") or []),
        )
        return result

    @staticmethod
    def _guess_operation(action: str) -> str:
        text = action.lower()
        if "布尔" in action or "boolean" in text:
            return "boolean"
        if "删除" in action or "delete" in text:
            return "delete"
        if "查询" in action or "检查" in action or "query" in text:
            return "query"
        if "挤出" in action or "extrude" in text:
            return "extrude"
        return "create_curve"
