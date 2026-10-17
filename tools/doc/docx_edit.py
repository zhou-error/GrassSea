"""Word 文档修改工具 — 支持四种方式

需求方确认（Q3 全选）：
  append        在文档末尾追加内容（不触碰原有内容，最安全）
  replace       占位符替换，例如 {{项目名称}}、{{日期}}（覆盖正文/表格/页眉页脚）
  rewrite       按标题定位：找到指定标题，重写其下直到下一个同级或更高级标题之前的内容
  reformat      保留文本、丢弃原格式，按目标模板整体重排
"""

from __future__ import annotations

import copy
import re

from docx import Document

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest
from shared.utils.docx_render import render_to_file
from shared.utils.logging import get_logger
from tools.doc._common import DocPathError, resolve_input, resolve_output

logger = get_logger(__name__)

PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

EDIT_MANIFEST = ToolManifest(
    tool_id="docx_edit",
    name="修改 Word 文档",
    description=(
        "修改已有的 Word 文档（.docx），支持四种方式："
        "append=在末尾追加内容；replace=占位符替换（如 {{项目名}}）；"
        "rewrite=按标题定位并重写该标题下的内容；reformat=保留文本、按模板整体重排。"
        "需要保留原文档、另存为新文件时，请传 output_path。"
    ),
    category=ToolCategory.REPORT,
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "待修改的 .docx 相对路径或绝对路径"},
            "mode": {
                "type": "string",
                "enum": ["append", "replace", "rewrite", "reformat"],
                "description": "修改方式",
            },
            "output_path": {"type": "string", "description": "另存为的路径；留空则原地修改"},
            "sections": {"type": "array", "description": "mode=append/rewrite 时的新内容块数组"},
            "heading": {"type": "string", "description": "mode=rewrite 时的目标标题文本"},
            "values": {"type": "object", "description": "mode=replace 时的占位符键值对"},
            "template": {"type": "string", "description": "mode=reformat 时的排版模板名"},
        },
        "required": ["path", "mode"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "path": {"type": "string"},
            "abs_path": {"type": "string"},
            "changes": {"type": "integer"},
        },
    },
    timeout_ms=60000,
    version="0.1.0",
)


def _iter_paragraphs(doc):
    """遍历正文、表格、页眉页脚的段落"""
    for para in doc.paragraphs:
        yield para
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    yield para
    for section in doc.sections:
        for part in (section.header, section.footer):
            for para in part.paragraphs:
                yield para


def _replace_in_paragraph(para, values: dict) -> int:
    """在一个段落内替换占位符，返回替换次数"""
    full = para.text
    if "{{" not in full:
        return 0
    replaced = PLACEHOLDER_RE.sub(
        lambda m: str(values.get(m.group(1).strip(), m.group(0))), full
    )
    if replaced == full:
        return 0
    # 占位符可能跨 run：统一写入第一个 run，其余清空（保留段落样式）
    if para.runs:
        para.runs[0].text = replaced
        for run in para.runs[1:]:
            run.text = ""
    return len(PLACEHOLDER_RE.findall(full))


def _heading_level(para) -> int | None:
    """判断段落是否为标题并返回级别"""
    style = (para.style.name or "") if para.style is not None else ""
    m = re.match(r"^(?:Heading|标题)\s*(\d)$", style)
    if m:
        return int(m.group(1))
    return None


def _extract_plain_sections(doc) -> list[dict]:
    """把文档内容抽取成结构化块（用于 reformat）"""
    blocks: list[dict] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        level = _heading_level(para)
        if level:
            blocks.append({"type": "heading", "level": min(level, 4), "text": text})
        else:
            blocks.append({"type": "paragraph", "text": text})
    for table in doc.tables:
        header: list[str] = []
        rows: list[list[str]] = []
        for r_idx, row in enumerate(table.rows):
            cells = [c.text.strip() for c in row.cells]
            if r_idx == 0:
                header = cells
            else:
                rows.append(cells)
        blocks.append({"type": "table", "header": header, "rows": rows})
    return blocks


def _append_sections(doc, sections: list[dict], base_dir=None) -> None:
    """把新内容块追加到文档末尾（复用渲染核心的块渲染器）"""
    from shared.utils.docx_render import DEFAULT_STYLE, _apply_template, _render_heading,         _render_paragraph, _render_list, _render_table, _render_image, _render_formula

    style = _apply_template(DEFAULT_STYLE, None)
    for block in sections:
        if not isinstance(block, dict):
            continue
        kind = str(block.get("type", "paragraph")).lower()
        if kind == "heading":
            _render_heading(doc, block, style)
        elif kind == "paragraph":
            _render_paragraph(doc, block, style)
        elif kind == "list":
            _render_list(doc, block, style)
        elif kind == "table":
            _render_table(doc, block, style)
        elif kind == "image":
            _render_image(doc, block, base_dir)
        elif kind == "formula":
            _render_formula(doc, block)
        elif kind == "page_break":
            doc.add_page_break()


def _rewrite_under_heading(doc, heading_text: str, sections: list[dict], base_dir=None) -> int:
    """删除指定标题下的旧内容，插入新内容；返回删除的段落数"""
    target_idx = None
    target_level = None
    for idx, para in enumerate(doc.paragraphs):
        if para.text.strip() == heading_text.strip():
            target_idx = idx
            target_level = _heading_level(para) or 1
            break
    if target_idx is None:
        raise ValueError(f"未找到标题：{heading_text}")

    end_idx = len(doc.paragraphs)
    for idx in range(target_idx + 1, len(doc.paragraphs)):
        level = _heading_level(doc.paragraphs[idx])
        if level is not None and level <= target_level:
            end_idx = idx
            break

    removed = 0
    for para in list(doc.paragraphs[target_idx + 1:end_idx]):
        para._p.getparent().remove(para._p)
        removed += 1

    # 用临时文档渲染新内容，再搬运 XML 到锚点之前
    if sections:
        anchor = doc.paragraphs[target_idx]._p
        temp = Document()
        _append_sections(temp, sections, base_dir)
        for element in list(temp.element.body):
            tag = element.tag.split("}")[-1]
            if tag in ("sectPr",):
                continue
            anchor.addnext(copy.deepcopy(element))
            anchor = element
    return removed


class DocxEditTool(BaseTool):
    """修改 Word 文档"""

    def __init__(self) -> None:
        super().__init__(EDIT_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        mode = str(params.get("mode") or "").strip().lower()
        if mode not in {"append", "replace", "rewrite", "reformat"}:
            return {"status": "error", "message": f"不支持的 mode：{mode}"}

        try:
            src = resolve_input(str(params.get("path") or ""))
        except DocPathError as exc:
            return {"status": "error", "message": str(exc)}
        if src.suffix.lower() != ".docx":
            return {"status": "error", "message": "只支持 .docx 格式（.doc 请先用 Word 另存为 .docx）"}

        out_path = params.get("output_path")
        try:
            target = resolve_output(str(out_path)) if out_path else src
        except DocPathError as exc:
            return {"status": "error", "message": str(exc)}
        if target.exists() and out_path and not params.get("overwrite", False):
            return {"status": "error", "message": f"目标文件已存在：{out_path}（如需覆盖请指定 overwrite=true）"}

        try:
            if mode == "reformat":
                doc = Document(str(src))
                sections = _extract_plain_sections(doc)
                spec = {"template": params.get("template"), "sections": sections}
                render_to_file(spec, target, base_dir=src.parent)
                return {
                    "status": "completed", "mode": mode, "path": str(target),
                    "abs_path": str(target), "changes": len(sections),
                }

            doc = Document(str(src))

            if mode == "append":
                sections = params.get("sections") or []
                if not sections:
                    return {"status": "error", "message": "mode=append 需要提供 sections"}
                _append_sections(doc, sections, src.parent)
                changes = len(sections)
            elif mode == "replace":
                values = params.get("values")
                if not isinstance(values, dict) or not values:
                    return {"status": "error", "message": "mode=replace 需要提供 values 键值对"}
                changes = sum(_replace_in_paragraph(para, values) for para in _iter_paragraphs(doc))
                if changes == 0:
                    return {
                        "status": "error",
                        "message": "文档中未找到任何匹配的占位符（格式应为 {{键名}}）",
                    }
            else:  # rewrite
                heading = str(params.get("heading") or "").strip()
                sections = params.get("sections") or []
                if not heading:
                    return {"status": "error", "message": "mode=rewrite 需要提供 heading"}
                changes = _rewrite_under_heading(doc, heading, sections, src.parent)

            doc.save(str(target))
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("docx 修改失败", mode=mode, error=str(exc))
            return {"status": "error", "message": f"文档修改失败：{exc}"}

        return {
            "status": "completed",
            "mode": mode,
            "path": str(target),
            "abs_path": str(target),
            "changes": changes,
            "bytes": target.stat().st_size,
        }
