"""GrassSea AI — 结构化日志模块

基于 structlog，JSON 格式输出到控制台。
支持分布式追踪 ID 注入。
"""

from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from contextvars import ContextVar

import structlog

# 分布式追踪上下文变量
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_span_id: ContextVar[str | None] = ContextVar("span_id", default=None)


def add_trace_context(
    logger: structlog.BoundLogger, method_name: str, event_dict: dict
) -> dict:
    """将追踪 ID 注入日志事件"""
    trace_id = _trace_id.get()
    span_id = _span_id.get()
    if trace_id:
        event_dict["trace_id"] = trace_id
    if span_id:
        event_dict["span_id"] = span_id
    return event_dict


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
) -> None:
    """初始化结构化日志系统

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        json_format: 是否使用 JSON 格式输出
    """
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_trace_context,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 降低第三方库日志噪音
    for lib in ("uvicorn", "httpx", "pymongo", "motor", "aiokafka", "pika"):
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """获取结构化日志实例"""
    return structlog.get_logger(name or __name__)


# --- 追踪上下文管理器 ---

@contextmanager
def trace_span(trace_id: str, span_id: str | None = None):
    """设置分布式追踪上下文"""
    t = _trace_id.set(trace_id)
    s = _span_id.set(span_id) if span_id else None
    try:
        yield
    finally:
        _trace_id.reset(t)
        if s is not None:
            _span_id.reset(s)


def set_trace_id(trace_id: str) -> None:
    _trace_id.set(trace_id)


def set_span_id(span_id: str) -> None:
    _span_id.set(span_id)