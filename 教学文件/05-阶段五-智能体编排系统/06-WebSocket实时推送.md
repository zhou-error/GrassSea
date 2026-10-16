# 06 - WebSocket 实时推送

## 学习目标

1. 理解 WebSocket 与 HTTP 的本质区别
2. 掌握 FastAPI WebSocket 端点的实现
3. 理解连接管理、双向通信和断线处理
4. 能实现基于 WebSocket 的实时进度推送

## 前置知识

- FastAPI 基础（路由、依赖注入）
- Python 异步编程（async/await）
- 了解 JSON 格式

## 概念讲解

### HTTP vs WebSocket

```
HTTP（短连接）：
═══════════════════════════════════════
  客户端： "给我数据" ──────────►
                             服务器处理
  客户端：        ◄──────── "这是数据"
  客户端： "还有新数据吗？" ───►
                             服务器处理
  客户端：        ◄──────── "没有"
  客户端： "现在呢？" ────────►
                             服务器处理
  客户端：        ◄──────── "有！这是新数据"

  问题：客户端必须不断轮询，浪费资源


WebSocket（长连接）：
═══════════════════════════════════════
  客户端： "我们建立连接吧" ───►
                             服务器： "好的"
         ═══════ 连接建立 ═══════
                             服务器： "任务开始了"
                             服务器： "进度 25%"
                             服务器： "进度 50%"
  客户端： "取消任务！" ──────►
                             服务器： "已取消"
                             服务器： "进度 100%"
         ═══════ 连接关闭 ═══════

  优势：双向、实时、低延迟、无需轮询
```

### WebSocket 在 GrassSea 中的角色

```
用户浏览器                     Agent Service
    │                              │
    │  ws://localhost:8002/ws/sess_abc
    │──────────────────────────────│
    │                              │
    │  ← {"event": "progress",     │
    │      "task_id": "t_123",     │
    │      "progress": 25.0}       │
    │                              │
    │  ← {"event": "progress",     │
    │      "task_id": "t_123",     │
    │      "progress": 50.0}       │
    │                              │
    │  ← {"event": "message",      │
    │      "text": "稳性分析完成"}  │
    │                              │
    │  {"action": "cancel",        │
    │   "task_id": "t_123"}  ──────►
    │                              │
    │  ← {"event": "cancelled"}    │
```

## 项目代码精讲

打开 `services/agent_service/main.py`。

### 全局连接池

```python
# 第34行
active_connections: dict[str, WebSocket] = {}

# 第196-197行：WebSocket 端点
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
```

`active_connections` 是一个全局字典，以 `session_id` 为键、`WebSocket` 对象为值。它使得系统的其他部分（如执行引擎）能向特定用户推送消息。

### WebSocket 生命周期

```python
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # 1. 接受连接
    await websocket.accept()
    active_connections[session_id] = websocket
    logger.info("WebSocket connected", session_id=session_id)

    try:
        # 2. 持续接收客户端消息
        while True:
            data = await websocket.receive_text()
            import json
            msg = json.loads(data)
            # 3. 处理客户端请求（如取消任务）
            if msg.get("action") == "cancel":
                await task_executor.cancel_task(msg.get("task_id"))
                await websocket.send_json({
                    "event": "cancelled",
                    "task_id": msg.get("task_id"),
                })

    except WebSocketDisconnect:
        # 4. 断线处理
        logger.info("WebSocket disconnected", session_id=session_id)

    finally:
        # 5. 清理
        active_connections.pop(session_id, None)
```

**五步生命周期**：
1. `accept()` -- 握手确认，连接建立
2. `while True` -- 循环接收消息
3. 处理消息 -- 解析 JSON，执行操作
4. `WebSocketDisconnect` -- 捕获断线异常
5. `finally` -- 无论如何都要从连接池中移除

### 服务端主动推送

当前代码中执行引擎（executor.py）没有直接调用 WebSocket 推送。但在生产环境中，推送逻辑应该是这样的：

```python
# 在其他代码中推送消息的典型模式
async def push_progress(session_id: str, task_id: str, progress: float):
    ws = active_connections.get(session_id)
    if ws:
        await ws.send_json({
            "event": "progress",
            "task_id": task_id,
            "progress": progress,
        })
```

这个函数可以在 `_execute_dag` 的进度更新处调用：

```python
# executor.py 的 _execute_dag 中
task["progress"] = ...  # 更新进度
# 推送给前端
await push_progress(task.get("session_id"), task_id, task["progress"])
```

### 与 HTTP 端点的配合

```
HTTP 端点：创建任务
═══════════════════════════════
POST /chat
  → 返回: {"task_id": "t_123", "answer": "任务已创建，正在执行..."}

WebSocket 端点：跟踪进度
═══════════════════════════════
ws://localhost:8002/ws/sess_abc
  ← {"event": "progress", "task_id": "t_123", "progress": 25.0}
  ← {"event": "progress", "task_id": "t_123", "progress": 50.0}
  ← {"event": "progress", "task_id": "t_123", "progress": 75.0}
  ← {"event": "completed", "task_id": "t_123", "result": {...}}

HTTP 端点：查询最终结果
═══════════════════════════════
GET /task/t_123/status
  → 返回: {"status": "completed", "progress": 100, "result": {...}}
```

两种协议各有分工：HTTP 负责创建和查询，WebSocket 负责实时跟踪。

### 完整的聊天流程（chat 端点回顾）

```python
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id or f"sess_{trace_id}"

    # 意图识别 → 路由
    intent_result = await intent_classifier.classify(request.message)

    if intent_result.intent_type in (IntentType.TOOL_CALL, IntentType.PROFESSIONAL_TASK):
        # 创建任务 → 异步执行
        task = await task_planner.plan(request.message, intent_result)
        await task_executor.execute_async(task, session_id, request.user_id)

        # 立即返回（不等待执行完成！）
        return ChatResponse(
            session_id=session_id,
            answer=f"任务已创建 (ID: {task['task_id']})",
            task_id=task["task_id"],
        )
```

用户收到 `task_id` 后，前端通过 WebSocket 连接跟踪任务进度。这是典型的"创建即返回 + 异步通知"模式。

## 手把手实践

### 实验一：最简单的 WebSocket 服务

```python
# mini_ws.py -- 10行代码理解 WebSocket
from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.websocket("/ws")
async def echo(websocket: WebSocket):
    await websocket.accept()                 # 接受连接
    while True:
        data = await websocket.receive_text()  # 收消息
        await websocket.send_text(f"收到: {data}")  # 回消息

# 运行: uvicorn mini_ws:app --port 8000
```

用浏览器或 `wscat` 测试：
```bash
npm install -g wscat
wscat -c ws://localhost:8000/ws
```

输入任意文本，服务器会回显。

### 实验二：带进度推送的 WebSocket

```python
# progress_ws.py
import asyncio
from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.websocket("/ws/task/{task_id}")
async def task_progress(websocket: WebSocket, task_id: str):
    await websocket.accept()

    # 模拟一个5步任务，每秒推送一次进度
    for i in range(1, 6):
        await asyncio.sleep(1)
        await websocket.send_json({
            "task_id": task_id,
            "step": i,
            "progress": i * 20,
            "message": f"正在执行第 {i} 步..."
        })

    await websocket.send_json({
        "task_id": task_id,
        "status": "completed",
        "progress": 100,
        "message": "任务完成！"
    })
    await websocket.close()
```

## 视频学习资源

请在 B站（bilibili.com）自行搜索以下关键词：

- "WebSocket 原理 通俗讲解" -- 入门 WebSocket
- "FastAPI WebSocket 实战教程" -- 学习 FastAPI WS
- "实时推送 SSE vs WebSocket vs 轮询" -- 对比实时通信方案

## 常见问题与排错

**Q1：WebSocket 连接频繁断开怎么办？**

A：常见原因和解决方案：
1. **代理超时**：Nginx 默认 60 秒超时，需要配置 `proxy_read_timeout 3600s`
2. **网络不稳定**：前端添加自动重连逻辑（exponential backoff）
3. **服务端崩溃**：WebSocket 在 `finally` 中清理，但意外崩溃可能跳过。添加心跳包（ping/pong）

**Q2：多个服务实例之间怎么共享 WebSocket 连接？**

A：当前内存字典只在单实例内有效。多实例部署时需要使用 Redis Pub/Sub 或消息队列来广播消息，让持有该 session 连接的实例推送。

**Q3：`receive_text()` 是阻塞的吗？**

A：FastAPI 的 WebSocket `receive_text()` 是异步的（awaitable），不会阻塞事件循环。但如果客户端长时间不发消息，服务器会一直等。建议设置心跳超时或使用 `asyncio.wait_for()`。

## 练习任务

1. **代码题**：修改 `mini_ws.py`，添加一个简单的聊天功能：服务器记录所有收到的消息，新客户端连接时自动发送历史消息。
2. **分析题**：`active_connections.pop(session_id, None)` 的第二个参数 `None` 是什么意思？如果去掉会怎样？
3. **实践题**：基于 `progress_ws.py`，添加客户端取消功能：客户端发送 `{"action": "cancel"}` 时，服务器中断任务执行。
4. **综合题**：设计一个方案，在 `_execute_dag` 的每个步骤完成后，通过 WebSocket 向对应的 session 推送进度。需要修改哪些代码？数据如何从 executor 传到 WebSocket？
