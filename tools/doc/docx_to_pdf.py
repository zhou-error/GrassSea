"""docx → PDF 转换工具"""

from __future__ import annotations

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest
from shared.utils.config import get_settings
from shared.utils.pdf_convert import available_converters, convert
from tools.doc._common import DocPathError, resolve_input, resolve_output

PDF_MANIFEST = ToolManifest(
    tool_id="docx_to_pdf",
    name="Word 转 PDF",
    description=(
        "把已有的 Word 文档（.docx）转换为 PDF。需要交付 PDF 版报告时使用。"
        "转换引擎按配置自动选择（本机 Word 或 LibreOffice）；"
        "若环境不具备转换能力，会返回明确原因，不会产出空文件。"
    ),
    category=ToolCategory.REPORT,
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "待转换的 .docx 路径"},
            "pdf_path": {"type": "string", "description": "输出 PDF 路径；留空则同名同目录"},
        },
        "required": ["path"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "pdf_path": {"type": "string"},
            "converter": {"type": "string"},
            "elapsed_ms": {"type": "integer"},
        },
    },
    timeout_ms=180000,
    version="0.1.0",
)


class DocxToPdfTool(BaseTool):
    """Word 转 PDF"""

    def __init__(self) -> None:
        super().__init__(PDF_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        try:
            src = resolve_input(str(params.get("path") or ""))
        except DocPathError as exc:
            return {"status": "error", "message": str(exc)}
        if src.suffix.lower() != ".docx":
            return {"status": "error", "message": "只支持 .docx 格式"}

        pdf_raw = params.get("pdf_path")
        try:
            target = resolve_output(str(pdf_raw)) if pdf_raw else src.with_suffix(".pdf")
        except DocPathError as exc:
            return {"status": "error", "message": str(exc)}
        if target.exists() and not params.get("overwrite", False):
            return {"status": "error", "message": f"PDF 已存在：{target.name}（如需覆盖请指定 overwrite=true）"}

        settings = get_settings()
        mode = (getattr(settings, "PDF_CONVERTER", "auto") or "auto").strip().lower()
        result = convert(src, target, mode=mode)

        if not result["ok"]:
            engines = available_converters()
            return {
                "status": "error",
                "message": result["message"],
                "available_converters": engines,
            }

        return {
            "status": "completed",
            "pdf_path": result["pdf_path"],
            "converter": result["converter"],
            "elapsed_ms": result["elapsed_ms"],
            "bytes": target.stat().st_size if target.exists() else 0,
        }
