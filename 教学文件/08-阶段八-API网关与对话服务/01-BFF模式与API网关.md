# 01 - BFF 模式与 API 网关

## 学习目标

1. 理解 Backend For Frontend (BFF) 模式的概念和 GrassSea 中的应用
2. 掌握使用 `httpx` 异步客户端实现路由转发（反向代理）
3. 理解 API 网关的核心功能：路由转发、负载均衡、请求聚合、安全防护
4. 读懂 `services/chat_service/main.py` 的核心代码

## 前置知识

- 了解 HTTP 协议基础（GET/POST 请求、请求头、状态码）
- 了解 Python `asyncio` 和 `async/await` 的基本用法
- 了解 FastAPI 的路由和中间件基础
- 不需要深入了解 gRPC、消息队列（这会在第03节讲）

## 概念讲解

### 为什么需要 API 网关？

GrassSea 是一个微服务架构：

```
  前端 (React, 端口 3000)
         |
         | HTTP 请求
         v
+-----------------------------+
|   API 网关 (Chat Service)   |  <-- 端口 8001
|   路由转发 + 请求聚合        |
+-----------------------------+
    /        |         \
   /         |          \
  v          v           v
Agent       Knowledge    Model
Service     Service      Gateway
(8002)      (8003)       (8004)
```

如果没有网关，前端需要：
- 记住每个服务的地址（8001/8002/8003/8004...）
- 处理跨域问题（CORS）
- 在每个请求中手动添加认证 token

有了网关后，前端只需要访问 `http://localhost:8001`，网关负责把请求转发到正确的后端服务。

### BFF 模式 (Backend For Frontend)

```
传统微服务:  前端 <-> 服务A <-> 服务B <-> 服务C
BFF 模式:    前端 <-> BFF网关 <-> [服务A, 服务B, 服务C]
```

BFF 模式的核心理念是：**为前端量身定做一个中间层**，而不是让前端直接面对所有微服务。

在 GrassSea 中：
- **Chat Service (8001)** 就是前端的 BFF
- 它不包含业务逻辑，只负责：
  1. 接收前端请求
  2. 转发到下游服务
  3. 返回结果给前端

### Chat Service 的完整架构

```
+------------------------------------------------------+
|              Chat Service (端口 8001)                  |
|                                                       |
|  /chat          -> 转发到 Agent Service (8002)        |
|  /rag/query     -> 转发到 Knowledge Service (8003)    |
|  /rag/documents -> 转发到 Knowledge Service (8003)    |
|  /task/{id}     -> 转发到 Agent Service (8002)        |
|  /config/*      -> 配置管理 (config_api.py)            |
|  /health        -> 自身健康检查                        |
+------------------------------------------------------+
```

这就是"路由表"——每个路径对应一个后端服务。新增服务只需在网关中加一条路由规则，无需修改前端代码。

## 项目代码精讲

**文件位置**: `services/chat_service/main.py`

### 1. 服务初始化

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx

AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:8002")
KNOWLEDGE_SERVICE_URL = os.getenv("KNOWLEDGE_SERVICE_URL", "http://localhost:8003")
```

**逐段解析**：

- `import httpx` — httpx 是 Python 的现代 HTTP 客户端库，支持 `async/await`。它相当于 "支持异步的 requests 库"。
- `os.getenv("AGENT_SERVICE_URL", "http://localhost:8002")` — 从环境变量读取服务地址。Docker 环境中用服务名 `http://agent-service:8002`，本地开发用 `localhost`。

```python
app = FastAPI(title="GrassSea Chat Service", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**CORS 中间件**：

CORS（跨域资源共享）是浏览器的一项安全策略。当前端（localhost:3000）请求后端（localhost:8001）时，浏览器会先发一个"预检请求"确认后端是否允许跨域。

`allow_origins=["http://localhost:3000", "http://localhost:5173"]` 表示只允许这两个地址的前端访问。注意 `allow_origins=["*"]` 和 `allow_credentials=True` 不能同时使用（浏览器安全策略），所以显式列出了两个前端地址（3000 是 Vite 预览端口，5173 是开发端口）。

### 2. 核心：路由转发

**对话请求转发**：

```python
@app.post("/chat")
async def proxy_chat(request: Request):
    """转发对话请求到智能体编排服务 (8002)"""
    body = await request.json()
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{AGENT_SERVICE_URL}/chat", json=body,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
```

**逐步解析这个"转发流水线"**：

1. `async def proxy_chat(request: Request):` — 接收前端发来的原始 HTTP 请求。`Request` 是 FastAPI 的请求对象，包含了所有请求信息。

2. `body = await request.json()` — 从请求中提取 JSON 体。例如用户发送 `{"message": "计算排水量", "session_id": "sess_123"}`，`body` 就是这个字典。

3. `async with httpx.AsyncClient(timeout=120) as client:` — 创建异步 HTTP 客户端，设置 120 秒超时。`async with` 确保请求结束后自动关闭连接。

4. `resp = await client.post(f"{AGENT_SERVICE_URL}/chat", json=body)` — 把前端请求的 JSON 体**原封不动**地发到 Agent Service。这是一种"透传"——网关不修改请求内容。

5. `return JSONResponse(content=resp.json(), status_code=resp.status_code)` — 把后端服务的响应**原封不动**地返回给前端。状态码也保持一致，这样后端返回的错误码（404、500等）前端也能正确接收。

**文档上传的特殊处理**：

```python
@app.post("/rag/documents")
async def proxy_rag_upload(request: Request):
    """转发文档上传到知识库服务 (8003)"""
    form = await request.form()
    async with httpx.AsyncClient(timeout=120) as client:
        # 重新构建 multipart
        files = {}
        data = {}
        for key, value in form.items():
            if hasattr(value, "filename"):
                files[key] = (value.filename, await value.read(), value.content_type)
            else:
                data[key] = str(value)

        resp = await client.post(
            f"{KNOWLEDGE_SERVICE_URL}/rag/documents",
            data=data, files=files,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
```

文件上传的转发比普通 JSON 请求复杂一些，因为涉及 **multipart/form-data** 格式：

1. `form = await request.form()` — 读取整个 multipart 表单
2. 遍历表单字段，区分"文件字段"（有 `filename` 属性）和"普通字段"
3. 对文件字段，构造元组 `(文件名, 文件内容, 内容类型)`
4. 重新发送到后端服务

为什么要"重新构建"而不是直接转发？因为 httpx 的 multipart 构建方式和 FastAPI 的原始请求格式不同，最简单可靠的做法是解析后重建。

### 3. API 网关 vs 反向代理

你可能会问：这和 nginx 反向代理有什么区别？

| 对比维度 | Nginx 反向代理 | GrassSea API 网关 |
|----------|---------------|-------------------|
| 配置方式 | nginx.conf 静态规则 | Python 代码动态逻辑 |
| 请求聚合 | 不支持 | 支持（一个前端请求 = 多个后端调用） |
| 鉴权 | 基础 IP/Header 检查 | Python 任意逻辑 |
| 性能 | 极高（C 语言） | 一般（Python asyncio） |
| 适用场景 | 通用反向代理 | 需要业务逻辑的网关 |

GrassSea 选择自建网关（而不是纯 nginx），原因包括：
1. 需要在前端请求和微服务之间做请求/响应格式转换
2. 需要将加密的 API Key 注入到转发的请求中
3. 需要根据用户权限动态路由到不同的模型服务

### 4. 启动时的密钥传播

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(level="DEBUG" if settings.APP_DEBUG else "INFO")
    logger.info("Chat Service starting...")

    # 将加密存储的 API Key 推送到下游服务（带重试）
    from services.chat_service.config_api import _propagate_all_secrets
    await _propagate_all_secrets()

    yield
```

`lifespan` 是 FastAPI 的生命周期管理器。`yield` 之前的代码在服务启动时执行，`yield` 之后的代码在服务关闭时执行。

`_propagate_all_secrets()` 在网关启动时，自动将加密存储中的 API Key 解密并推送到所有下游服务。这意味着运维人员只需在网关配置一次 Key，所有下游服务都会自动获取。

## 手把手实践

### 实践1: 观察网关的转发行为

启动项目后，使用 curl 测试：

```bash
# 测试健康检查
curl http://localhost:8001/health

# 测试对话转发
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好", "session_id": "test_001"}'

# 测试 RAG 查询转发
curl -X POST http://localhost:8001/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "CCS 规范 稳性要求"}'
```

观察返回结果的格式，确认网关正确转发了响应。

### 实践2: 在网关中增加一个新转发路由

假设你有一个新的微服务"计算服务"运行在 8005，你想通过网关转发 `/compute/hydrostatics` 请求：

```python
# 在 main.py 中添加
COMPUTE_SERVICE_URL = os.getenv("COMPUTE_SERVICE_URL", "http://localhost:8005")

@app.post("/compute/hydrostatics")
async def proxy_hydrostatics(request: Request):
    body = await request.json()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{COMPUTE_SERVICE_URL}/compute/hydrostatics",
            json=body,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
```

### 实践3: 理解超时设置

修改 `/chat` 路由的超时时间为 5 秒，故意让请求超时：

```python
# 将 timeout=120 改为 timeout=2
async with httpx.AsyncClient(timeout=2) as client:
```

观察超时后前端的错误信息。这让你体验"超时保护"的意义——如果没有超时限制，一个卡住的后端服务会让所有前端用户一直等待。

## 视频学习资源

1. **微服务架构之 API 网关** — 理解网关在微服务中的位置
   - 搜索关键词: `微服务 API网关 BFF模式`
   - 推荐在 B 站搜索 "API 网关" 观看

2. **FastAPI 异步编程与 httpx 实战** — 掌握异步 HTTP 调用
   - 搜索关键词: `FastAPI httpx 异步请求`
   - 推荐在 B 站搜索 "FastAPI httpx" 或 "httpx 教程" 观看

3. **CORS 跨域原理详解** — 理解浏览器的安全策略
   - 搜索关键词: `CORS 跨域 原理`
   - 推荐在 B 站搜索 "CORS 跨域" 观看

## 常见问题与排错

### Q1: 前端请求返回 502 Bad Gateway

**原因**: 后端服务不可达。检查：
1. Agent Service (8002) 是否启动
2. `AGENT_SERVICE_URL` 环境变量是否正确
3. Docker 环境中服务名是否写对（如 `agent-service` vs `agent_service`）

### Q2: 文件上传返回 422 Unprocessable Entity

**原因**: 文件字段名不匹配。检查前端发送的字段名（如 `file`）是否与后端期望的字段名一致。

### Q3: 转发后返回"跨域错误"

**原因**: CORS 中间件配置问题。确认：
1. 前端地址是否在 `allow_origins` 列表中
2. 是否设置了 `allow_credentials=True`

### Q4: 网关自身的性能瓶颈

**说明**: 网关是 Python asyncio 实现，对于数千并发请求可能有性能压力。如果遇到性能瓶颈，可以在网关前再套一层 nginx 作为静态层，由 nginx 处理静态文件和基础限流，网关只处理需要业务逻辑的请求。

## 练习任务

1. **基础练习**: 在 Chat Service 中添加一个新路由 `/compute/stability`，转发到 Agent Service 的对应端点。

2. **进阶练习**: 修改 `/chat` 路由，在转发请求前先调用 `_propagate_all_secrets` 确保下游服务有最新的 API Key（提示：不要在每次请求都调用，可以在 lifespan 之后的某时刻触发）。

3. **挑战练习**: 在网关中实现请求日志记录：为所有转发请求添加日志，记录请求路径、转发目标、耗时、响应状态码。使用 `time.time()` 计算请求耗时。
