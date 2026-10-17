"""从备份包恢复 GrassSea 个人数据

用法：
    uv run python scripts/restore.py --list                  # 列出可用备份
    uv run python scripts/restore.py <备份文件>              # 恢复（先自动备份当前状态）
    uv run python scripts/restore.py <备份文件> --dry-run    # 只看会覆盖哪些文件
    uv run python scripts/restore.py <备份文件> --yes        # 跳过确认

安全策略：
  1. 恢复前**自动备份当前状态**，覆盖错了还能退回去；
  2. 默认需要交互确认；
  3. 逐文件校验路径，拒绝 ../ 之类的越界条目。
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


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


def _target_for(name: str) -> Path | None:
    """把备份内的相对路径映射到本机绝对路径"""
    if name.startswith("data/"):
        return _data_dir() / name[len("data/"):]
    if name.startswith("secrets/"):
        return _secrets_dir() / name[len("secrets/"):]
    if name == ".env":
        return PROJECT_ROOT / ".env"
    return None


def list_backups() -> None:
    out = _data_dir() / "backups"
    items = sorted(out.glob("grasssea-backup-*.zip"), reverse=True) if out.exists() else []
    if not items:
        print("未找到任何备份（默认目录 data/backups）")
        return
    print(f"可用备份（{out}）：")
    for f in items:
        print(f"  {f.name}  {f.stat().st_size / 1048576:.1f} MB")


def main() -> int:
    parser = argparse.ArgumentParser(description="从备份恢复 GrassSea 数据")
    parser.add_argument("archive", nargs="?", help="备份 zip 文件路径")
    parser.add_argument("--list", action="store_true", help="列出可用备份")
    parser.add_argument("--dry-run", action="store_true", help="只显示将覆盖的文件")
    parser.add_argument("--yes", action="store_true", help="跳过确认")
    args = parser.parse_args()

    if args.list:
        list_backups()
        return 0

    if not args.archive:
        print("请提供备份文件路径，或使用 --list 查看可用备份。")
        return 1

    archive = Path(args.archive)
    if not archive.exists():
        print(f"❌ 备份文件不存在：{archive}")
        return 1

    try:
        zf = zipfile.ZipFile(archive)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 无法打开备份包：{exc}")
        return 1

    with zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        plan: list[tuple[str, Path]] = []
        skipped: list[str] = []
        for name in names:
            target = _target_for(name)
            if target is None:
                skipped.append(name)
                continue
            # 越界校验
            try:
                target.resolve().relative_to(PROJECT_ROOT.resolve())
            except ValueError:
                skipped.append(name)
                continue
            plan.append((name, target))

        manifest = ""
        if "manifest.json" in names:
            manifest = zf.read("manifest.json").decode("utf-8", errors="replace")

        print(f"备份包：{archive}")
        if manifest:
            import json

            try:
                info = json.loads(manifest)
                print(f"  创建时间：{info.get('created_at', '未知')}")
                print(f"  包含：{'、'.join(info.get('included') or []) or '（未记录）'}")
            except Exception:  # noqa: BLE001
                pass
        print(f"  将恢复 {len(plan)} 个文件，跳过 {len(skipped)} 个")
        for name, target in plan[:20]:
            print(f"    {name}  ->  {target}")
        if len(plan) > 20:
            print(f"    …其余 {len(plan) - 20} 个")

        if args.dry_run:
            print("\n(dry-run，未写入任何文件)")
            return 0

        if not args.yes:
            answer = input("\n确认覆盖恢复？会先自动备份当前数据 [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("已取消。")
                return 1

        # 先备份当前状态
        try:
            from scripts.backup import create_backup

            print("\n先备份当前状态…")
            create_backup()
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️  当前状态备份失败（{exc}）；继续恢复可能导致数据丢失。")
            if not args.yes:
                if input("仍要继续？[y/N] ").strip().lower() not in ("y", "yes"):
                    print("已取消。")
                    return 1

        # 写入
        written = 0
        for name, target in plan:
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(target, "wb") as dst:
                dst.write(src.read())
            written += 1

        print(f"\n✅ 恢复完成：{written} 个文件")
        print("请重启 GrassSea 使数据生效。")
        return 0


if __name__ == "__main__":
    sys.exit(main())
