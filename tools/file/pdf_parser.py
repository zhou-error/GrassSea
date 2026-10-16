"""PDF 解析工具 — 规范文件文本/表格提取"""

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

PDF_PARSER_MANIFEST = ToolManifest(
    tool_id="pdf_parser", name="PDF 解析", description="规范文件文本/表格提取，支持 PyMuPDF/pdfplumber",
    category=ToolCategory.FILE,
    input_schema={"type": "object", "properties": {"file_path": {"type": "string"}, "pages": {"type": "string"}}},
    output_schema={"type": "object", "properties": {"text": {"type": "string"}, "pages": {"type": "integer"}, "tables": {"type": "array"}}},
    timeout_ms=60000, version="0.1.0",
)


class PdfParserTool(BaseTool):
    def __init__(self): super().__init__(PDF_PARSER_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        """如实返回未实现 — 不返回任何正文或页数"""
        return {
            "status": "not_implemented",
            "message": "PDF 解析尚未实现：正文/表格提取流程未接通，无法返回页数、条文正文或表格内容。",
        }
