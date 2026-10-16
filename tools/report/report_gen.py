"""报告生成工具 — Markdown → PDF（规范排版）"""

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

REPORT_GEN_MANIFEST = ToolManifest(
    tool_id="report_gen", name="报告生成", description="Markdown → PDF 报告生成（规范排版）",
    category=ToolCategory.REPORT,
    input_schema={"type": "object", "properties": {"title": {"type": "string"}, "content": {"type": "string"}, "template": {"type": "string"}, "format": {"type": "string"}}},
    output_schema={"type": "object", "properties": {"file_path": {"type": "string"}, "pages": {"type": "integer"}}},
    timeout_ms=30000, version="0.1.0",
)


class ReportGenTool(BaseTool):
    def __init__(self): super().__init__(REPORT_GEN_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        """如实返回未实现 — 不产出任何报告文件"""
        return {
            "status": "not_implemented",
            "message": "报告生成尚未实现：未接入 Markdown→PDF 渲染器，无法产出报告文件，因此不返回任何文件路径。",
        }
