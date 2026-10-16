# Python 异步编程 — async/await 与 asyncio

## 学习目标

- 理解同步与异步编程的本质区别
- 掌握 `async`/`await` 语法并能编写协程函数
- 理解 asyncio 事件循环的工作原理
- 能区分协程、线程、进程的适用场景
- 能在 FastAPI 项目中读懂和编写异步代码

## 前置知识

- 熟悉 Python 基础语法（函数、类、模块导入）
- 了解 Python 的 `requests` 库或 HTTP 请求的基本概念
- 完成 `00-学习路线图.md` 的阅读

---

## 1. 概念讲解

### 1.1 为什么需要异步编程？

想象你在餐厅点餐：

- **同步模式**：你点完菜，厨师开始做。你就站在取餐口等着，什么事也不做，直到菜做好。期间后面的客人也只能干等。
- **异步模式**：你点完菜拿到号码牌，回到座位上刷手机。厨师做好菜，叫号，你再去取。期间你可以同时做别的事，餐厅也能服务更多人。

在编程中，**I/O 操作**（网络请求、数据库查询、文件读写）就是"厨师做菜"的过程。CPU 提交一个 I/O 请求后，大部分时间在等待外部系统响应。如果不使用异步，这段时间 CPU 就白白空转了。

**GrassSea 项目中的真实场景**：

1. Agent Service 在 `_handle_knowledge_query` 中需要调用知识库服务的 HTTP API -- 如果同步等待，整个服务会被阻塞
2. Chat Service 作为前端 API 网关，需要将请求转发到下游服务 -- 每个请求都涉及网络 I/O
3. Model Gateway 调用外部 LLM API（DeepSeek、Claude），响应可能长达数十秒

如果不使用异步编程，**一次请求就会阻塞整个服务**，10 个并发用户可能需要排队等待几百秒。

### 1.2 核心概念图解

```
┌─────────────────────────────────────────────────────┐
│                   事件循环 (Event Loop)               │
│                                                     │
│   ┌──────┐    ┌──────┐    ┌──────┐                 │
│   │协程 A │    │协程 B │    │协程 C │                 │
│   │      │    │      │    │      │                 │
│   │ 执行  │───▶│ 等待 │    │ 等待 │  ← 遇到 await 挂起│
│   │      │    │      │    │      │                 │
│   │ 等待  │    │ 执行  │───▶│ 等待 │                 │
│   │      │    │      │    │      │                 │
│   │ 等待  │    │ 等待 │    │ 执行  │                 │
│   └──────┘    └──────┘    └──────┘                 │
│                                                     │
│   单线程！同一时刻只有一个协程在运行                      │
│   但 I/O 等待期间可以切换到其他协程                      │
└─────────────────────────────────────────────────────┘
```

**三个关键概念**：

| 概念 | 说明 | 类比 |
|------|------|------|
| **协程 (Coroutine)** | 用 `async def` 定义的函数，可以在执行中被挂起和恢复 | 一项待办任务 |
| **事件循环 (Event Loop)** | 调度器，管理所有协程的执行顺序，检测 I/O 完成 | 餐厅老板，分配厨师 |
| **await** | 挂起当前协程，交出控制权，等待结果返回后继续 | "我先去忙别的，好了叫我" |

### 1.3 协程 vs 线程 vs 进程

```
┌───────────────┬──────────────┬──────────────┬──────────────┐
│               │    协程       │    线程       │    进程       │
├───────────────┼──────────────┼──────────────┼──────────────┤
│ 调度者         │ 程序自身      │ 操作系统      │ 操作系统      │
│ 切换成本       │ 极低 (ns)     │ 中等 (μs)    │ 高 (ms)      │
│ 内存占用       │ KB 级         │ MB 级        │ 百MB 级      │
│ 适合场景       │ I/O 密集型    │ 混合型        │ CPU 密集型   │
│ Python 实现    │ asyncio       │ threading     │ multiprocessing│
│ 数据共享       │ 无需锁        │ 需要锁        │ IPC 通信     │
└───────────────┴──────────────┴──────────────┴──────────────┘
```

> ⚠️ **注意**：Python 的 GIL（全局解释器锁）使得多线程无法真正并行执行 Python 代码。对于 I/O 密集型任务，**asyncio 是 Python 中最高效的方案**。

---

## 2. 项目代码精讲

> 🔗 **参考文件**：`services/agent_service/main.py`、`services/chat_service/main.py`

### 2.1 async def -- 定义一个协程

打开 `services/agent_service/main.py`，几乎每个函数都以 `async def` 开头：

```python
# services/agent_service/main.py (第88行)
@app.get("/health")
async def health():
    agents = await agent_registry.list_agents() if agent_registry else []
    return {
        "status": "healthy", "service": "agent-service",
        "version": settings.APP_VERSION,
        "registered_agents": len(agents),
    }
```

`async def` 定义的函数返回的是一个**协程对象**，调用它不会立即执行，而是返回一个可以交给事件循环的对象。FastAPI 会自动识别 `async def` 的路由处理函数，并在事件循环中执行它。

### 2.2 await -- 等待并交出控制权

```python
# services/agent_service/main.py (第150行)
intent_result = await intent_classifier.classify(request.message)
```

`await` 做了三件事：
1. 暂停当前协程的执行
2. 将控制权交还给事件循环，让其他协程可以运行
3. 等 `intent_classifier.classify()` 完成后，恢复执行并获取结果

**关键规则**：`await` 只能用在 `async def` 函数内部。

### 2.3 httpx.AsyncClient -- 异步 HTTP 客户端

项目中最常见的 I/O 操作是 HTTP 请求。代码使用了 `httpx.AsyncClient` 而非传统的 `requests` 库：

```python
# services/agent_service/main.py (第224行)
async def _handle_chitchat(message: str) -> str:
    import httpx
    if not settings.DEEPSEEK_API_KEY:
        return "您好！我是 GrassSea AI 助手..."

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": message}], "max_tokens": 1024},
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"]
```

逐行解析：
- `async with httpx.AsyncClient(timeout=30) as client:` -- 创建异步 HTTP 客户端上下文，超时 30 秒
- `resp = await client.post(...)` -- 异步发送 POST 请求，**这里 await 让出了控制权**
- 在等待 DeepSeek 响应的这段时间，事件循环可以去处理其他用户的请求

**对比**：如果用 `requests.post()`，整个线程会阻塞在这里，等待网络返回，其他任何请求都无法处理。

### 2.4 asynccontextmanager -- 应用生命周期

FastAPI 使用 `@asynccontextmanager` 管理应用的启动和关闭：

```python
# services/chat_service/main.py (第27行)
@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(level="DEBUG" if settings.APP_DEBUG else "INFO")
    logger.info("Chat Service starting...")
    # 将加密存储的 API Key 推送到下游服务
    from services.chat_service.config_api import _propagate_all_secrets
    await _propagate_all_secrets()
    yield       # ← 这里是分界线：之前是启动逻辑，之后是关闭逻辑
    # 关闭清理逻辑（当前未显式执行，但可以在此添加）

app = FastAPI(title="GrassSea Chat Service", version="0.1.0", lifespan=lifespan)
```

`yield` 之前 -- 启动时执行（初始化数据库连接、加载配置等）
`yield` 之后 -- 关闭时执行（清理连接等）

### 2.5 异步与同步混用注意事项

在 `services/chat_service/main.py` 中，所有路由处理函数都是 `async def`：

```python
# services/chat_service/main.py (第60行)
@app.post("/chat")
async def proxy_chat(request: Request):
    body = await request.json()
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{AGENT_SERVICE_URL}/chat", json=body)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
```

> ⚠️ **注意**：如果在 `async def` 中调用了同步阻塞函数（如 `time.sleep(5)`），整个事件循环会被卡住 5 秒。应该使用 `await asyncio.sleep(5)` 代替。

---

## 3. 手把手实践

### 3.1 你的第一个协程

创建一个文件 `test_async.py`：

```python
import asyncio

async def greet(name: str) -> str:
    """异步打招呼函数"""
    print(f"[开始] 准备向 {name} 打招呼...")
    await asyncio.sleep(1)   # 模拟 I/O 等待（如网络请求）
    print(f"[完成] {name} 的招呼已准备好")
    return f"你好, {name}!"

async def main():
    # 方式1: 顺序执行
    result1 = await greet("Alice")
    print(result1)
    result2 = await greet("Bob")
    print(result2)

# 运行
asyncio.run(main())
```

运行后你会发现：两个招呼是**顺序**执行的，总耗时约 2 秒。

### 3.2 并发执行 -- asyncio.gather

修改 `main()` 函数：

```python
async def main():
    # 方式2: 并发执行
    results = await asyncio.gather(
        greet("Alice"),
        greet("Bob"),
        greet("Charlie"),
    )
    for r in results:
        print(r)
```

这次三个协程**并发**执行，总耗时约 1 秒！因为三个协程同时开始等待，等待期间控制权在事件循环中互相切换。

### 3.3 模拟 HTTP 请求并发

```python
import asyncio
import time

async def fetch_url(url: str) -> str:
    """模拟获取 URL 内容（实际应使用 httpx）"""
    print(f"  [开始请求] {url}")
    await asyncio.sleep(2)  # 模拟网络延迟
    print(f"  [完成请求] {url}")
    return f"<{url} 的内容>"

async def main():
    urls = ["http://api1.com", "http://api2.com", "http://api3.com"]

    start = time.time()
    results = await asyncio.gather(*(fetch_url(u) for u in urls))
    elapsed = time.time() - start

    print(f"\n并发请求 {len(urls)} 个 URL 仅耗时 {elapsed:.1f} 秒")
    for r in results:
        print(r)

asyncio.run(main())
```

> 💡 **提示**：`asyncio.gather(*(...))` 中的 `*` 是解包操作符，将列表展开为多个参数。

---

## 4. 视频学习资源

在 B站 (bilibili.com) 搜索以下关键词，可以找到高质量视频教程：

- [B站搜索: Python asyncio 异步编程 入门](https://search.bilibili.com/all?keyword=Python+asyncio+%E5%BC%82%E6%AD%A5%E7%BC%96%E7%A8%8B+%E5%85%A5%E9%97%A8) -- 建议筛选播放量较高的视频
- [B站搜索: FastAPI 异步 async await 实战](https://search.bilibili.com/all?keyword=FastAPI+async+await+%E5%AE%9E%E6%88%98) -- 结合框架理解异步
- [B站搜索: Python 协程 asyncio 原理](https://search.bilibili.com/all?keyword=Python+%E5%8D%8F%E7%A8%8B+asyncio+%E5%8E%9F%E7%90%86) -- 深入理解事件循环

> 💡 **提示**：推荐关注 B站 UP主「码农高天」「Python知识圈」等频道，他们的 Python 教程质量较高。

---

## 5. 常见问题与排错

### Q1: `RuntimeWarning: coroutine 'xxx' was never awaited`

```python
# 错误写法
async def foo():
    return "hello"

result = foo()  # ← 这里只是创建了协程对象，没有执行！
print(result)   # <coroutine object foo at 0x...>
```

**原因**：调用了 `async def` 函数但没有 `await` 它。协程对象只是被创建了，没有执行。

**解决**：使用 `result = await foo()` 或 `asyncio.run(foo())`。

### Q2: `await` 用在非 `async def` 函数中

```python
def normal_function():
    result = await some_coroutine()  # ← SyntaxError!
```

**解决**：将函数改为 `async def`，或者在最外层使用 `asyncio.run()`。

### Q3: `asyncio.run()` 不能在已有事件循环中调用

FastAPI 应用已经运行在事件循环中，所以在路由函数中**不要使用** `asyncio.run()`。直接 `await` 即可。

### Q4: 同步阻塞库导致性能问题

`time.sleep(5)`、`requests.get(url)` 等同步操作会阻塞事件循环。替代方案：

| 同步写法                | 异步替代                       |
|------------------------|-------------------------------|
| `time.sleep(5)`        | `await asyncio.sleep(5)`      |
| `requests.get(url)`    | `await httpx.AsyncClient().get(url)` |
| `open("file").read()`  | `await aiofiles.open("file").read()` |

---

## 6. 练习任务

### 练习1：异步爬虫模拟
编写一个异步函数 `fetch_user_info(user_id: str)`，模拟从 5 个不同的 API 获取用户信息（每个 `asyncio.sleep(random())` 模拟不同延迟），然后用 `asyncio.gather` 并发执行，对比顺序执行的时间差异。

### 练习2：分析项目代码
打开 `services/agent_service/main.py`，找到并列出所有使用了 `await` 的行，解释每一行 `await` 是在等待什么操作完成。

### 练习3：改造同步代码
将下面这段同步代码改写为异步版本：

```python
import requests

def get_all_data():
    urls = ["https://api1.com/a", "https://api2.com/b", "https://api3.com/c"]
    results = []
    for url in urls:
        resp = requests.get(url, timeout=30)
        results.append(resp.json())
    return results
```

---

*上一篇：[00-学习路线图.md](./00-学习路线图.md)*
*下一篇：[02-Pydantic数据模型.md](./02-Pydantic数据模型.md)*
