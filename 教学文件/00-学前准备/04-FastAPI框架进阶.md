# FastAPI 框架进阶 — 从路由到实时通信

## 学习目标

- 理解 FastAPI 应用生命周期（lifespan）及其用途
- 掌握中间件机制（CORS、自定义中间件）
- 学会使用 `Depends` 进行依赖注入
- 能编写 WebSocket 端点和 SSE 流式响应
- 理解路由分组 `include_router` 的模块化设计

## 前置知识

- FastAPI 基础知识（路由定义、请求体、路径参数）
- Python 异步编程（`async`/`await`、`asyncio`）
- Pydantic 数据模型基础
- 完成前三篇教学文件的学习

---

## 1. 概念讲解

### 1.1 为什么需要这些进阶特性？

基础 FastAPI 教程通常只讲到"定义路由 → 返回数据"。但在真实项目中：

1. **应用启动时需要初始化**：连接数据库、加载模型、注册智能体 -- 这些不能写在请求里
2. **每个请求前后需要处理**：验证身份、记录日志、添加安全 Header -- 这是中间件的工作
3. **服务间共享资源**：数据库会话、配置对象 -- 依赖注入就是解决这个的
4. **实时通信**：推送任务进度、流式输出 AI 回复 -- 需要 WebSocket 和 SSE

这些就是 FastAPI "进阶"要解决的问题。

### 1.2 核心概念全景图

```
                    ┌─────────────────────────┐
       请求进入 ──▶  │   CORS 中间件            │  ← 允许跨域
                    │   SecurityHeadersMiddleware│  ← 添加安全头
                    │   AuditMiddleware        │  ← 记录审计日志
                    └──────────┬──────────────┘
                               │
                               ▼
                    ┌─────────────────────────┐
                    │   路由匹配                │
                    │   /chat → proxy_chat    │
                    │   /rag/query → proxy_rag│
                    │   /ws/{id} → websocket  │
                    └──────────┬──────────────┘
                               │
                               ▼
                    ┌─────────────────────────┐
                    │   依赖注入 (Depends)      │  ← db session, config
                    │   get_pg_session()      │
                    │   get_settings()        │
                    └──────────┬──────────────┘
                               │
                               ▼
                    ┌─────────────────────────┐
                    │   路由处理函数            │
                    │   async def chat(...)   │
                    └─────────────────────────┘
```

---

## 2. 项目代码精讲

> 🔗 **参考文件**：`services/chat_service/main.py`、`services/agent_service/main.py`、`services/model_gateway/main.py`、`shared/middleware/security.py`

### 2.1 应用生命周期（lifespan）

打开 `services/model_gateway/main.py` 第33-49行：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    global model_router, token_tracker
    setup_logging(level="DEBUG" if settings.APP_DEBUG else "INFO")
    logger.info("Model Gateway starting...")

    # ===== 启动阶段 =====
    model_router = ModelRouter(settings)
    await model_router.initialize()        # 初始化模型路由器（加载配置、预热连接）

    token_tracker = TokenTracker()          # 初始化 Token 追踪器

    logger.info("Model Gateway started", port=settings.MODEL_GATEWAY_PORT)

    # ===== yield: 分界线 =====
    yield
    # ===== 关闭阶段 =====

    logger.info("Model Gateway shutting down...")
    if model_router:
        await model_router.close()          # 优雅关闭 HTTP 连接

app = FastAPI(
    title="GrassSea Model Gateway",
    version="0.1.0",
    lifespan=lifespan,    # ← 注入生命周期管理器
)
```

`yield` 之前 -- FastAPI 启动时执行（初始化）
`yield` 之后 -- FastAPI 关闭时执行（清理资源）

> 💡 **提示**：GrassSea 的三个服务都用了 `@asynccontextmanager` + `lifespan` 模式。这是 FastAPI 推荐的做法（替代旧版的 `@app.on_event("startup")` 和 `@app.on_event("shutdown")`）。

对比 `services/agent_service/main.py` 的 lifespan，可以看到它初始化了更多组件：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global intent_classifier, task_planner, agent_registry, task_executor
    setup_logging(...)
    # 初始化四个核心组件
    intent_classifier = IntentClassifier(settings)
    task_planner = TaskPlanner(settings)
    agent_registry = AgentRegistry()
    task_executor = TaskExecutor(settings, agent_registry)
    await agent_registry.initialize()
    await intent_classifier.initialize()
    yield
```

### 2.2 中间件机制

#### CORS 中间件

打开 `services/chat_service/main.py` 第40-46行：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

CORS（跨域资源共享）是浏览器的安全机制。前端（React 跑在 `localhost:5173`）请求后端（FastAPI 跑在 `localhost:8001`）时，浏览器会阻止跨域请求。CORS 中间件告诉浏览器："这些来源的请求是合法的"。

参数解释：
- `allow_origins`：允许哪些域名访问（生产环境应限制为实际域名）
- `allow_credentials`：是否允许携带 Cookie/Authorization header
- `allow_methods`：允许的 HTTP 方法
- `allow_headers`：允许的请求头

#### 自定义中间件

打开 `shared/middleware/security.py` 第68-83行：

```python
from starlette.middleware.base import BaseHTTPMiddleware

class AuditMiddleware(BaseHTTPMiddleware):
    """审计日志 — 记录所有 API 调用"""

    async def dispatch(self, request: Request, call_next):
        # 1. 请求前处理（这里不需要）
        response = await call_next(request)   # 2. 调用下一个处理器
        # 3. 响应后处理 — 记录审计信息
        logger.info(
            "audit_log",
            method=request.method,        # GET / POST / ...
            path=request.url.path,        # /chat /rag/query ...
            status=response.status_code,  # 200 / 404 / 500 ...
            ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("User-Agent", ""),
        )
        return response
```

`call_next(request)` 是关键的"传递"调用，它把请求交给下一个中间件或最终的路由处理器。在它之前是"请求前处理"，之后是"响应后处理"。

同一个文件还定义了安全 Header 中间件（第88-98行）：

```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
```

**中间件的执行顺序**：按照 `add_middleware` 的调用顺序反向执行（洋葱模型）。先添加的先包裹外层，后添加的在更内层。

### 2.3 依赖注入（Depends）

在 `shared/models/database.py` 中定义了一个标准的依赖注入函数：

```python
async def get_pg_session() -> AsyncGenerator[AsyncSession, None]:
    """获取 PostgreSQL 异步会话 (用于 FastAPI 依赖注入)"""
    async with pg_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

在路由中使用：

```python
@app.get("/projects")
async def list_projects(session: AsyncSession = Depends(get_pg_session)):
    result = await session.execute(select(Project))
    return result.scalars().all()
```

`Depends(get_pg_session)` 做了以下事情：
1. FastAPI 调用 `get_pg_session()`，获得异步生成器
2. 执行到 `yield`，把 `session` 对象注入到 `list_projects` 的 `session` 参数
3. 路由函数执行完毕后，回到生成器执行 `commit()` 或 `rollback()`

### 2.4 WebSocket 端点

打开 `services/agent_service/main.py` 第196-213行：

```python
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket 连接 — 实时推送任务进度和流式输出"""
    # 1. 接受连接
    await websocket.accept()
    active_connections[session_id] = websocket
    logger.info("WebSocket connected", session_id=session_id)

    try:
        # 2. 持续接收消息
        while True:
            data = await websocket.receive_text()
            import json
            msg = json.loads(data)
            if msg.get("action") == "cancel":
                await task_executor.cancel_task(msg.get("task_id"))
    except WebSocketDisconnect:
        # 3. 客户端断开
        logger.info("WebSocket disconnected", session_id=session_id)
    finally:
        # 4. 清理
        active_connections.pop(session_id, None)
```

WebSocket 的特点：
- **持久连接**：连接一旦建立就保持打开，不像 HTTP 请求-响应就关闭
- **双向通信**：服务器可以主动推送数据给客户端
- **适用场景**：实时通知、任务进度、聊天消息

在 GrassSea 中，WebSocket 用于：
- 实时推送智能体任务执行进度
- 流式输出 LLM 生成内容到前端
- 接收客户端指令（如取消任务）

### 2.5 StreamingResponse (SSE)

打开 `services/model_gateway/main.py` 第213-222行：

```python
if request.stream:
    return StreamingResponse(
        _stream_response(request, route_result, trace_id, start_time),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Trace-Id": trace_id,
        },
    )
```

SSE（Server-Sent Events）是一种基于 HTTP 的服务器推送技术：

```python
async def _stream_response(request, route_result, trace_id, start_time):
    """流式响应生成器 (SSE)"""
    try:
        # 逐块生成内容
        async for chunk in model_router.complete_stream(route_result):
            content = chunk.get("content", "")
            if content:
                data = {"id": f"chatcmpl-{trace_id}", "choices": [...]}
                yield f"data: {__import__('json').dumps(data)}\n\n"

        # 最终帧
        yield "data: [DONE]\n\n"
    except Exception as e:
        error_data = {"error": {"message": str(e)}}
        yield f"data: {__import__('json').dumps(error_data)}\n\n"
        yield "data: [DONE]\n\n"
```

SSE 的格式：每条消息以 `data:` 开头，以两个换行 `\n\n` 结尾。`StreamingResponse` 配合 `media_type="text/event-stream"` 告诉浏览器这是 SSE 流。

**为什么用 SSE 而不是 WebSocket 来流式输出？**

| 特性 | SSE | WebSocket |
|------|-----|-----------|
| 方向 | 单向（服务器→客户端） | 双向 |
| 协议 | HTTP（兼容性好） | 独立协议（ws:// 需升级） |
| 自动重连 | 浏览器内置 | 需手动实现 |
| 适用场景 | AI 流式输出、通知 | 聊天、实时协作 |

对于 LLM 逐字输出这种场景，SSE 简单、标准、够用。

### 2.6 路由分组（include_router）

打开 `services/chat_service/main.py` 第49行：

```python
from services.chat_service.config_api import router as config_router

app.include_router(config_router)
```

`include_router` 将其他模块中定义的路由**挂载**到主应用上。例如 `config_api.py` 中可能有：

```python
router = APIRouter(prefix="/config", tags=["配置管理"])

@router.get("/models")
async def get_models():
    ...

@router.post("/apikeys")
async def update_api_keys():
    ...
```

挂载后，这些路由的实际路径就是 `/config/models` 和 `/config/apikeys`。

**好处**：
- 按功能模块拆分母版文件（如 `config_api.py`、`auth_api.py`）
- 避免主文件 `main.py` 变得太长
- 可以设置统一的 `prefix`、`tags`、`dependencies`

---

## 3. 手把手实践

### 3.1 创建带生命周期的应用

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

# 模拟的"数据库"
fake_db = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：加载初始数据
    fake_db["users"] = {"alice": "工程师", "bob": "设计师"}
    print(f"应用启动，加载了 {len(fake_db['users'])} 个用户")
    yield
    # 关闭：保存数据
    print(f"应用关闭，当前有 {len(fake_db['users'])} 个用户")
    fake_db.clear()

app = FastAPI(lifespan=lifespan)

@app.get("/users")
async def get_users():
    return fake_db.get("users", {})

@app.post("/users/{name}")
async def add_user(name: str, role: str):
    fake_db["users"][name] = role
    return {"message": f"添加用户 {name} 成功"}
```

### 3.2 编写自定义中间件

```python
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import time

class TimingMiddleware(BaseHTTPMiddleware):
    """记录每个请求的处理时间"""

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed = (time.time() - start) * 1000
        response.headers["X-Process-Time-ms"] = f"{elapsed:.2f}"
        print(f"[{request.method}] {request.url.path} → {response.status_code} ({elapsed:.1f}ms)")
        return response

# 添加中间件（必须在所有路由之前）
app.add_middleware(TimingMiddleware)
```

### 3.3 编写 SSE 流式端点

```python
import asyncio
from fastapi.responses import StreamingResponse

async def number_generator(count: int):
    """模拟逐步生成数据"""
    for i in range(1, count + 1):
        await asyncio.sleep(0.5)  # 模拟耗时操作
        yield f"{i}\n"

@app.get("/stream/chunks")
async def stream_data():
    return StreamingResponse(
        number_generator(5),
        media_type="text/plain",
    )
```

访问 `http://localhost:8000/stream/chunks`，你会看到数字逐行出现，而不是等 2.5 秒后一次性返回。

---

## 4. 视频学习资源

在 B站搜索以下关键词：

- [B站搜索: FastAPI 进阶教程 lifespan 中间件](https://search.bilibili.com/all?keyword=FastAPI+进阶教程+lifespan+中间件) -- 生命周期与中间件
- [B站搜索: FastAPI WebSocket 实时通信](https://search.bilibili.com/all?keyword=FastAPI+WebSocket+实时通信) -- WebSocket 端点
- [B站搜索: FastAPI StreamingResponse SSE](https://search.bilibili.com/all?keyword=FastAPI+StreamingResponse+SSE) -- 流式响应
- [B站搜索: FastAPI 依赖注入 Depends](https://search.bilibili.com/all?keyword=FastAPI+依赖注入+Depends) -- 依赖注入

> 💡 **提示**：FastAPI 官方文档的 Advanced User Guide（https://fastapi.tiangolo.com/advanced/）涵盖了所有这些进阶特性，是最权威的参考。

---

## 5. 常见问题与排错

### Q1: lifespan 中 await 的初始化操作失败导致应用无法启动

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_database()     # 如果失败，应用会崩溃
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        raise  # 让应用无法启动（显式失败优于静默错误）
    yield
```

数据库不可用时，应让应用**启动失败**而非带病运行。

### Q2: CORS 配置后前端仍然跨域报错

检查以下几点：
- `allow_origins` 列表是否包含前端实际运行的地址（注意 `localhost` ≠ `127.0.0.1`）
- 是否添加了 `allow_credentials=True`
- 前端请求是否带了 `withCredentials: true`
- 检查浏览器控制台的具体错误信息（是 Preflight 失败还是响应头缺失）

### Q3: WebSocket 连接 403 错误

WebSocket 升级请求不会自动携带认证信息。如果使用了认证中间件，需要在 WebSocket 端点中单独处理认证。在 GrassSea 中，`/ws/{session_id}` 使用 `session_id` 作为简易的身份标识。

### Q4: SSE 流在浏览器中缓冲不显示

可能原因：
- 中间件设置了 `Content-Encoding`（压缩会导致缓冲）
- 反代（nginx）开启了响应缓冲
- 响应数据量太小，浏览器等待更多数据

**解决**：在 SSE 响应的 header 中添加 `"X-Accel-Buffering": "no"`（对 nginx）。

### Q5: include_router 后路由 404

检查：
- 导入的 `router` 对象是否正确
- `prefix` 是否与你预期的路径一致
- 子路由中的路径是否以 `/` 开头

---

## 6. 练习任务

### 练习1：搭建多服务模拟
创建三个 FastAPI 应用实例，模拟 GrassSea 的微服务架构：
- **Gateway**（端口 8001）：负责接收请求并转发
- **Agent Service**（端口 8002）：处理智能体编排
- **Model Gateway**（端口 8004）：处理 LLM 调用

使用 `httpx.AsyncClient` 在 Gateway 中转发请求到下游服务。

### 练习2：实现 SSE 流式输出
在 Model Gateway 模拟服务中实现一个 `/chat/stream` 端点，使用 `StreamingResponse` 流式返回 LLM 的"思考过程"（可以用 `asyncio.sleep` 模拟逐步生成）。

### 练习3：编写审计中间件
参考 `shared/middleware/security.py` 中的 `AuditMiddleware`，自己编写一个中间件，记录每个请求的：
- 请求方法、路径、状态码
- 处理耗时（毫秒）
- 客户端 IP 和 User-Agent

并将日志输出为 JSON 格式。

---

*上一篇：[03-SQLAlchemy异步ORM.md](./03-SQLAlchemy异步ORM.md)*
*下一篇：进入阶段 01 — [项目初始化](../01-项目初始化/01-项目骨架搭建.md)*
