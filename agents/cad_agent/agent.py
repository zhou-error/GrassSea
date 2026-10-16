"""CAD Agent — 图纸解析、型线绘制、曲线光顺、DWG 操作

诚实性约定：本 Agent 尚未接入 CAD 引擎与 DWG/DXF 解析器，
因此不生成任何图纸文件、不返回文件路径，也不给出无法测量的质量指标。
"""

from __future__ import annotations
from shared.protocols.agent import AgentCallbacks, AgentCapability, AgentMetadata, BaseAgent

CAD_AGENT_METADATA = AgentMetadata(
    agent_id="cad_agent",
    name="CAD Agent",
    role="图纸解析、型线绘制、曲线光顺、DWG 操作",
    capabilities=[
        AgentCapability(name="cad_draw", description="型线图绘制与曲线光顺", tools=["cad_draw", "dwg_converter"], estimated_latency_ms=5000),
        AgentCapability(name="cad_parse", description="从 DWG/DXF 提取尺寸和标注", tools=["cad_parse", "ocr_engine"], estimated_latency_ms=3000),
    ],
    model_preference="deepseek-chat",
    max_concurrent_tasks=2,
    version="0.1.0",
)


class CADAgent(BaseAgent):
    def __init__(self): super().__init__(CAD_AGENT_METADATA)

    async def handle_task(self, task: dict, context: dict, callbacks: AgentCallbacks) -> dict:
        """动作路由保持不变：cad_parse / parse → 图纸解析；cad_draw → 型线绘制"""
        action = task.get("action", "")
        if "parse" in action or "解析" in action:
            return await self._parse_drawing(task, context)
        return await self._draw_lines(task, context)

    async def _draw_lines(self, task: dict, context: dict) -> dict:
        """型线图绘制 — 未接入 CAD 引擎，如实返回未实现"""
        return {
            "status": "not_implemented",
            "message": "型线图绘制尚未实现：未接入 AutoCAD/SolidWorks 等 CAD 引擎，无法生成 DWG 型线图与预览图，因此不返回任何文件路径或光顺质量指标。",
        }

    async def _parse_drawing(self, task: dict, context: dict) -> dict:
        """图纸解析 — 未接入解析器，如实返回未实现"""
        return {
            "status": "not_implemented",
            "message": "图纸解析尚未实现：未接入 DWG/DXF 解析器与 OCR 引擎，无法从图纸中提取真实的尺寸、标注与图层，因此不返回任何提取结果。",
        }
