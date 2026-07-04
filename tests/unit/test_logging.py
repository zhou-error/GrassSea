"""日志模块单元测试"""

from __future__ import annotations

import pytest

from shared.utils.logging import setup_logging, get_logger, trace_span, set_trace_id, set_span_id


class TestLogging:
    """测试日志系统"""

    def test_setup_logging_json(self) -> None:
        """测试 JSON 格式日志初始化"""
        setup_logging(level="INFO", json_format=True)
        logger = get_logger("test")
        assert logger is not None

    def test_setup_logging_console(self) -> None:
        """测试控制台格式日志初始化"""
        setup_logging(level="DEBUG", json_format=False)
        logger = get_logger("test.console")
        logger.info("test message")

    def test_get_logger(self) -> None:
        """测试获取日志实例"""
        logger1 = get_logger("test.a")
        logger2 = get_logger("test.b")
        assert logger1 is not None
        assert logger2 is not None

    def test_trace_context(self) -> None:
        """测试追踪上下文"""
        with trace_span("trace-123", "span-456"):
            # 验证上下文设置（通过日志输出间接验证）
            logger = get_logger("test.trace")
            logger.info("inside trace context")

    def test_set_trace_id(self) -> None:
        """测试设置追踪 ID"""
        set_trace_id("test-trace-001")
        set_span_id("test-span-001")
        logger = get_logger("test")
        logger.info("with trace ids")
