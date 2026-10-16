# 01 - OpenTelemetry 埋点

> ⚠️ **范围说明（项目定位：个人使用）**
>
> 本章讲解的集群部署 / CI/CD / 可观测性属于通用工程知识，**当前项目不包含这部分能力**：
> 相关流水线与部署清单已从仓库移除，对应容器配置也已从 `docker-compose.yml` 移除。
> 本章可作为学习资料阅读，但无需在本项目中落地。

## 学习目标

1. 理解分布式追踪（Distributed Tracing）的核心概念：Trace、Span
2. 掌握 OpenTelemetry 在 FastAPI 中的自动埋点方法
3. 理解 Trace ID 在微服务间传递的机制
4. 能够解读一次请求的完整调用链路

## 前置知识

- 基础 Python（装饰器、async/await）
- 了解 FastAPI 中间件的工作原理（参考阶段十第4章）
- 了解什么是微服务架构（一个请求可能需要经过多个服务）

## 概念讲解

### 为什么需要分布式追踪？

在单体应用中，调试很容易——所有代码在一个进程里，看日志就行。但在微服务架构中，一个用户请求可能经过 3-5 个不同的服务。当某次请求变慢或出错时，你怎么知道是哪个服务的问题？

```
微服务架构中的"盲区"：

  用户请求
     │
     ▼
  ┌──────────┐   HTTP    ┌──────────┐   gRPC    ┌──────────┐
  │ 前端      │─────────▶│ 对话服务   │─────────▶│ 知识库服务 │
  │ :5173    │          │ :8001    │          │ :8003    │
  └──────────┘          └────┬─────┘          └────┬─────┘
                             │                     │
                             │ HTTP                │ 调用 Milvus
                             ▼                     ▼
                        ┌──────────┐          ┌──────────┐
                        │ 模型网关   │          │  Milvus  │
                        │ :8004    │          │ :19530   │
                        └──────────┘          └──────────┘

  问题: 请求在"对话服务"等了 200ms，到底是在等"模型网关"还是"知识库服务"？
  没有统一追踪 → 只能逐个服务翻日志，效率极低。
```

### Trace 和 Span 的概念

OpenTelemetry 使用两个核心概念来描述一次请求的生命周期：

```
Trace (追踪) = 一次完整请求的"故事"
Span  (片段) = 故事中的每一个"章节"

  Trace: "用户查询散货船规范"（完整请求）
  ┌─────────────────────────────────────────────────────────┐
  │                                                          │
  │  Span 1: 对话服务接收请求          [0ms ─────── 350ms]   │
  │    │                                                     │
  │    ├── Span 2: 调用知识库服务检索  [10ms ─── 200ms]     │
  │    │     ├── Span 3: Milvus 向量检索 [15ms ── 50ms]    │
  │    │     ├── Span 4: PostgreSQL 查元数据 [50ms ─ 80ms]  │
  │    │     └── Span 5: 重排序          [80ms ── 180ms]    │
  │    │                                                     │
  │    └── Span 6: 调用模型网关生成回答 [200ms ── 340ms]    │
  │          └── Span 7: DeepSeek API  [210ms ─ 330ms]      │
  │                                                          │
  └─────────────────────────────────────────────────────────┘

  Trace ID: abc-123  (贯穿所有 Span，是"故事的名字")
  Span ID:  各有不同 (每个 Span 有自己的 ID)
  Parent Span ID: 指向上层 Span (建立父子关系)
```

### Trace ID 的传播机制

Trace ID 如何从一个服务传到另一个服务？通过 HTTP 请求头！

```
  服务A                                   服务B
  ┌────────────────┐                    ┌────────────────┐
  │ trace_id=abc   │                    │ 接收请求头:     │
  │                │   HTTP Request     │ X-Trace-Id: abc │
  │ 提取:           │──────────────────▶│                 │
  │ X-Trace-Id: abc│   (在请求头中携带)  │ 继续使用 abc    │
  │                │                    │ 记录自己的 Span │
  └────────────────┘                    └────────────────┘

  所有服务用同一个 Trace ID → 日志中可以串联 → "拼图完成"
```

## 项目代码精讲

GrassSea 的可观测性代码在 `shared/middleware/observability.py`。

### ObservabilityMiddleware 自定义中间件

```python
# shared/middleware/observability.py 第18-41行
class ObservabilityMiddleware(BaseHTTPMiddleware):
    """全链路追踪 + 指标采集中间件"""

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id",
                        f"tr_{int(time.time() * 1000)}")
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
```

**逐段解析**：

1. `trace_id = request.headers.get("X-Trace-Id", f"tr_{int(time.time() * 1000)}")` — 从请求头中读取上游传入的 Trace ID。如果请求头中没有（说明这是调用链的起点），则自动生成一个。格式 `tr_` 前缀 + 毫秒时间戳，确保大概率唯一。

2. `set_trace_id(trace_id)` — 将 Trace ID 注入到当前线程的上下文变量（ContextVar）中。这样同一请求内的所有代码（包括日志输出）都能自动获取到这个 ID。

3. `start = time.time()` — 记录请求开始的时间戳，用于计算耗时。

4. `response = await call_next(request)` — 调用后续中间件和业务逻辑。这是洋葱模型的核心。

5. `elapsed_ms = (time.time() - start) * 1000` — 计算请求处理总耗时（毫秒）。

6. `response.headers["X-Trace-Id"] = trace_id` — **关键**：将 Trace ID 写入响应头，这样调用方也能追踪到这个 Trace ID。

7. `response.headers["X-Response-Time-Ms"]` — 返回响应耗时，方便前端直接获取。

8. 日志中包含 `latency_ms` 和 `trace_id`，后续可以通过这些信息在日志系统中搜索和统计。

### OpenTelemetry SDK 初始化

```python
# shared/middleware/observability.py 第44-68行
def setup_observability(app: FastAPI) -> None:
    """配置 OpenTelemetry 自动埋点"""
    app.add_middleware(ObservabilityMiddleware)

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export \
            import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.instrumentation.fastapi \
            import FastAPIInstrumentor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter \
            import OTLPSpanExporter

        provider = TracerProvider()
        provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter()))

        try:
            otlp = OTLPSpanExporter(
                endpoint="http://localhost:4318/v1/traces")
            provider.add_span_processor(BatchSpanProcessor(otlp))
        except Exception:
            pass

        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        logger.warning(
            "OpenTelemetry not available, skipping instrumentation")
```

**逐段解析**：

1. 先注册自定义的 `ObservabilityMiddleware`（总是启用）。

2. `try: ... except ImportError:` — OpenTelemetry 是可选的依赖。如果未安装（如轻量部署场景），跳过自动埋点，只保留自定义中间件的基本追踪功能。这种"优雅降级"是工程上的良好实践。

3. `TracerProvider()` — 创建一个 Tracer 提供者。Tracer 是 OpenTelemetry 的核心对象，负责创建 Span 和管理 Span 的导出。

4. `BatchSpanProcessor(ConsoleSpanExporter())` — 批量处理器 + 控制台导出器。Span 会先缓存起来，攒够一批再导出（避免每个 Span 都单独发送，提升性能）。控制台导出器把 Span 打印到 stdout，方便开发调试。

5. `OTLPSpanExporter(endpoint="...")` — OTLP 是 OpenTelemetry 的标准传输协议。这里配置了一个 OTLP 导出器，把 Span 发送到本地的 OpenTelemetry Collector（用于转发到 Jaeger/Zipkin 等后端）。

6. `FastAPIInstrumentor.instrument_app(app)` — **自动埋点**。这一行代码自动为所有 FastAPI 路由添加 Span，记录每个端点的调用耗时和状态。无需手动添加任何代码。

### Trace ID 与日志的集成

在 `shared/utils/logging.py` 中，`add_trace_context` 函数将 ContextVar 中的 trace_id 自动注入到每条日志中：

```python
# shared/utils/logging.py 第21-31行
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
```

这意味着你在任何地方调用 `logger.info(...)`，日志自动带上 trace_id——不需要手动传递。

## 手把手实践

### 实验一：观察 Trace ID

1. 启动一个 GrassSea 服务（如 model_gateway）
2. 发送一个请求：`curl -v http://localhost:8004/health`
3. 观察响应头中的 `X-Trace-Id` 和 `X-Response-Time-Ms`
4. 查看控制台日志输出，搜索该 Trace ID，观察同一请求的所有日志

### 实验二：模拟分布式追踪

1. 启动两个服务（如 model_gateway 和 chat_service）
2. 从前端发起一个对话请求
3. 在两个服务的日志中搜索相同的 Trace ID
4. 理解这个 ID 是如何跨越服务边界传播的

## 视频学习资源

请在 B站（bilibili.com）搜索以下关键词：

- "OpenTelemetry 分布式追踪 入门" -- 了解 OTel 的核心概念
- "Jaeger 分布式追踪 搭建" -- 学习追踪后端可视化
- "微服务 可观测性 三支柱" -- 了解 Logs/Metrics/Traces 的关系
- "ContextVar Python 上下文变量" -- 理解 Trace ID 如何在异步代码中传递

## 常见问题与排错

**Q1：Trace ID 在异步代码中能正确传递吗？**

A：能。`ContextVar` 是 Python 3.7+ 引入的机制，专为异步编程设计。它与 `asyncio.Task` 绑定，每个 Task 有自己独立的上下文，不会互相干扰。比传统的 `threading.local` 更适合 async/await 场景。

**Q2：为什么既有自定义中间件又用 OpenTelemetry？**

A：自定义中间件提供基本的追踪能力（Trace ID 传播 + 耗时记录），不需要额外依赖。OpenTelemetry 提供更丰富的功能（自动 Span 创建、与 Jaeger 等后端集成、标准化的导出格式）。两者互补。

**Q3：`BatchSpanProcessor` 缓冲会不会丢数据？**

A：在进程正常退出时会 flush 缓冲区。但如果进程被 kill -9 强制终止，缓冲区中的 Span 会丢失。对于生产环境，可以设置更小的 batch size 或使用同步导出器。

## 练习任务

1. **概念题**：什么是 Trace？什么是 Span？它们之间是什么关系？
2. **代码题**：在 `ObservabilityMiddleware` 的基础上，增加一个功能——如果请求耗时超过 1000ms，在日志中额外记录一个 `slow_request: true` 标记。
3. **思考题**：如果一个请求经过了 5 个微服务，所有服务都打印了日志，你如何快速定位是哪个服务响应慢？请描述你的排查步骤。
4. **扩展题**：阅读 `shared/utils/logging.py` 中的 `trace_span` 上下文管理器，理解它是如何通过 try/finally 确保 trace_id 在代码块结束后被清理的。
