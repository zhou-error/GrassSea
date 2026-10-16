"""表格解析工具 — 型值表结构化提取"""

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

XLSX_PARSER_MANIFEST = ToolManifest(
    tool_id="xlsx_parser", name="表格解析", description="型值表结构化提取，支持 xlsx/xls/csv",
    category=ToolCategory.FILE,
    input_schema={"type": "object", "properties": {"file_path": {"type": "string"}, "sheet_name": {"type": "string"}}},
    output_schema={"type": "object", "properties": {"headers": {"type": "array"}, "rows": {"type": "integer"}, "data": {"type": "array"}}},
    timeout_ms=30000, version="0.1.0",
)


class XlsxParserTool(BaseTool):
    def __init__(self): super().__init__(XLSX_PARSER_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        """如实返回未实现 — 不返回任何表头或数据行"""
        return {
            "status": "not_implemented",
            "message": "型值表解析尚未实现：表格读取与型值结构化流程未接通，无法返回表头与数据行。",
        }
