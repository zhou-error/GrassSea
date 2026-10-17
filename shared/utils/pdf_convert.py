"""docx → PDF 转换（可切换引擎）

支持三种模式，由配置 PDF_CONVERTER 决定：

  word        调用本机 Microsoft Word（COM 自动化）。保真度最高，需要安装 Office。
  libreoffice 调用 LibreOffice 无头模式。不依赖 Office，跨平台，适合 Docker / 打包分发。
  none        禁用转换，调用时返回明确错误（不伪造 PDF）。
  auto（默认）先试 Word，不可用则试 LibreOffice，都不可用则报错并给出安装提示。

重要约束
--------
Word 与 LibreOffice 都是**本机程序**：Docker 容器里没有它们，
因此服务器形态下 PDF 转换不可用。这属于设计预期，会返回可读的中文原因，
而不是静默失败或产出空文件。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from shared.utils.logging import get_logger

logger = get_logger(__name__)

# 常见 LibreOffice 路径（Windows / Linux / macOS）
LIBREOFFICE_CANDIDATES = (
    r"C:/Program Files/LibreOffice/program/soffice.exe",
    r"C:/Program Files (x86)/LibreOffice/program/soffice.exe",
    "/usr/bin/soffice",
    "/usr/lib/libreoffice/program/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
)


def find_libreoffice() -> str | None:
    """定位 LibreOffice 可执行文件"""
    for candidate in LIBREOFFICE_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return shutil.which("soffice") or shutil.which("libreoffice")


def _convert_with_word(docx_path: Path, pdf_path: Path, timeout: float = 180.0) -> None:
    """用 Word COM 转换（仅 Windows 且装了 Office）"""
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise RuntimeError("未安装 pywin32，无法调用 Word 转换") from exc

    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(str(docx_path), ReadOnly=False)
        # 17 = wdExportFormatPDF
        doc.ExportAsFixedFormat(str(pdf_path), 17)
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:  # noqa: BLE001
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:  # noqa: BLE001
            pass


def _convert_with_libreoffice(docx_path: Path, pdf_path: Path, timeout: float = 180.0) -> None:
    """用 LibreOffice 无头模式转换"""
    soffice = find_libreoffice()
    if not soffice:
        raise RuntimeError("未找到 LibreOffice（soffice 可执行文件）")

    out_dir = pdf_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    # 使用独立的用户配置目录，避免与已运行的 LibreOffice 实例冲突
    profile = out_dir / ".lo-profile"
    cmd = [
        soffice,
        "--headless",
        "--norestore",
        f"-env:UserInstallation=file:///{str(profile).replace(os.sep, '/')}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(docx_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    # LibreOffice 输出 <stem>.pdf
    produced = out_dir / (docx_path.stem + ".pdf")
    if not produced.exists():
        raise RuntimeError(
            f"LibreOffice 转换未产出文件（exit={proc.returncode}）：{(proc.stderr or proc.stdout)[:300]}"
        )
    if produced.resolve() != pdf_path.resolve():
        produced.replace(pdf_path)


def convert(docx_path: str | Path, pdf_path: str | Path | None = None, mode: str = "auto") -> dict:
    """把 .docx 转成 .pdf

    返回: {"ok": bool, "pdf_path": str|None, "converter": str, "message": str, "elapsed_ms": int}
    """
    started = time.monotonic()
    src = Path(docx_path)
    if not src.exists():
        return {"ok": False, "pdf_path": None, "converter": "none",
                "message": f"源文件不存在：{src}", "elapsed_ms": 0}

    dst = Path(pdf_path) if pdf_path else src.with_suffix(".pdf")
    dst.parent.mkdir(parents=True, exist_ok=True)

    mode = (mode or "auto").strip().lower()
    if mode == "none":
        return {"ok": False, "pdf_path": None, "converter": "none",
                "message": "PDF 转换已被配置禁用（PDF_CONVERTER=none）", "elapsed_ms": 0}

    order = ["word", "libreoffice"] if mode == "auto" else [mode]
    errors: list[str] = []

    for engine in order:
        try:
            if engine == "word":
                _convert_with_word(src, dst)
            elif engine == "libreoffice":
                _convert_with_libreoffice(src, dst)
            else:
                errors.append(f"未知的转换引擎：{engine}")
                continue

            if not dst.exists() or dst.stat().st_size == 0:
                errors.append(f"{engine} 未产出有效 PDF")
                continue

            elapsed = int((time.monotonic() - started) * 1000)
            logger.info("PDF 转换成功", engine=engine, elapsed_ms=elapsed, size=dst.stat().st_size)
            return {"ok": True, "pdf_path": str(dst), "converter": engine,
                    "message": "转换成功", "elapsed_ms": elapsed}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{engine}: {exc}")
            logger.warning("PDF 转换失败，尝试下一个引擎", engine=engine, error=str(exc))

    elapsed = int((time.monotonic() - started) * 1000)
    hint = ""
    if mode == "auto" and not any("word" in e for e in errors if "未安装" not in e):
        hint = "；服务器/Docker 形态请在镜像中安装 LibreOffice，或设置 PDF_CONVERTER=libreoffice"
    message = "PDF 转换失败：" + " | ".join(errors) + hint
    return {"ok": False, "pdf_path": None, "converter": "none", "message": message, "elapsed_ms": elapsed}


def available_converters() -> dict:
    """探测当前可用的转换引擎（供状态接口与报错提示使用）"""
    word_ok = False
    try:
        import win32com.client  # type: ignore  # noqa: F401

        word_ok = os.name == "nt"
    except ImportError:
        word_ok = False
    lo = find_libreoffice()
    return {"word": word_ok, "libreoffice": bool(lo), "libreoffice_path": lo or ""}
