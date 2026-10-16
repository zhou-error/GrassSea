"""DWG 格式转换工具 — DWG ↔ DXF ↔ PDF ↔ PNG"""

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

DWG_CONVERTER_MANIFEST = ToolManifest(
    tool_id="dwg_converter", name="DWG 格式转换", description="DWG ↔ DXF ↔ PDF ↔ PNG 格式互转",
    category=ToolCategory.FILE,
    input_schema={"type": "object", "properties": {"file_path": {"type": "string"}, "target_format": {"type": "string"}}},
    output_schema={"type": "object", "properties": {"output_path": {"type": "string"}}},
    timeout_ms=60000, version="0.1.0",
)


class DwgConverterTool(BaseTool):
    def __init__(self): super().__init__(DWG_CONVERTER_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        """如实返回未实现 — 不产出任何转换文件"""
        return {
            "status": "not_implemented",
            "message": "DWG 格式转换尚未实现：未接入 DWG/DXF/PDF/PNG 转换器（如 ODA File Converter），无法产出转换文件。",
        }
