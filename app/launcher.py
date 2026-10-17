"""GrassSea 单进程启动器

用一个 Python 进程同时运行四个 FastAPI 服务（各自独立的 uvicorn 与端口），
替代 Docker Compose 的多容器形态；四个服务之间仍通过 HTTP 通信，
因此**服务代码零改动**，只有跨服务地址从容器名改写为 127.0.0.1。

设计要点
--------
1. 环境变量必须在导入服务模块**之前**注入：
   各服务在模块顶层执行 settings = get_settings()，读到的是导入时的环境。
2. uvicorn.Server.serve() 默认会安装 SIGINT/SIGTERM 处理器，四个实例互相覆盖，
   因此这里对所有实例关闭自动信号处理，由本模块统一接管并优雅退出。
3. 与 Docker 形态完全并存：本文件不被任何服务导入，删除它也不影响容器部署。

端口（与 Docker 形态一致）
    8004 model_gateway      模型网关
    8003 knowledge_service  知识库（RAG）
    8002 agent_service      智能体编排
    8001 chat_service       对话服务（前端入口）

用法
    uv run python -m app.launcher            # 启动全部服务
    uv run python -m app.launcher --check    # 只做导入与配置自检，不监听端口
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# (名称, ASGI 应用路径, 端口环境变量, 默认端口)
SERVICES: tuple[tuple[str, str, str, int], ...] = (
    ("model_gateway", "services.model_gateway.main:app", "MODEL_GATEWAY_PORT", 8004),
    ("knowledge_service", "services.knowledge_service.main:app", "KNOWLEDGE_SERVICE_PORT", 8003),
    ("agent_service", "services.agent_service.main:app", "AGENT_SERVICE_PORT", 8002),
    ("chat_service", "services.chat_service.main:app", "CHAT_SERVICE_PORT", 8001),
)

# 服务间调用地址 -> 对应服务的名称（容器内是服务名，本机形态必须是回环地址）
INTERNAL_URLS: dict[str, str] = {
    "MODEL_GATEWAY_URL": "model_gateway",
    "AGENT_SERVICE_URL": "agent_service",
    "KNOWLEDGE_SERVICE_URL": "knowledge_service",
}

# 服务名 -> (端口环境变量, 默认端口)
PORT_BY_NAME: dict[str, tuple[str, int]] = {
    name: (env_key, default_port) for name, _path, env_key, default_port in SERVICES
}


def resolve_port(env_key: str, default: int) -> int:
    """读取端口配置，非法值回退到默认值"""
    raw = os.environ.get(env_key, "").strip()
    if not raw:
        return default
    try:
        port = int(raw)
    except ValueError:
        return default
    return port if 1 <= port <= 65535 else default


def prepare_environment() -> dict[str, Any]:
    """在任何服务模块被导入之前准备运行环境

    返回一份便于打印/自检的配置摘要。
    """
    os.chdir(PROJECT_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    # 注意：必须用 resolve_port 解析，否则上层若覆盖了端口，
    # 服务间地址仍指向默认端口，本机形态会连不上。
    for var, service_name in INTERNAL_URLS.items():
        env_key, default_port = PORT_BY_NAME[service_name]
        os.environ.setdefault(var, f"http://127.0.0.1:{resolve_port(env_key, default_port)}")

    # 桌面/本机形态默认使用零依赖的向量后端与项目内数据目录；
    # 显式设置的环境变量优先（例如连本机 Milvus 时设 VECTOR_BACKEND=milvus）。
    os.environ.setdefault("VECTOR_BACKEND", "local")
    os.environ.setdefault("DATA_DIR", str(PROJECT_ROOT / "data"))

    return {
        "VECTOR_BACKEND": os.environ["VECTOR_BACKEND"],
        "DATA_DIR": os.environ["DATA_DIR"],
        "MODEL_GATEWAY_URL": os.environ["MODEL_GATEWAY_URL"],
        "AGENT_SERVICE_URL": os.environ["AGENT_SERVICE_URL"],
        "KNOWLEDGE_SERVICE_URL": os.environ["KNOWLEDGE_SERVICE_URL"],
    }


def import_apps() -> list[tuple[str, Any, int]]:
    """按顺序导入四个 ASGI 应用（导入即触发各服务的模块级初始化）"""
    loaded: list[tuple[str, Any, int]] = []
    for name, path, env_key, default_port in SERVICES:
        module_path, attr = path.split(":")
        module = importlib.import_module(module_path)
        loaded.append((name, getattr(module, attr), resolve_port(env_key, default_port)))
    return loaded


async def serve(
    name: str,
    app: Any,
    port: int,
    servers: dict[str, Any],
    primary: bool,
    verbose: bool = False,
) -> None:
    """在独立 uvicorn 实例上提供服务"""
    import uvicorn

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info" if (primary or verbose) else "warning",
        access_log=False,
        lifespan="on",
    )
    server = uvicorn.Server(config)
    # 统一由本模块处理信号，避免四个实例互相覆盖
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    servers[name] = server
    await server.serve()


async def run(verbose: bool = False, force: bool = False) -> int:
    info = prepare_environment()

    # ---- 启动自检（P0）：失败即中止，不带病启动 ----
    from app.preflight import format_report, run_all

    report = run_all()
    print(format_report(report), flush=True)
    if not report["ok"] and not force:
        return 2

    apps = import_apps()

    banner = [
        "",
        "=" * 68,
        "  白草沧智 GrassSea AI — 单进程运行形态",
        "=" * 68,
        f"  向量后端 : {info['VECTOR_BACKEND']}",
        f"  数据目录 : {info['DATA_DIR']}",
        "-" * 68,
    ]
    for name, _app, port in apps:
        banner.append(f"  {name:<20} http://127.0.0.1:{port}")
    banner += [
        "-" * 68,
        f"  对话入口 : http://127.0.0.1:{next(p for n, _a, p in apps if n == 'chat_service')}",
        "  按 Ctrl+C 停止全部服务",
        "=" * 68,
        "",
    ]
    print("\n".join(banner), flush=True)

    servers: dict[str, Any] = {}
    tasks = [
        asyncio.create_task(
            serve(name, app, port, servers, primary=(name == "chat_service"), verbose=verbose),
            name=name,
        )
        for name, app, port in apps
    ]

    stop = asyncio.Event()

    def _request_stop(*_: Any) -> None:
        stop.set()

    # Windows 的事件循环不支持 loop.add_signal_handler，直接用 signal.signal
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _request_stop)
        except (ValueError, OSError):  # 非主线程等情况
            pass

    # ---- 看护（P0）：任一服务协程意外退出，必须让用户看见 ----
    failed: dict[str, str] = {}

    async def _watchdog() -> None:
        while not stop.is_set():
            await asyncio.sleep(2)
            for task in tasks:
                if not task.done() or stop.is_set():
                    continue
                name = task.get_name()
                if name in failed:
                    continue
                if task.cancelled():
                    failed[name] = "已取消"
                else:
                    exc = task.exception()
                    failed[name] = f"{type(exc).__name__}: {exc}" if exc else "已退出"
                logger.error("服务意外退出", service=name, reason=failed[name])
                print(
                    f"\n[警告] 服务 {name} 意外退出：{failed[name]}"
                    f"（其余服务仍在运行；详细日志见 data/logs/app.log）\n",
                    flush=True,
                )

    watchdog = asyncio.create_task(_watchdog(), name="__watchdog__")
    started = time.time()
    try:
        await stop.wait()
    except asyncio.CancelledError:
        pass
    finally:
        print("\n正在停止服务…", flush=True)
        for server in servers.values():
            server.should_exit = True
        await asyncio.gather(*tasks, return_exceptions=True)
        alive = [t for t in tasks if not t.done()]
        for t in alive:
            t.cancel()
        watchdog.cancel()
        if failed:
            print("运行期间有服务异常退出：" + "、".join(failed.keys()), flush=True)
        print(f"已停止（运行 {time.time() - started:.1f} 秒）", flush=True)

    return 3 if failed else 0


def check() -> int:
    """自检：准备环境 + 导入四个服务 + 打印关键配置，不监听端口"""
    info = prepare_environment()
    print("=" * 68)
    print("  单进程形态自检")
    print("=" * 68)
    for key, value in info.items():
        print(f"  {key:<24} {value}")
    print("-" * 68)

    failures = 0
    for name, path, env_key, default_port in SERVICES:
        module_path, attr = path.split(":")
        port = resolve_port(env_key, default_port)
        try:
            module = importlib.import_module(module_path)
            getattr(module, attr)
            print(f"  [OK]   {name:<20} :{port}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  [FAIL] {name:<20} {type(exc).__name__}: {exc}")

    print("-" * 68)
    print("自检通过" if failures == 0 else f"自检失败：{failures} 个服务无法导入")
    return 0 if failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="grasssea", description="GrassSea 单进程启动器")
    parser.add_argument("--check", action="store_true", help="只做导入与配置自检，不启动服务")
    parser.add_argument("--verbose", action="store_true", help="输出更详细的日志")
    parser.add_argument("--force", action="store_true", help="忽略启动自检失败，强制启动")
    parser.add_argument("--desktop", action="store_true", help="启动服务并打开桌面窗口")
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="配合 --desktop：只启动服务与桌面模式能力，不打开窗口",
    )
    parser.add_argument(
        "--prefer",
        default="auto",
        choices=("auto", "pywebview", "browser-app", "web"),
        help="桌面窗口方式（默认 auto：依次尝试）",
    )
    args = parser.parse_args(argv)

    if args.check:
        return check()

    if args.desktop:
        from app.desktop import main as desktop_main

        forwarded: list[str] = ["--prefer", args.prefer]
        if args.verbose:
            forwarded.append("--verbose")
        if args.no_window:
            forwarded.append("--no-window")
        return desktop_main(forwarded)

    try:
        return asyncio.run(run(verbose=args.verbose, force=args.force))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
