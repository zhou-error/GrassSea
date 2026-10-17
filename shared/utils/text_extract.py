"""按文件格式提取纯文本

工作文件夹里的工程资料大量是 PDF / DOCX / XLSX，都是二进制。
若直接按文本解码，会导致**静默假成功**（出现乱码但状态是 completed），
违反项目「诚实失败」原则。

本模块按后缀分派到真正的解析器；无法解析时抛出可操作的错误，绝不返回乱码。
"""

from __future__ import annotations

from pathlib import Path

# 明确按文本处理的扩展名（这些才走编码解码）
TEXT_SUFFIXES = frozenset({
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".yaml", ".yml",
    ".log", ".ini", ".toml", ".cfg", ".conf", ".env", ".xml", ".html", ".htm",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".css", ".scss", ".sql", ".bat", ".ps1",
    ".java", ".go", ".rs", ".c", ".h", ".cpp", ".hpp", ".sh",
})

# 已知但当前**无法解析**的二进制格式：给出明确原因与替代方案
UNSUPPORTED = {
    ".doc": (
        "旧版 Word 二进制格式（.doc）无法解析。"
        "请在 Word 中「另存为」.docx 后重试，或用 LibreOffice 转换："
        "soffice --headless --convert-to docx <文件>"
    ),
    ".dwg": "DWG 是 AutoCAD 二进制格式，需要 CAD 解析能力，当前尚未实现。",
    ".dxf": "DXF 解析尚未实现（工具 cad_parse 目前返回未实现状态）。",
    ".xls": "旧版 Excel 二进制格式（.xls）无法解析，请另存为 .xlsx 后重试。",
    ".ppt": "旧版 PowerPoint 二进制格式无法解析，请另存为 .pptx。",
    ".zip": "压缩包需要先解压，再进行读取。",
    ".rar": "压缩包需要先解压，再进行读取。",
    ".7z": "压缩包需要先解压，再进行读取。",
}


class ExtractError(Exception):
    """提取失败（信息可直接展示给用户）"""


def _decode_text(raw: bytes) -> str:
    """按常见中文编码解码

    ⚠️ 刻意**不**回退到 latin-1：它对任意字节都不会失败，
    会把二进制文件"成功"解码成乱码，掩盖真实问题。
    """
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ExtractError(
        "该文件不是可识别的文本（编码无法识别），可能是二进制或已损坏。"
        "若确为文本，请另存为 UTF-8 后重试。"
    )


def _looks_binary(raw: bytes) -> bool:
    head = raw[:8192]
    return b"\x00" in head


def _extract_pdf(target: Path) -> tuple[str, str]:
    raw = target.read_bytes()
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=raw, filetype="pdf")
        parts = [page.get_text("text") for page in doc]
        doc.close()
        text = "\n\n".join(parts)
        note = "PyMuPDF"
    except ImportError:
        from io import BytesIO

        from PyPDF2 import PdfReader

        reader = PdfReader(BytesIO(raw))
        text = "\n\n".join((p.extract_text() or "") for p in reader.pages)
        note = "PyPDF2"
    if not text.strip():
        raise ExtractError(
            "该 PDF 未能提取到任何文本，通常是扫描件（纯图片）。"
            "当前不支持 OCR，请先用别的工具转成文字版 PDF。"
        )
    return text, note


def _extract_docx(target: Path) -> tuple[str, str]:
    try:
        from docx import Document
    except ImportError as exc:
        raise ExtractError("解析 .docx 需要 python-docx，请先安装") from exc

    try:
        doc = Document(str(target))
    except Exception as exc:  # noqa: BLE001
        # 常见于：把旧版 .doc 直接改名成 .docx，或文件损坏/只是主题占位文件
        raise ExtractError(
            f"「{target.name}」不是有效的 Word(.docx) 文件（{type(exc).__name__}）。"
            "常见原因：① 它其实是旧版 .doc 只改了扩展名；② 文件损坏或是占位/主题文件。"
            "请在 Word 中打开后「另存为」.docx 再重试。"
        ) from exc
    parts: list[str] = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            parts.append(t)
    for idx, table in enumerate(doc.tables, 1):
        parts.append(f"[表格 {idx}]")
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(",".join(cells))
    if not parts:
        raise ExtractError("Word 文档中没有可读取的文本内容。")
    return "\n".join(parts), "python-docx"


def _extract_xlsx(target: Path) -> tuple[str, str]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise ExtractError("解析 .xlsx 需要 openpyxl，请先安装") from exc

    wb = load_workbook(str(target), read_only=True, data_only=True)
    blocks: list[str] = []
    try:
        for ws in wb.worksheets:
            rows: list[str] = []
            for row in ws.iter_rows(values_only=True):
                cells = ["" if c is None else str(c).strip() for c in row]
                if any(cells):
                    rows.append(",".join(cells))
                if len(rows) >= 3000:
                    rows.append("…（该工作表其余行已省略）")
                    break
            if rows:
                blocks.append(f"[工作表] {ws.title}\n" + "\n".join(rows))
    finally:
        wb.close()
    if not blocks:
        raise ExtractError("Excel 中没有可读取的非空内容。")
    return "\n\n".join(blocks), "openpyxl"


def extract_text(target: Path, max_chars: int = 60_000) -> dict:
    """提取任意支持格式的纯文本

    返回: {"text","format","parser","chars","truncated","note"}
    无法解析时抛 ExtractError（消息可直接展示给用户）。
    """
    if not target.exists():
        raise ExtractError(f"文件不存在：{target.name}")
    if target.is_dir():
        raise ExtractError(f"这是目录而不是文件：{target.name}")

    suffix = target.suffix.lower()

    if suffix in UNSUPPORTED:
        raise ExtractError(UNSUPPORTED[suffix])

    if suffix == ".pdf":
        text, parser = _extract_pdf(target)
        fmt = "pdf"
    elif suffix == ".docx":
        text, parser = _extract_docx(target)
        fmt = "docx"
    elif suffix in (".xlsx", ".xlsm"):
        text, parser = _extract_xlsx(target)
        fmt = "xlsx"
    else:
        raw = target.read_bytes()
        if _looks_binary(raw):
            raise ExtractError(
                f"「{target.name}」看起来是二进制文件（含空字节），不是文本。"
                "支持的格式：文本类、.pdf、.docx、.xlsx。"
                "若这是 .doc/.dwg/.xls，请按提示先转换格式。"
            )
        text, parser = _decode_text(raw), "text"
        fmt = "text"

    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars] + f"\n…（已截断，原文共 {len(text)} 字符）"

    return {
        "text": text,
        "format": fmt,
        "parser": parser,
        "chars": len(text),
        "truncated": truncated,
    }
