"""文档工具的公共逻辑：路径解析与安全校验

落盘位置优先级（需求方确认：Q5 = 优先工作文件夹，未选则 data/outputs）
1. 桌面模式下用户已选择工作文件夹 -> 相对路径落在其中，并做越界校验
2. 否则 -> <DATA_DIR>/outputs（或 DOC_OUTPUT_DIR）
"""

from __future__ import annotations

from pathlib import Path

from shared.utils import workspace as ws
from shared.utils.config import get_settings

DOC_SUFFIXES = {".docx", ".doc", ".md", ".txt"}
PDF_SUFFIXES = {".pdf"}


class DocPathError(Exception):
    """路径相关错误（信息可直接展示给用户）"""


def output_root() -> Path:
    """返回输出根目录"""
    root = ws.get_root()
    if root is not None:
        return root
    settings = get_settings()
    configured = (getattr(settings, "DOC_OUTPUT_DIR", "") or "").strip()
    if configured:
        base = Path(configured)
    else:
        data_dir = (getattr(settings, "DATA_DIR", "") or "").strip()
        base = (Path(data_dir) if data_dir else settings.PROJECT_ROOT / "data") / "outputs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def resolve_output(rel_path: str) -> Path:
    """解析输出路径并确保不越出输出根目录"""
    raw = (rel_path or "").strip()

    # 审计 S3-1：绝对路径必须拒绝，而不是静默 lstrip 后写到别处。
    # 之前 resolve_output("/etc/passwd") 会被改写成 <outputs>/etc/passwd 并"成功"，
    # 用户以为写到了 /etc，实际落在数据目录 —— 静默行为差异。
    from pathlib import Path as _Path

    # 注意：Windows 上 Path("/etc/passwd").is_absolute() 返回 False，
    # 单看 is_absolute 会漏掉「以斜杠开头」这类 POSIX 风格路径（合同测试抓到过）。
    looks_absolute = (
        _Path(raw).is_absolute()
        or raw.startswith(("/", "\\"))
        or (len(raw) > 1 and raw[1] == ":")
    )
    if looks_absolute:
        raise DocPathError(f"必须是相对路径，收到绝对路径：{rel_path}")

    rel = raw.replace("\\", "/").lstrip("/")
    if not rel:
        raise DocPathError("必须提供相对路径（含文件名）")
    root = output_root().resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise DocPathError(f"路径越界，已拒绝写入：{rel_path}") from exc
    return target


def resolve_input(rel_path: str) -> Path:
    """解析输入文件路径：先在工作文件夹找，再按绝对路径找"""
    rel = (rel_path or "").strip().strip('"')
    if not rel:
        raise DocPathError("必须提供文件路径")
    candidate = Path(rel)
    if candidate.is_absolute():
        if not candidate.exists():
            raise DocPathError(f"文件不存在：{rel}")
        return candidate
    root = ws.get_root()
    if root is not None:
        try:
            target = ws.resolve(rel)
            if target.exists():
                return target
        except Exception:  # noqa: BLE001
            pass
    fallback = output_root() / rel
    if fallback.exists():
        return fallback
    raise DocPathError(f"文件不存在：{rel}（已尝试工作文件夹与输出目录）")


def default_name(stem: str, suffix: str) -> str:
    """生成默认文件名"""
    safe = "".join(ch for ch in (stem or "文档") if ch not in '\\/:*?"<>|').strip() or "文档"
    return f"{safe}{suffix}"
