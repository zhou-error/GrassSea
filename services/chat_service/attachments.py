"""附件处理：接收上传文件 → 提取正文 → 生成描述符

支持的类型
----------
- 文本类：txt / md / markdown / csv / json / log / yaml / 常见源码扩展名 → 直接解码
- PDF   ：PyMuPDF（fitz），失败回退 PyPDF2（与知识库入库用的是同一套降级策略）
- 表格  ：xlsx / xlsm → openpyxl
- 图片  ：png / jpg / jpeg / webp / gif → 不提取正文，标记为 image
- 其它  ：标记为 binary，不提取正文

设计约定
--------
- 单个附件的正文注入上限 MAX_TEXT_CHARS，超出截断并标记 truncated（不静默丢内容）。
- 图片是否"能被模型理解"取决于当前配置的模型是否支持视觉；本模块只负责如实
  分类与说明，不做任何"假装看懂了"的处理。
"""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from shared.utils.config import get_settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)

# 单个附件注入模型上下文的最大字符数
MAX_TEXT_CHARS = 20_000
# 一次对话中所有附件注入的总字符上限
MAX_TOTAL_CHARS = 60_000

TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log", ".yaml", ".yml",
    ".ini", ".cfg", ".conf", ".xml", ".html", ".htm", ".sql",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".h", ".cpp", ".cs",
    ".go", ".rs", ".rb", ".php", ".sh", ".bat", ".ps1", ".r", ".m",
}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
TABLE_EXTS = {".xlsx", ".xlsm"}
PDF_EXTS = {".pdf"}


@dataclass
class Attachment:
    """一个已解析的附件"""

    attachment_id: str
    filename: str
    media_type: str
    size: int
    kind: str                      # text | pdf | table | image | binary
    text: str = ""
    stored_path: str = ""
    truncated: bool = False
    note: str = ""                 # 需要如实告知用户的说明（如"图片无法解析"）

    @property
    def chars(self) -> int:
        return len(self.text)

    def to_dict(self) -> dict:
        return {
            "attachment_id": self.attachment_id,
            "filename": self.filename,
            "media_type": self.media_type,
            "size": self.size,
            "kind": self.kind,
            "chars": self.chars,
            "text": self.text,
            "truncated": self.truncated,
            "note": self.note,
        }


def _uploads_dir() -> Path:
    settings = get_settings()
    data_dir = (getattr(settings, "DATA_DIR", "") or "").strip()
    base = Path(data_dir) if data_dir else (settings.PROJECT_ROOT / "data")
    path = base / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _decode_text(content: bytes) -> str:
    """按 UTF-8 → GBK → latin-1 依次尝试解码中文文本"""
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _extract_pdf(content: bytes) -> str:
    """PDF 正文提取：PyMuPDF 优先，PyPDF2 兜底（与知识库入库一致）"""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=content, filetype="pdf")
        try:
            parts = [page.get_text("text") for page in doc]
        finally:
            doc.close()
        text = "\n".join(parts)
        if text.strip():
            return text
    except Exception as exc:  # noqa: BLE001
        logger.warning("PyMuPDF 解析失败，回退 PyPDF2", error=str(exc))

    try:
        import io

        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # noqa: BLE001
        logger.warning("PDF 解析失败", error=str(exc))
        return ""


def _extract_xlsx(content: bytes) -> str:
    """表格正文提取：逐工作表转成 CSV 风格文本"""
    try:
        import io

        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        try:
            blocks: list[str] = []
            for ws in wb.worksheets:
                rows: list[str] = []
                for row in ws.iter_rows(values_only=True):
                    cells = ["" if c is None else str(c) for c in row]
                    if any(cells):
                        rows.append(",".join(cells))
                    if len(rows) >= 500:      # 单表最多 500 行，避免超大表格撑爆上下文
                        rows.append("…（该工作表其余行已省略）")
                        break
                if rows:
                    blocks.append(f"[工作表] {ws.title}\n" + "\n".join(rows))
            return "\n\n".join(blocks)
        finally:
            wb.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("XLSX 解析失败", error=str(exc))
        return ""


def classify(filename: str, media_type: str = "") -> str:
    """按扩展名判断附件类别"""
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXTS or media_type.startswith("image/"):
        return "image"
    if ext in PDF_EXTS or media_type == "application/pdf":
        return "pdf"
    if ext in TABLE_EXTS:
        return "table"
    if ext in TEXT_EXTS or media_type.startswith("text/"):
        return "text"
    return "binary"


def process_upload(filename: str, content: bytes, media_type: str = "") -> Attachment:
    """保存并在需要时提取正文"""
    attachment_id = uuid.uuid4().hex[:12]
    kind = classify(filename, media_type)

    stored_path = ""
    try:
        safe_name = Path(filename).name or "upload.bin"
        target = _uploads_dir() / f"{attachment_id}_{safe_name}"
        target.write_bytes(content)
        stored_path = str(target)
    except Exception as exc:  # noqa: BLE001
        logger.warning("附件落盘失败", filename=filename, error=str(exc))

    att = Attachment(
        attachment_id=attachment_id,
        filename=Path(filename).name or "upload.bin",
        media_type=media_type or "application/octet-stream",
        size=len(content),
        kind=kind,
        stored_path=stored_path,
    )

    if kind == "image":
        att.note = "图片已接收，但当前模型不支持图片理解，无法解析其中的内容。"
        return att

    if kind == "binary":
        att.note = "该文件类型暂不支持解析，仅完成接收与保存。"
        return att

    if kind == "pdf":
        text = _extract_pdf(content)
    elif kind == "table":
        text = _extract_xlsx(content)
    else:
        text = _decode_text(content)

    if not text.strip():
        att.note = "未能从该文件中提取到文本内容。"
        return att

    if len(text) > MAX_TEXT_CHARS:
        att.text = text[:MAX_TEXT_CHARS]
        att.truncated = True
    else:
        att.text = text
    return att


def build_context(attachments: list[dict]) -> tuple[str, list[str]]:
    """把附件正文拼成注入模型的上下文块

    参数 attachments 为附件描述符列表（来自 /attachments 的返回）。
    返回 (上下文文本, 需要如实告知用户的说明列表)。
    """
    if not attachments:
        return "", []

    blocks: list[str] = []
    notes: list[str] = []
    total = 0

    for idx, item in enumerate(attachments, start=1):
        name = item.get("filename") or f"附件{idx}"
        kind = item.get("kind") or "binary"
        text = item.get("text") or ""
        note = item.get("note") or ""

        header = f"[附件 {idx}] {name}（{kind}）"
        if note:
            notes.append(f"{name}：{note}")
            blocks.append(header + "\n" + note)
            continue

        remaining = MAX_TOTAL_CHARS - total
        if remaining <= 0:
            notes.append(f"{name}：内容超出本次对话的附件总量上限，未注入模型。")
            blocks.append(header + "\n（内容超出总量上限，已省略）")
            continue

        chunk = text[:remaining]
        total += len(chunk)
        blocks.append(header + "\n" + chunk)
        if item.get("truncated") or len(chunk) < len(text):
            notes.append(f"{name}：内容较长，仅注入前 {len(chunk)} 字符。")

    context = "\n\n".join(blocks)
    return context, notes


def image_data_url(stored_path: str, media_type: str) -> str | None:
    """把图片转成 data URL（供支持视觉的模型使用）"""
    try:
        data = Path(stored_path).read_bytes()
    except Exception:  # noqa: BLE001
        return None
    return f"data:{media_type or 'image/png'};base64," + base64.b64encode(data).decode("ascii")
