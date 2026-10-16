"""CAD 图纸解析工具 — 从 DWG/DXF 提取尺寸、标注、图层"""

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

CAD_PARSE_MANIFEST = ToolManifest(
    tool_id="cad_parse", name="CAD 图纸解析", description="从 DWG/DXF 提取尺寸、标注、图层信息",
    category=ToolCategory.CAD,
    input_schema={"type": "object", "properties": {"file_path": {"type": "string"}}},
    output_schema={"type": "object", "properties": {"dimensions": {"type": "array"}, "layers": {"type": "array"}}},
    timeout_ms=60000, requires_auth=True, rate_limit_per_min=20, version="0.1.0",
)


class CadParseTool(BaseTool):
    def __init__(self): super().__init__(CAD_PARSE_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        """如实返回未实现 — 不返回任何图纸解析结论"""
        return {
            "status": "not_implemented",
            "message": "CAD 图纸解析尚未实现：未接入 DXF/DWG 解析器，无法从图纸中提取真实尺寸、标注与图层。",
        }
