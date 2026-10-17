"""报告生成工具 — Markdown → Word(docx) → PDF

原先只是诚实占位（not_implemented）。现在接入真实渲染链：
Markdown 解析成结构化块 → shared.utils.docx_render 渲染 .docx → 可选导出 PDF。
需求方确认（Q7=A）：与 docx 能力一起实现。
"""

from __future__ import annotations

import re

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest
from shared.utils.config import get_settings
from shared.utils.docx_render import render_to_file
from shared.utils.logging import get_logger
from shared.utils.pdf_convert import convert
from tools.doc._common import DocPathError, default_name, resolve_output

logger = get_logger(__name__)

REPORT_MANIFEST = ToolManifest(
    tool_id="report_gen",
    name="报告生成",
    description=(
        "把 Markdown 文本渲染成规范排版的 Word 文档，可选同时导出 PDF。"
        "适合用户提供了一段 Markdown 内容、希望得到正式排版报告文件的场景。"
        "支持 Markdown 标题（# 到 ####）、段落、有序/无序列表、表格、图片。"
        "更精细的排版控制（目录、页眉页脚、合并单元格、公式）请改用 docx_create。"
    ),
    category=ToolCategory.REPORT,
    input_schema={
        "type": "object",
        "properties": {
            "markdown": {"type": "string", "description": "Markdown 正文"},
            "path": {"type": "string", "description": "输出 .docx 的相对路径；留空按 title 生成"},
            "title": {"type": "string", "description": "文档标题（用于封面与默认文件名）"},
            "toc": {"type": "boolean", "description": "是否插入自动目录，默认 false"},
            "to_pdf": {"type": "boolean", "description": "是否同时导出 PDF，默认 false"},
            "template": {"type": "string", "description": "排版模板名，默认取 DOC_DEFAULT_TEMPLATE"},
            "overwrite": {"type": "boolean", "description": "目标已存在时是否覆盖"},
        },
        "required": ["markdown"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "path": {"type": "string"},
            "pdf_path": {"type": "string"},
            "blocks": {"type": "integer"},
        },
    },
    timeout_ms=180000,
    version="0.1.0",
)

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
_ULIST_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_OLIST_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}")
_IMAGE_RE = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)\s*$")
_FENCE = "\x60\x60\x60"


def markdown_to_blocks(md: str) -> list[dict]:
    """把 Markdown 转成渲染块"""
    blocks: list[dict] = []
    lines = (md or "").replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        if stripped.startswith(_FENCE):
            i += 1
            buf: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith(_FENCE):
                buf.append(lines[i])
                i += 1
            i += 1
            if buf:
                blocks.append({"type": "paragraph", "text": "\n".join(buf), "font": "Consolas",
                               "first_line_indent": False, "line_spacing": 1.0})
            continue

        m = _HEADING_RE.match(stripped)
        if m:
            blocks.append({"type": "heading", "level": len(m.group(1)), "text": m.group(2).strip()})
            i += 1
            continue

        m = _IMAGE_RE.match(stripped)
        if m:
            blocks.append({"type": "image", "path": m.group(1).strip(), "width_cm": 12})
            i += 1
            continue

        if stripped.startswith("|"):
            rows_raw: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows_raw.append(lines[i].strip())
                i += 1
            parsed = [[c.strip() for c in r.strip("|").split("|")]
                      for r in rows_raw if not _TABLE_SEP_RE.match(r)]
            if parsed:
                blocks.append({"type": "table", "header": parsed[0], "rows": parsed[1:]})
            continue

        if _ULIST_RE.match(line) or _OLIST_RE.match(line):
            ordered = bool(_OLIST_RE.match(line))
            pattern = _OLIST_RE if ordered else _ULIST_RE
            items: list[str] = []
            while i < len(lines):
                mm = pattern.match(lines[i])
                if not mm:
                    break
                items.append(mm.group(1).strip())
                i += 1
            blocks.append({"type": "list", "ordered": ordered, "items": items})
            continue

        buf = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (not nxt or _HEADING_RE.match(nxt) or _ULIST_RE.match(nxt)
                    or _OLIST_RE.match(nxt) or nxt.startswith("|") or nxt.startswith(_FENCE)):
                break
            buf.append(nxt)
            i += 1
        blocks.append({"type": "paragraph", "text": " ".join(buf)})

    return blocks


class ReportGenTool(BaseTool):
    """报告生成"""

    def __init__(self) -> None:
        super().__init__(REPORT_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        markdown = params.get("markdown")
        if not isinstance(markdown, str) or not markdown.strip():
            return {"status": "error", "message": "必须提供非空的 markdown 内容"}

        title = str(params.get("title") or "报告")
        template = str(params.get("template") or getattr(get_settings(), "DOC_DEFAULT_TEMPLATE", "report") or "report")
        blocks = markdown_to_blocks(markdown)
        if not blocks:
            return {"status": "error", "message": "Markdown 未解析出任何内容块"}

        path = str(params.get("path") or "").strip() or default_name(title, ".docx")
        if not path.lower().endswith(".docx"):
            path += ".docx"
        try:
            target = resolve_output(path)
        except DocPathError as exc:
            return {"status": "error", "message": str(exc)}
        if target.exists() and not params.get("overwrite", False):
            return {"status": "error", "message": f"文件已存在：{path}（如需覆盖请指定 overwrite=true）"}

        spec = {
            "template": template,
            "cover": {"title": title},
            "toc": bool(params.get("toc", False)),
            "page_number": True,
            "sections": blocks,
        }
        try:
            render_to_file(spec, target, base_dir=target.parent)
        except Exception as exc:  # noqa: BLE001
            logger.error("报告渲染失败", error=str(exc))
            return {"status": "error", "message": f"报告渲染失败：{exc}"}

        result = {
            "status": "completed",
            "path": path,
            "abs_path": str(target),
            "bytes": target.stat().st_size,
            "blocks": len(blocks),
        }

        if params.get("to_pdf", False):
            pdf_result = convert(target, target.with_suffix(".pdf"),
                                 mode=(getattr(get_settings(), "PDF_CONVERTER", "auto") or "auto"))
            result["pdf_path"] = pdf_result["pdf_path"] or ""
            result["pdf_ok"] = bool(pdf_result["ok"])
            if not pdf_result["ok"]:
                result["pdf_message"] = pdf_result["message"]
        return result
