"""启动自检（preflight）

三件事在启动前必须确认，任何一项失败都**不应带病启动**：

1. **密钥可解密** —— 有加密密钥库但缺少 Fernet 密钥文件，或密钥与密文不匹配时，
   已保存的 LLM API Key 会静默失效（服务照常启动，用户直到某次调用失败才发现）。
2. **数据目录可写** —— data/ 被移到只读位置、磁盘满、权限异常时，
   知识库与文档都会静默写失败。
3. **端口可用** —— 8001-8004 被占用时，uvicorn 启动失败但用户只看到"窗口没反应"。

设计原则：宁可启动失败并给出**可执行的恢复命令**，也不要带病运行。
"""

from __future__ import annotations

import socket
from pathlib import Path

from shared.utils.config import get_settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)

# 与 app/launcher.py 的 SERVICES 保持一致（避免循环导入，这里独立声明）
DEFAULT_PORTS: dict[str, int] = {
    "model_gateway": 8004,
    "knowledge_service": 8003,
    "agent_service": 8002,
    "chat_service": 8001,
}
PORT_ENV_KEYS: dict[str, str] = {
    "model_gateway": "MODEL_GATEWAY_PORT",
    "knowledge_service": "KNOWLEDGE_SERVICE_PORT",
    "agent_service": "AGENT_SERVICE_PORT",
    "chat_service": "CHAT_SERVICE_PORT",
}


def _data_dir() -> Path:
    settings = get_settings()
    configured = (getattr(settings, "DATA_DIR", "") or "").strip()
    return Path(configured) if configured else (settings.PROJECT_ROOT / "data")


# ---------------------------------------------------------------- 密钥

def check_secrets() -> dict:
    """检查密钥文件与加密密钥库是否配套可用"""
    result = {"name": "secrets", "ok": True, "blocking": False, "detail": "", "hints": []}
    try:
        from shared.utils import secrets as secret_mod
    except Exception as exc:  # noqa: BLE001
        result.update(ok=True, detail=f"密钥模块不可用，跳过检查（{exc}）")
        return result

    base = Path(getattr(secret_mod, "_SECRETS_DIR", _data_dir()))
    key_file = Path(getattr(secret_mod, "KEY_FILE", base / ".grasssea_key"))
    sec_file = Path(getattr(secret_mod, "SECRETS_FILE", base / ".grasssea_secrets"))

    has_key = key_file.exists()
    has_secrets = sec_file.exists()

    if not has_key and not has_secrets:
        result.update(detail=f"首次运行，尚无密钥（将自动创建于 {base}）")
        return result

    if has_secrets and not has_key:
        result.update(
            ok=False,
            blocking=True,
            detail=f"检测到加密密钥库 {sec_file.name}，但缺少 Fernet 密钥 {key_file.name}",
            hints=[
                f"已保存的 API Key 无法解密（服务会静默带病运行）。",
                f"请从备份恢复 {key_file}，或删除 {sec_file} 后重新在设置页填写密钥。",
                f"密钥目录：{base}",
            ],
        )
        return result

    if has_key and not has_secrets:
        result.update(detail=f"已有密钥文件 {key_file.name}，尚未保存任何密钥")
        return result

    # 两者都在：实际解密一次，确认能打开
    try:
        loaded = secret_mod.load_secrets()
        result.update(detail=f"密钥可正常解密（已保存 {len(loaded)} 项）")
    except Exception as exc:  # noqa: BLE001
        result.update(
            ok=False,
            blocking=True,
            detail=f"密钥解密失败：{exc}",
            hints=[
                "密钥文件与密钥库不匹配（通常是更换了 .grasssea_key 或拷贝时只带了一个文件）。",
                f"请从备份同时恢复 {key_file.name} 与 {sec_file.name}；",
                f"或在设置页重新填写 API Key（会以当前密钥重新加密）。",
                f"密钥目录：{base}",
            ],
        )
    return result


# ---------------------------------------------------------------- 数据目录

def check_data_dir() -> dict:
    """检查数据目录可写（知识库、日志、文档输出都依赖它）"""
    result = {"name": "data_dir", "ok": True, "blocking": False, "detail": "", "hints": []}
    target = _data_dir()
    probe = target / ".write_probe"
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        result["detail"] = f"数据目录可写：{target}"
    except Exception as exc:  # noqa: BLE001
        result.update(
            ok=False,
            blocking=True,
            detail=f"数据目录不可写：{target}（{exc}）",
            hints=[
                "知识库、日志、文档输出都会写失败。",
                "请确认：目录未被设为只读 / 磁盘未满 / 未被杀毒软件锁定；",
                f"或在 .env 中把 DATA_DIR 指向一个可写目录。",
            ],
        )
    return result


# ---------------------------------------------------------------- 端口

def _port_free(port: int) -> bool:
    """尝试在 127.0.0.1 上绑定，判断端口是否空闲

    ⚠️ 千万不要设 SO_REUSEADDR：在 Windows 上它允许绑定到**已被监听**的端口，
    会让本检查永远返回"空闲"（实测踩过）。此处保持默认行为。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def resolve_port(service: str) -> int:
    """读取某服务的端口（与 launcher 同样的规则）"""
    import os

    env_key = PORT_ENV_KEYS.get(service, "")
    default = DEFAULT_PORTS.get(service, 0)
    raw = (os.environ.get(env_key, "") or "").strip() if env_key else ""
    if not raw:
        return default
    try:
        port = int(raw)
    except ValueError:
        return default
    return port if 1 <= port <= 65535 else default


def check_ports(services: list[str] | None = None) -> dict:
    """检查服务端口是否空闲

    services 为空时检查全部四个端口；合并形态只需检查对话端口，
    否则 8002~8004 被别的程序占用会误报启动失败。
    """
    result = {"name": "ports", "ok": True, "blocking": False, "detail": "", "hints": []}
    targets = services or list(DEFAULT_PORTS)
    busy: list[str] = []
    for service in targets:
        port = resolve_port(service)
        if not _port_free(port):
            busy.append(f"{service}:{port}")

    if not busy:
        result["detail"] = "端口全部空闲：" + "、".join(
            str(resolve_port(s)) for s in targets
        )
        return result

    result.update(
        ok=False,
        blocking=True,
        detail="以下端口已被占用：" + "、".join(busy),
        hints=[
            "很可能是上一次的 GrassSea 进程没有完全退出。",
            "Windows 下可执行：taskkill /F /IM python.exe",
            "或查看占用进程：netstat -ano | findstr :8001",
            "也可以在 .env 中改用其它端口（如 CHAT_SERVICE_PORT=8101），内部服务地址会自动跟随。",
        ],
    )
    return result


# ---------------------------------------------------------------- 汇总

def run_all(services: list[str] | None = None) -> dict:
    """执行全部检查，返回结构化结果

    services 传给端口检查：合并形态只需 ["chat_service"]。
    """
    checks = [check_secrets(), check_data_dir(), check_ports(services)]
    blocking = [c for c in checks if c.get("blocking")]
    warnings = [c for c in checks if not c.get("ok") and not c.get("blocking")]
    return {
        "ok": not blocking,
        "checks": checks,
        "blocking": blocking,
        "warnings": warnings,
    }


def format_report(report: dict) -> str:
    """把检查结果渲染成可直接打印的中文报告"""
    lines: list[str] = []
    lines.append("=" * 68)
    lines.append("  GrassSea 启动自检")
    lines.append("=" * 68)
    icon = {True: "[ OK ]", False: "[FAIL]"}
    for check in report["checks"]:
        state = check.get("ok", True)
        lines.append(f"  {icon[state]} {check['name']:<10} {check.get('detail', '')}")
        for hint in check.get("hints") or []:
            lines.append(f"         → {hint}")
    lines.append("-" * 68)

    if report["ok"]:
        lines.append("  自检通过，可以启动。")
    else:
        lines.append("  自检未通过，已中止启动。请按上面的提示处理后重试。")
        lines.append("")
        lines.append("  如果你确认要继续（例如端口占用只是临时现象），")
        lines.append("  可加 --force 忽略自检结果。")
    lines.append("=" * 68)
    return "\n".join(lines)
