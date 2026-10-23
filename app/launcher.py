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
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 启动器运行在各服务 setup_logging 之前，用标准库 logger 最安全。
# 注意：这里曾经**没有**定义 logger，而看护协程与合并形态都在用 —— 平时不触发，
# 一旦服务真的挂掉就会 NameError 二次崩溃（实测在合并形态启动时暴露）。
logger = logging.getLogger("grasssea.launcher")

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

# 合并模式（桌面形态）下各服务挂载的路径前缀。
# 对话服务挂在根路径（它要托管前端静态资源与 SPA 兜底路由），必须最后挂载。
MERGED_PREFIX: dict[str, str] = {
    "model_gateway": "/gateway",
    "knowledge_service": "/knowledge",
    "agent_service": "/agent",
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


def prepare_environment(merged: bool = False) -> dict[str, Any]:
    """在任何服务模块被导入之前准备运行环境

    merged=True 时（桌面形态）四个服务合并到**同一个端口**，
    因此服务间地址必须带上挂载前缀，并**强制覆盖**（不能 setdefault，
    否则 .env 里的旧地址会赢）。分体形态（Docker）保持原行为。

    返回一份便于打印/自检的配置摘要。
    """
    os.chdir(PROJECT_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    # 注意：必须用 resolve_port 解析，否则上层若覆盖了端口，
    # 服务间地址仍指向默认端口，本机形态会连不上。
    if merged:
        chat_env, chat_default = PORT_BY_NAME["chat_service"]
        base = f"http://127.0.0.1:{resolve_port(chat_env, chat_default)}"
        for var, service_name in INTERNAL_URLS.items():
            os.environ[var] = f"{base}{MERGED_PREFIX[service_name]}"
    else:
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
    try:
        await server.serve()
    except SystemExit as exc:
        # uvicorn 启动失败时会 sys.exit(3)。SystemExit 在 asyncio 任务里会
        # 终止整个进程，把其余三个服务一起带走。这里转成普通异常，
        # 让看护逻辑记录并只标记这一个服务失败。
        reason = f"启动失败（uvicorn exit {exc.code}）"
        print(
            f"\n[警告] 服务 {name}（端口 {port}）{reason}；其余服务继续运行。\n",
            flush=True,
        )
        raise RuntimeError(reason) from None


def build_merged_app() -> Any:
    """把四个 ASGI 应用挂到一个 FastAPI 上（桌面形态）

    注意挂载顺序：对话服务必须**最后**挂到 "/"，因为它的 SPA 兜底路由
    会吞掉所有未匹配路径；先挂它会让 /agent、/knowledge、/gateway 全部 404。
    """
    from contextlib import AsyncExitStack, asynccontextmanager

    from fastapi import FastAPI

    # 关键：Starlette 的 mount() **不会**调用子应用的 lifespan。
    # 若不手动进入，agent_service 的注册表/工具/意图分类器全都不会初始化，
    # 表现为 /agent/health 正常但 /agents 返回 0（实测踩到）。
    # 这里按 SERVICES 顺序（gateway -> knowledge -> agent -> chat）进入，
    # 退出时逆序关闭。
    sub_apps: list[tuple[str, Any]] = []
    for name, path, _env_key, _default_port in SERVICES:
        module_path, attr = path.split(":")
        sub_apps.append((name, getattr(importlib.import_module(module_path), attr)))

    @asynccontextmanager
    async def merged_lifespan(_app: Any):
        async with AsyncExitStack() as stack:
            for name, sub in sub_apps:
                await stack.enter_async_context(sub.router.lifespan_context(sub))
                logger.info("合并形态：子应用 lifespan 已进入：%s", name)
            yield

    root = FastAPI(
        title="GrassSea (merged)",
        docs_url=None,
        openapi_url=None,
        redoc_url=None,
        lifespan=merged_lifespan,
    )

    for name, sub_app in sub_apps:
        if name == "chat_service":
            continue
        root.mount(MERGED_PREFIX[name], sub_app)

    # 对话服务最后挂到 "/"：它有 SPA 兜底路由，先挂会吞掉上面所有前缀
    for name, sub_app in sub_apps:
        if name == "chat_service":
            root.mount("/", sub_app)
    return root


async def _run_merged(info: dict[str, Any], verbose: bool = False) -> int:
    """桌面形态：单端口单应用，替代原来的四个 uvicorn"""
    import uvicorn

    chat_env, chat_default = PORT_BY_NAME["chat_service"]
    port = resolve_port(chat_env, chat_default)

    app = build_merged_app()

    print("\n".join([
        "",
        "=" * 68,
        "  白草沧智 GrassSea AI — 单进程合并形态（桌面）",
        "=" * 68,
        f"  向量后端 : {info['VECTOR_BACKEND']}",
        f"  数据目录 : {info['DATA_DIR']}",
        "-" * 68,
        f"  对话入口 : http://127.0.0.1:{port}",
        f"  编排服务 : http://127.0.0.1:{port}/agent",
        f"  知识服务 : http://127.0.0.1:{port}/knowledge",
        f"  模型网关 : http://127.0.0.1:{port}/gateway",
        "  按 Ctrl+C 停止",
        "=" * 68,
        "",
    ]), flush=True)

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info" if verbose else "warning",
        access_log=False,
        lifespan="on",
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]

    stop = asyncio.Event()

    def _request_stop(*_: Any) -> None:
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _request_stop)
        except (ValueError, OSError):
            pass

    task = asyncio.create_task(server.serve(), name="merged")
    started = time.time()
    try:
        # 合并形态只有一个进程：它退出就等于整体退出，无需看护多个服务
        while not stop.is_set():
            if task.done():
                exc = None if task.cancelled() else task.exception()
                reason = f"{type(exc).__name__}: {exc}" if exc else "已退出"
                print(f"\n[错误] 服务已退出：{reason}\n", flush=True)
                logger.error("合并形态服务退出：%s", reason)
                return 3
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass
    finally:
        print("\n正在停止服务…", flush=True)
        server.should_exit = True
        try:
            await asyncio.wait_for(task, timeout=10)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()
        print(f"已停止（运行 {time.time() - started:.1f} 秒）", flush=True)
    return 0


async def run(verbose: bool = False, force: bool = False, merged: bool = True) -> int:
    info = prepare_environment(merged=merged)

    # ---- 启动自检（P0）：失败即中止，不带病启动 ----
    from app.preflight import format_report, run_all

    # 合并形态只监听对话端口，检查全部四个会误报
    report = run_all(["chat_service"] if merged else None)
    print(format_report(report), flush=True)
    if not report["ok"] and not force:
        return 2

    if merged:
        return await _run_merged(info, verbose=verbose)

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
                logger.error("服务意外退出：%s（%s）", name, failed[name])
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


async def _lifespan_smoke(apps: list[tuple[str, Any, int]]) -> int:
    """逐个跑一次 lifespan 的 startup + shutdown

    导入成功不代表能启动：曾发生过 @asynccontextmanager 被顶掉，
    导入全绿但实际启动 TypeError 的事故。这里用最小代价把这类问题
    挡在 --check 阶段，而不是等用户双击时黑窗闪退。
    """
    failures = 0
    for name, app, port in apps:
        try:
            lifespan = app.router.lifespan_context
        except AttributeError:
            print(f"  [SKIP] {name:<20} :{port} 无 lifespan")
            continue
        try:
            async with lifespan(app):
                pass
            print(f"  [OK]   {name:<20} :{port} lifespan")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  [FAIL] {name:<20} :{port} lifespan {type(exc).__name__}: {exc}")
    return failures


def check() -> int:
    """自检：准备环境 + 导入四个服务 + 跑一次 lifespan + 打印关键配置，不监听端口"""
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

    # ---- lifespan 冒烟（导入通过后再跑，避免掩盖导入错误）----
    if failures == 0:
        print("-" * 68)
        try:
            apps = import_apps()
            failures += asyncio.run(_lifespan_smoke(apps))
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  [FAIL] 无法构建应用实例 {type(exc).__name__}: {exc}")

    print("-" * 68)
    print("自检通过" if failures == 0 else f"自检失败：{failures} 项问题")
    return 0 if failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="grasssea", description="GrassSea 单进程启动器")
    parser.add_argument("--check", action="store_true", help="只做导入与配置自检，不启动服务")
    parser.add_argument("--verbose", action="store_true", help="输出更详细的日志")
    parser.add_argument("--force", action="store_true", help="忽略启动自检失败，强制启动")
    parser.add_argument(
        "--split",
        action="store_true",
        help="桌面形态下改为四端口分体启动（默认合并为单端口；用于回滚与排障）",
    )
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
        if args.split:
            forwarded.append("--split")
        return desktop_main(forwarded)

    try:
        return asyncio.run(run(verbose=args.verbose, force=args.force, merged=not args.split))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
