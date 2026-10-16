"""GrassSea 桌面窗口

把单进程服务包装成一个桌面应用窗口。采用**分级策略**，按可用性依次尝试：

1. PyWebView（嵌入窗口，最接近原生应用）
   需要 WebView2 运行时 + pythonnet 能加载 .NET。
   已知问题：pywebview 自带的 Microsoft.Web.WebView2.WinForms.dll 目标是
   .NET Framework 4.6.2，与 pythonnet 的 coreclr 模式不兼容；而 netfx 模式在
   部分机器上无法加载 Python.Runtime。任一环节不可用即自动降级到方案 2。
2. Edge/Chrome 的 --app 模式（无地址栏、无标签页的独立窗口，独立任务栏图标）
   零额外依赖，Windows 10/11 必装 Edge，实测稳定。
3. 系统默认浏览器

无论走哪条路径，后端都是同一个本机服务，功能完全一致。
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 常见浏览器可执行文件位置（按优先级）
BROWSER_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


def find_browser() -> str | None:
    """定位可用于 --app 模式的 Chromium 系浏览器"""
    for path in BROWSER_CANDIDATES:
        if Path(path).exists():
            return path
    for name in ("msedge.exe", "chrome.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def wait_for_backend(url: str, timeout: float = 60.0) -> bool:
    """等待后端就绪（避免窗口先于服务打开而显示连接失败）"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.6)
    return False


def launch_browser_app(
    url: str, profile_dir: Path, width: int = 1440, height: int = 920
) -> subprocess.Popen | None:
    """以 --app 模式启动无边框窗口"""
    browser = find_browser()
    if not browser:
        return None
    try:
        profile_dir.mkdir(parents=True, exist_ok=True)
    except Exception:  # noqa: BLE001
        pass
    args = [
        browser,
        f"--app={url}",
        f"--window-size={width},{height}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate,OptimizationHints",
    ]
    try:
        return subprocess.Popen(args, close_fds=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[desktop] 启动浏览器窗口失败：{exc}")
        return None


def try_pywebview(url: str, title: str, width: int, height: int) -> bool:
    """尝试用 PyWebView 打开嵌入窗口；不可用时返回 False"""
    try:
        import webview  # type: ignore

        webview.create_window(title, url, width=width, height=height, min_size=(1024, 680))
        webview.start()          # 阻塞直到窗口关闭
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[desktop] PyWebView 不可用（{type(exc).__name__}: {str(exc)[:120]}），改用备用窗口")
        return False


def open_in_browser(url: str) -> None:
    """兜底：用系统默认浏览器打开"""
    import webbrowser

    webbrowser.open(url)


def run(
    url: str,
    title: str = "白草沧智 GrassSea AI",
    width: int = 1440,
    height: int = 920,
    prefer: str = "auto",
) -> str:
    """打开桌面窗口，返回实际使用的方式

    prefer: auto | pywebview | browser-app | web
    """
    if not wait_for_backend(url, timeout=60.0):
        print("[desktop] 后端未在 60 秒内就绪，仍尝试打开窗口")

    if prefer in ("auto", "pywebview") and try_pywebview(url, title, width, height):
        return "pywebview"

    if prefer in ("auto", "browser-app"):
        proc = launch_browser_app(url, PROJECT_ROOT / "data" / "window-profile", width, height)
        if proc is not None:
            return "browser-app"

    open_in_browser(url)
    return "web"


def _profile_in_use(profile_dir: Path) -> bool:
    """判断 --app 窗口是否仍在运行（按命令行里的专用 profile 路径匹配）

    查询失败时保守地返回 True，避免误判为"窗口已关闭"而提前退出。
    """
    marker = str(profile_dir).lower()
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe' or Name='chrome.exe'\" "
        "| Select-Object -ExpandProperty CommandLine"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=25,
        )
        return marker in (out.stdout or "").lower()
    except Exception:  # noqa: BLE001
        return True


def main(argv: list[str] | None = None) -> int:
    """桌面应用入口：启动后端服务 → 打开窗口 → 窗口关闭后退出"""
    import argparse

    parser = argparse.ArgumentParser(prog="grasssea-desktop", description="GrassSea 桌面版")
    parser.add_argument("--no-window", action="store_true", help="只启动服务，不打开窗口")
    parser.add_argument("--prefer", default="auto", choices=("auto", "pywebview", "browser-app", "web"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    os.environ["DESKTOP_MODE"] = "true"

    from app import launcher

    port = launcher.resolve_port("CHAT_SERVICE_PORT", 8001)
    url = f"http://127.0.0.1:{port}"

    services = threading.Thread(
        target=lambda: asyncio.run(launcher.run(verbose=args.verbose)),
        name="grasssea-services",
        daemon=True,
    )
    services.start()

    if args.no_window:
        print(f"[desktop] 服务已启动（无窗口模式）：{url}", flush=True)
        try:
            while services.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        return 0

    mode = run(url, prefer=args.prefer)
    print(f"[desktop] 窗口方式：{mode}", flush=True)

    if mode == "browser-app":
        profile = PROJECT_ROOT / "data" / "window-profile"
        # 窗口关闭后自动退出；最多等待 12 小时，避免异常情况下永远不退出
        deadline = time.monotonic() + 12 * 3600
        while time.monotonic() < deadline:
            time.sleep(4)
            if not _profile_in_use(profile):
                break
    elif mode == "web":
        print("[desktop] 已用默认浏览器打开；按 Ctrl+C 结束服务", flush=True)
        try:
            while services.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    print("[desktop] 正在退出…", flush=True)
    return 0
