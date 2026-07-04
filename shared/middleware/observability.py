"""可观测性中间件 — OpenTelemetry 自动埋点 + Prometheus 指标"""

from __future__ import annotations

import time
from contextvars import ContextVar

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from shared.utils.logging import get_logger, set_trace_id

logger = get_logger(__name__)

request_count = ContextVar("http_request_count", default=0)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """全链路追踪 + 指标采集中间件"""

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id", f"tr_{int(time.time() * 1000)}")
        set_trace_id(trace_id)

        start = time.time()
        response = await call_next(request)
        elapsed_ms = (time.time() - start) * 1000

        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Response-Time-Ms"] = str(round(elapsed_ms, 1))

        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=round(elapsed_ms, 1),
            trace_id=trace_id,
        )

        return response


def setup_observability(app: FastAPI) -> None:
    """配置 OpenTelemetry 自动埋点"""
    app.add_middleware(ObservabilityMiddleware)

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        try:
            otlp = OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
            provider.add_span_processor(BatchSpanProcessor(otlp))
        except Exception:
            pass

        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry instrumentation enabled")
    except ImportError:
        logger.warning("OpenTelemetry not available, skipping instrumentation")


@app_metrics = None  # Placeholder for Prometheus metrics endpoint
