"""CAD 图纸生成工具 — 型线图绘制、曲线光顺"""

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

CAD_DRAW_MANIFEST = ToolManifest(
    tool_id="cad_draw", name="CAD 图纸生成", description="型线图绘制、曲线光顺、支持 AutoCAD/SolidWorks MCP",
    category=ToolCategory.CAD,
    input_schema={"type": "object", "properties": {"drawing_type": {"type": "string"}, "parameters": {"type": "object"}}},
    output_schema={"type": "object", "properties": {"file_path": {"type": "string"}, "format": {"type": "string"}}},
    timeout_ms=120000, requires_auth=True, rate_limit_per_min=10, version="0.1.0",
)


class CadDrawTool(BaseTool):
    def __init__(self): super().__init__(CAD_DRAW_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        """如实返回未实现 — 不生成任何图纸文件"""
        return {
            "status": "not_implemented",
            "message": "CAD 图纸生成尚未实现：未接入 AutoCAD/SolidWorks MCP，无法输出 DWG 型线图与预览图，因此不返回任何文件路径。",
        }
