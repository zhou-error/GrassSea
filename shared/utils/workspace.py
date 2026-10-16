"""工作文件夹访问（桌面模式）

用户在界面上选定一个文件夹后，模型可以通过 workspace_list / workspace_read /
workspace_write 三个工具按需读写其中的文件。用户未指定保存格式时，由模型自行
决定合适的扩展名。

安全边界
--------
1. 仅在 DESKTOP_MODE=true 时可用；Docker/服务器模式下一律拒绝。
2. 所有相对路径都经过 resolve() 归一化并校验必须落在根目录之内，
   从而阻止 ../../ 之类的路径穿越。
3. 读取有字节与字符上限，写入有大小上限；覆盖已有文件需要显式 overwrite=true。
4. 列出目录时跳过常见的重目录（.git / node_modules / __pycache__ 等）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from shared.utils.config import get_settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)

# 列目录时跳过的目录名
SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    ".idea", ".vscode", "dist", "build", ".next", ".cache", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "target", "bin", "obj",
}

MAX_READ_BYTES = 2 * 1024 * 1024        # 单文件读取上限 2MB
MAX_READ_CHARS = 60_000                 # 注入模型的字符上限
MAX_WRITE_BYTES = 5 * 1024 * 1024       # 单文件写入上限 5MB
MAX_LIST_ENTRIES = 500                  # 单次列目录条目上限

# 进程级当前工作文件夹（桌面模式下由用户选定）
_current_root: Path | None = None


class WorkspaceError(Exception):
    """工作文件夹操作错误（信息可直接展示给用户）"""


def is_enabled() -> bool:
    """工作文件夹功能是否可用（仅桌面模式）"""
    return bool(getattr(get_settings(), "DESKTOP_MODE", False))


def _require_enabled() -> None:
    if not is_enabled():
        raise WorkspaceError("工作文件夹功能仅在桌面模式下可用（请用 app.launcher --desktop 启动）")


def get_root() -> Path | None:
    """当前工作文件夹；未选择时返回 None"""
    global _current_root
    if _current_root is not None:
        return _current_root
    # 允许通过配置预置（例如快捷方式带上 WORKSPACE_ROOT）
    configured = (getattr(get_settings(), "WORKSPACE_ROOT", "") or "").strip()
    if configured:
        p = Path(configured)
        if p.is_dir():
            _current_root = p.resolve()
    return _current_root


def set_root(path: str) -> Path:
    """设置工作文件夹（必须是已存在的目录）"""
    _require_enabled()
    if not path or not path.strip():
        raise WorkspaceError("路径为空")
    p = Path(path.strip().strip('"')).expanduser()
    if not p.exists():
        raise WorkspaceError(f"目录不存在：{p}")
    if not p.is_dir():
        raise WorkspaceError(f"不是目录：{p}")
    global _current_root
    _current_root = p.resolve()
    logger.info("工作文件夹已设置", root=str(_current_root))
    return _current_root


def resolve(rel_path: str = "") -> Path:
    """把相对路径解析为绝对路径，并确保不越出工作文件夹"""
    root = get_root()
    if root is None:
        raise WorkspaceError("尚未选择工作文件夹")
    rel = (rel_path or "").strip().replace("\\", "/").lstrip("/")
    target = (root / rel).resolve() if rel else root
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise WorkspaceError(f"路径越界，已拒绝访问：{rel_path}") from exc
    return target


def list_dir(rel_path: str = "", max_entries: int = MAX_LIST_ENTRIES) -> dict:
    """列出目录内容（只列一层）"""
    _require_enabled()
    target = resolve(rel_path)
    if not target.exists():
        raise WorkspaceError(f"路径不存在：{rel_path}")
    if target.is_file():
        raise WorkspaceError(f"这是文件而不是目录：{rel_path}")

    root = get_root()
    assert root is not None
    entries: list[dict] = []
    truncated = False
    try:
        for item in sorted(target.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            if item.name in SKIP_DIRS or item.name.startswith("."):
                continue
            if len(entries) >= max_entries:
                truncated = True
                break
            try:
                stat = item.stat()
                entries.append({
                    "name": item.name,
                    "path": str(item.relative_to(root)).replace("\\", "/"),
                    "type": "dir" if item.is_dir() else "file",
                    "size": 0 if item.is_dir() else stat.st_size,
                    "modified": int(stat.st_mtime),
                })
            except OSError:
                continue
    except PermissionError as exc:
        raise WorkspaceError(f"没有权限读取该目录：{rel_path}") from exc

    return {
        "root": str(root),
        "path": str(target.relative_to(root)).replace("\\", "/") or ".",
        "entries": entries,
        "count": len(entries),
        "truncated": truncated,
    }


def read_file(rel_path: str, max_chars: int = MAX_READ_CHARS) -> dict:
    """读取文本文件"""
    _require_enabled()
    target = resolve(rel_path)
    if not target.exists():
        raise WorkspaceError(f"文件不存在：{rel_path}")
    if target.is_dir():
        raise WorkspaceError(f"这是目录而不是文件：{rel_path}")

    size = target.stat().st_size
    if size > MAX_READ_BYTES:
        raise WorkspaceError(
            f"文件过大（{size} 字节），单次读取上限 {MAX_READ_BYTES} 字节：{rel_path}"
        )

    raw = target.read_bytes()
    text = ""
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        raise WorkspaceError(f"无法解码为文本（可能是二进制文件）：{rel_path}")

    truncated = len(text) > max_chars
    return {
        "path": rel_path,
        "size": size,
        "chars": len(text),
        "text": text[:max_chars],
        "truncated": truncated,
    }


def write_file(rel_path: str, content: str, overwrite: bool = False) -> dict:
    """写入文本文件；已存在且未显式允许覆盖时拒绝"""
    _require_enabled()
    if not rel_path or not rel_path.strip():
        raise WorkspaceError("必须提供相对路径（含文件名）")

    target = resolve(rel_path)
    if target.exists() and target.is_dir():
        raise WorkspaceError(f"目标是目录，不能写入文件：{rel_path}")
    if target.exists() and not overwrite:
        raise WorkspaceError(f"文件已存在：{rel_path}（如需覆盖请显式指定 overwrite=true）")

    data = content.encode("utf-8")
    if len(data) > MAX_WRITE_BYTES:
        raise WorkspaceError(f"内容过大（{len(data)} 字节），上限 {MAX_WRITE_BYTES} 字节")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    root = get_root()
    assert root is not None
    logger.info("已写入文件", path=str(target.relative_to(root)), bytes=len(data))
    return {
        "path": str(target.relative_to(root)).replace("\\", "/"),
        "bytes": len(data),
        "created": True,
    }


def tree(rel_path: str = "", max_depth: int = 2, max_entries: int = 200) -> dict:
    """生成目录树摘要（用于让模型了解文件夹结构）"""
    root = get_root()
    if root is None:
        return {"root": "", "lines": [], "truncated": False}

    lines: list[str] = []
    truncated = False

    def walk(directory: Path, depth: int) -> None:
        nonlocal truncated
        if depth > max_depth or len(lines) >= max_entries:
            truncated = True
            return
        try:
            items = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except (PermissionError, OSError):
            return
        for item in items:
            if item.name in SKIP_DIRS or item.name.startswith("."):
                continue
            if len(lines) >= max_entries:
                truncated = True
                return
            rel = str(item.relative_to(root)).replace("\\", "/")
            if item.is_dir():
                lines.append(f"{rel}/")
                walk(item, depth + 1)
            else:
                try:
                    lines.append(f"{rel}  ({item.stat().st_size} B)")
                except OSError:
                    lines.append(rel)

    start = resolve(rel_path) if rel_path else root
    if start.is_dir():
        walk(start, 1)

    return {"root": str(root), "lines": lines, "truncated": truncated}


def summary_lines() -> list[str]:
    """一行式状态摘要，供模型上下文使用"""
    root = get_root()
    if root is None:
        return []
    info = tree(max_depth=2, max_entries=200)
    head = [f"用户已选择工作文件夹：{root}", "目录结构（最多两层）："]
    return head + info["lines"]
