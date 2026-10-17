"""一键备份 GrassSea 的个人数据

桌面形态下真正不可再生的资产：
  1. data/vectorstore/  知识库向量（重新入库要花几十分钟）
  2. data/uploads/      对话附件原件
  3. data/outputs/      生成的 Word / PDF
  4. data/templates/    你手改过的排版模板
  5. secrets/           Fernet 密钥 + 加密后的 API Key（两者必须成对）
  6. .env               端口与开关配置

刻意**不**打包：data/models（向量模型缓存，可重新下载）、data/logs、
data/backups、data/window-profile、__pycache__。

用法：
    uv run python scripts/backup.py                  # 备份到 data/backups/
    uv run python scripts/backup.py --list           # 列出已有备份
    uv run python scripts/backup.py --out D:/bak/    # 指定输出目录
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 需要打包的 data 子目录（相对 data/）
INCLUDE_DATA_DIRS = ["vectorstore", "uploads", "outputs", "templates"]
# data 下不打包的
EXCLUDE_DATA = {"models", "logs", "backups", "window-profile", ".lo-profile"}
# 不打包的文件模式
EXCLUDE_SUFFIX = {".pyc", ".lock", ".tmp"}


def _data_dir() -> Path:
    try:
        from shared.utils.config import get_settings

        s = get_settings()
        configured = (getattr(s, "DATA_DIR", "") or "").strip()
        return Path(configured) if configured else (s.PROJECT_ROOT / "data")
    except Exception:  # noqa: BLE001
        return PROJECT_ROOT / "data"


def _secrets_dir() -> Path:
    try:
        from shared.utils import secrets as m

        return Path(getattr(m, "_SECRETS_DIR", PROJECT_ROOT / "docker-data" / "secrets"))
    except Exception:  # noqa: BLE001
        return PROJECT_ROOT / "docker-data" / "secrets"


def _iter_files(root: Path, skip_dirs: set[str]):
    """遍历目录，跳过指定子目录与临时文件"""
    if not root.exists():
        return
    for item in root.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(root)
        if any(part in skip_dirs for part in rel.parts):
            continue
        if item.suffix in EXCLUDE_SUFFIX:
            continue
        yield item


def create_backup(out_dir: Path | None = None) -> Path:
    data = _data_dir()
    sec = _secrets_dir()
    out = out_dir or (data / "backups")
    out.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = out / f"grasssea-backup-{stamp}.zip"

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_root": str(PROJECT_ROOT),
        "data_dir": str(data),
        "secrets_dir": str(sec),
        "workspace_root_hint": "",
        "included": [],
    }

    added = 0
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1) data 下的关键目录
        for name in INCLUDE_DATA_DIRS:
            src = data / name
            if not src.exists():
                continue
            for f in _iter_files(src, EXCLUDE_DATA | {"__pycache__"}):
                arc = Path("data") / f.relative_to(data)
                zf.write(f, arc.as_posix())
                added += 1
            manifest["included"].append(f"data/{name}")

        # 2) 密钥（必须成对，否则解不开）
        for keyname in (".grasssea_key", ".grasssea_secrets"):
            f = sec / keyname
            if f.exists():
                zf.write(f, f"secrets/{keyname}")
                added += 1
        if (sec / ".grasssea_key").exists():
            manifest["included"].append("secrets/")

        # 3) .env
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            zf.write(env_file, ".env")
            added += 1
            manifest["included"].append(".env")

        # 4) 清单
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        added += 1

    size_mb = target.stat().st_size / 1048576
    print(f"✅ 备份完成：{target}")
    print(f"   文件数 {added} · 大小 {size_mb:.1f} MB")
    print(f"   包含：{'、'.join(manifest['included']) or '（无）'}")
    if not (sec / ".grasssea_key").exists():
        print("⚠️  未找到密钥文件，备份里没有 API Key；恢复后需重新在设置页填写。")
    return target


def list_backups() -> None:
    data = _data_dir()
    out = data / "backups"
    if not out.exists():
        print("尚未创建任何备份。")
        return
    items = sorted(out.glob("grasssea-backup-*.zip"), reverse=True)
    if not items:
        print("尚未创建任何备份。")
        return
    print(f"已有 {len(items)} 个备份（目录 {out}）：")
    for f in items:
        print(f"  {f.name}  {f.stat().st_size / 1048576:.1f} MB")


def main() -> int:
    parser = argparse.ArgumentParser(description="备份 GrassSea 个人数据")
    parser.add_argument("--out", type=str, default="", help="输出目录（默认 data/backups）")
    parser.add_argument("--list", action="store_true", help="只列出已有备份")
    args = parser.parse_args()

    if args.list:
        list_backups()
        return 0
    try:
        create_backup(Path(args.out) if args.out else None)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 备份失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
