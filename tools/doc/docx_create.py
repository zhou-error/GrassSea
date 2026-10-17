"""Word 文档新建工具 — 按结构化描述生成排版完整的 .docx

需求方确认的排版范围：标题层级、自动目录、页眉页脚页码、表格（含合并单元格与
表头跨页重复）、图片、字体字号颜色对齐、行距段前后首行缩进、分页、分节横向页、
有序/无序列表、公式（OMML）。脚注按需求方决定**不提供**。
"""

from __future__ import annotations

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest
from shared.utils.docx_render import render_to_file
from shared.utils.logging import get_logger
from tools.doc._common import DocPathError, default_name, resolve_output

logger = get_logger(__name__)

CREATE_MANIFEST = ToolManifest(
    tool_id="docx_create",
    name="新建 Word 文档",
    description=(
        "按结构化描述新建一份排版完整的 Word 文档（.docx）。"
        "需要在文档中包含多级标题、自动目录、页眉页脚与页码、带合并单元格的表格、"
        "图片、公式、分页或横向页时使用本工具。"
        "用户未指定保存格式时默认保存为 .docx；如需 PDF 另行调用 docx_to_pdf。"
        "不提供脚注功能。"
    ),
    category=ToolCategory.REPORT,
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "相对输出目录的文件路径，例如 报告/稳性计算书.docx"},
            "document": {
                "type": "object",
                "description": (
                    "文档结构化描述。字段：template(模板名)、cover(封面)、toc(是否插目录)、"
                    "header/footer_note/page_number、sections(内容块数组)。"
                    "内容块 type 取值：heading/paragraph/list/table/image/formula/page_break/section_break。"
                ),
            },
            "overwrite": {"type": "boolean", "description": "目标已存在时是否覆盖，默认 false"},
        },
        "required": ["path", "document"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "path": {"type": "string"},
            "abs_path": {"type": "string"},
            "bytes": {"type": "integer"},
        },
    },
    timeout_ms=60000,
    version="0.1.0",
)


class DocxCreateTool(BaseTool):
    """新建 Word 文档"""

    def __init__(self) -> None:
        super().__init__(CREATE_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        path = str(params.get("path") or "").strip()
        document = params.get("document")
        if not isinstance(document, dict):
            return {"status": "error", "message": "document 必须是对象"}
        if not path:
            path = default_name(document.get("title") or "文档", ".docx")
        if not path.lower().endswith(".docx"):
            path += ".docx"

        try:
            target = resolve_output(path)
        except DocPathError as exc:
            return {"status": "error", "message": str(exc)}

        if target.exists() and not params.get("overwrite", False):
            return {
                "status": "error",
                "message": f"文件已存在：{path}（如需覆盖请显式指定 overwrite=true）",
            }

        try:
            render_to_file(document, target, base_dir=target.parent)
        except FileNotFoundError as exc:
            return {"status": "error", "message": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("docx 生成失败", path=path, error=str(exc))
            return {"status": "error", "message": f"文档生成失败：{exc}"}

        return {
            "status": "completed",
            "path": path,
            "abs_path": str(target),
            "bytes": target.stat().st_size,
            "blocks": len(document.get("sections") or []),
        }
