# 04 - SSE 流式输出

## 学习目标

学完本文件后，你将能够：
1. 理解 SSE（Server-Sent Events）协议的基本原理
2. 掌握 Python 异步生成器（async generator）的用法
3. 理解 FastAPI 的 `StreamingResponse` 使用方法
4. 读懂 GrassSea 中 SSE 流式输出的完整实现

## 前置知识

- 了解 HTTP 协议的基本概念（请求/响应、Header、Content-Type）
- 掌握 Python 的 `yield` 关键字和生成器概念
- 了解 `async`/`await` 异步编程基础

## 概念讲解

### 一、为什么需要流式输出

LLM 生成文本的过程是逐个 token 的。如果等所有 token 生成完再返回，用户需要等待数十秒。

```
非流式输出 (Streaming=false):

发送请求 ────────────────────────────────────────> 收到完整响应
          <── 等待 10-30 秒，用户看着空白屏幕 ──>


流式输出 (Streaming=true):

发送请求 ──> "船" ──> "舶" ──> "稳" ──> "性" ──> "是" ──> ... ──> 完成
              <── 每个 token 到达后立即显示 ──>
```

流式输出的用户体验远好于非流式——就像打字机效果，用户能看到 AI 逐字"思考"的过程。

**数据量对比**：

```
非流式：                                流式 (SSE)：

HTTP Response                          HTTP Response (text/event-stream)
Content-Type: application/json         Content-Type: text/event-stream
                                       Cache-Control: no-cache
{                                      Connection: keep-alive
  "choices": [{
    "message": {                        data: {"choices":[{"delta":{"content":"船"}}]}
      "content": "船舶稳性是..."        data: {"choices":[{"delta":{"content":"舶"}}]}
    }                                  data: {"choices":[{"delta":{"content":"稳"}}]}
  }]                                   data: {"choices":[{"delta":{"content":"性"}}]}
}                                      data: {"choices":[{"delta":{"content":"是"}}]}
                                       data: {"choices":[{"delta":{"content":"..."}}]}
一次传输 1000 tokens                     data: [DONE]
                                       N 次传输，每次 1 token
```

### 二、SSE 协议基础

SSE（Server-Sent Events）是 HTTP 标准的一部分，专门用于服务器向客户端推送实时事件。

**SSE 协议规则**：

```
1. Content-Type 必须是 "text/event-stream"
2. 每条消息以 "data: " 开头
3. 每条消息以 "\n\n"（两个换行）结尾
4. 可选字段: id, event, retry
5. 结束消息: "data: [DONE]\n\n"
```

SSE 数据流示例：

```
data: {"token": "船"}\n\n
data: {"token": "舶"}\n\n
data: {"token": "稳"}\n\n
data: {"token": "性"}\n\n
data: [DONE]\n\n
```

**SSE vs WebSocket**：

| 特性 | SSE | WebSocket |
|------|-----|-----------|
| 方向 | 单向（服务器 → 客户端） | 双向 |
| 协议 | HTTP（标准端口，无需特殊配置） | 独立协议（ws://） |
| 自动重连 | 浏览器内置 | 需要手动实现 |
| 适用场景 | 实时更新、流式数据 | 聊天、游戏、协作编辑 |
| 复杂度 | 低（就是 HTTP） | 较高 |

对于 LLM 流式输出这种"单向数据流"场景，SSE 是完美的选择。

### 三、Python 异步生成器

GrassSea 的流式输出使用 Python 的**异步生成器**（async generator）。

```python
# 普通函数
def normal():
    return "结果"           # 一次性返回

# 普通生成器 (同步)
def generator():
    yield "第1个"           # 逐次返回
    yield "第2个"
    yield "第3个"

# 异步生成器
async def async_gen():
    yield "第1个"           # 逐次返回（支持 await）
    await asyncio.sleep(1)
    yield "第2个"

# 使用方式
async for item in async_gen():
    print(item)
```

FastAPI 的 `StreamingResponse` 接受一个异步生成器，每个 `yield` 输出作为 HTTP 响应的一块数据发送给客户端。

## 项目代码精讲

### StreamingResponse 入口

```python
if request.stream:
    return StreamingResponse(
        _stream_response(request, route_result, trace_id, start_time),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",      # 禁止缓存
            "Connection": "keep-alive",       # 保持连接
            "X-Trace-Id": trace_id,           # 追踪 ID
        },
    )
```

**关键 Header 含义**：

- `Cache-Control: no-cache`：代理服务器不能缓存 SSE 流
- `Connection: keep-alive`：保持 TCP 连接不关闭
- `X-Trace-Id`：自定义响应头，方便客户端追踪

### _stream_response —— 流式生成器

```python
async def _stream_response(
    request: ChatCompletionRequest,
    route_result,
    trace_id: str,
    start_time: float,
):
    try:
        # === 阶段 1：逐 token 输出 ===
        async for chunk in model_router.complete_stream(route_result):
            content = chunk.get("content", "")
            if content:
                data = {
                    "id": f"chatcmpl-{trace_id}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": route_result.model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": content},      # 流式用 delta，非流式用 message
                        "finish_reason": None,
                    }],
                }
                yield f"data: {__import__('json').dumps(data)}\n\n"

        # === 阶段 2：发送结束帧 ===
        elapsed_ms = (time.time() - start_time) * 1000

        if token_tracker:
            await token_tracker.record(...)

        final_data = {
            "id": f"chatcmpl-{trace_id}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": route_result.model,
            "choices": [
                {"index": 0, "delta": {}, "finish_reason": "stop"}
            ],
        }
        yield f"data: {__import__('json').dumps(final_data)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error("Streaming error", error=str(e))
        error_data = {"error": {"message": str(e), "type": "stream_error"}}
        yield f"data: {__import__('json').dumps(error_data)}\n\n"
        yield "data: [DONE]\n\n"
```

### 流式响应的时间线

```
客户端                                服务器 (SSE 流)

│ POST /v1/chat/completions          │
│ {stream: true, ...}                │
│ ─────────────────────────────────> │
│                                     │ 调用 _call_deepseek_stream()
│                                     │
│ <───────────────────────────────── │ data: {"delta":{"content":"船"}}
│ <───────────────────────────────── │ data: {"delta":{"content":"舶"}}
│ <───────────────────────────────── │ data: {"delta":{"content":"稳"}}
│ <───────────────────────────────── │ data: {"delta":{"content":"性"}}
│                                     │ ... (更多 token)
│ <───────────────────────────────── │ data: {"delta":{}, "finish_reason":"stop"}
│ <───────────────────────────────── │ data: [DONE]
│                                     │
│ 连接关闭                            │ 生成器退出
```

### DeepSeek 流式调用

```python
async def _call_deepseek_stream(self, route: ModelRouteResult) -> AsyncIterator[dict]:
    url = f"{route.base_url}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {route.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": route.model,
        "messages": [{"role": "user", "content": "ping"}],
        "stream": True,                             # 启用流式
    }

    async with self._http_client.stream("POST", url, json=payload, headers=headers) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():   # 逐行读取
            if line.startswith("data: "):
                data_str = line[6:]                  # 去掉 "data: " 前缀
                if data_str == "[DONE]":
                    break
                data = json.loads(data_str)
                choice = data.get("choices", [{}])[0]
                delta = choice.get("delta", {})
                yield {"content": delta.get("content", "")}
```

**httpx 流式连接的处理**：

```python
# 普通 POST（一次性读取响应）
response = await client.post(url, json=payload)
data = response.json()

# 流式 POST（逐行读取响应）
async with client.stream("POST", url, json=payload) as response:
    async for line in response.aiter_lines():
        # 逐行处理...
```

关键：
- `client.stream()` 不对接整个响应体，而是打开一个流式连接
- `aiter_lines()` 按行迭代响应内容
- `async with` 确保异常时连接正确关闭

### Claude 流式调用

```python
async def _call_claude_stream(self, route: ModelRouteResult) -> AsyncIterator[dict]:
    url = f"{route.base_url}/v1/messages"
    headers = {
        "x-api-key": route.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": route.model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": "ping"}],
        "stream": True,
    }

    async with self._http_client.stream("POST", url, json=payload, headers=headers) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:]
                data = json.loads(data_str)
                # Claude 的流式事件类型
                if data.get("type") == "content_block_delta":
                    delta = data.get("delta", {})
                    yield {"content": delta.get("text", "")}
```

**Claude 流式事件与 DeepSeek 流式事件的差异**：

```
DeepSeek (OpenAI 格式):
data: {"choices":[{"delta":{"content":"token1"}}]}
data: {"choices":[{"delta":{"content":"token2"}}]}
data: [DONE]

Claude (Anthropic 格式):
event: content_block_start
data: {"type":"content_block_start","index":0,...}
event: content_block_delta
data: {"type":"content_block_delta","delta":{"text":"token1"}}
event: content_block_delta
data: {"type":"content_block_delta","delta":{"text":"token2"}}
event: message_stop
data: {"type":"message_stop"}
```

网关将这些差异封装起来，对外统一输出 OpenAI 格式。

## 手把手实践

### 任务：用 Python 消费 SSE 流

**步骤 1**：安装依赖

```bash
pip install httpx httpx-sse
```

**步骤 2**：编写 SSE 客户端

```python
import asyncio
import httpx

async def consume_sse():
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            "http://localhost:8004/v1/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "解释船舶稳性"}],
                "stream": True,
            },
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        print("\n--- 结束 ---")
                        break
                    import json
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        print(content, end="", flush=True)  # 不换行输出

asyncio.run(consume_sse())
```

**效果**：脚本运行时，你会看到文本像打字机一样逐字出现。

## 视频学习资源

在 B 站搜索以下关键词：
1. "SSE Server-Sent Events 教程" — SSE 协议的原理和实现
2. "Python 异步生成器 async generator" — 理解 yield 和 async for
3. "FastAPI StreamingResponse" — FastAPI 中流式响应的使用方法

## 常见问题与排错

### Q1: SSE 连接建立后没有数据
**原因**：LLM API 响应慢，或流式连接配置有问题。
**排查**：
```bash
# 用 curl 测试（-N 禁用缓冲）
curl -N -X POST http://localhost:8004/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}],"stream":true}'
```

### Q2: 浏览器缓存 SSE 响应
**解决**：在响应头中设置 `Cache-Control: no-cache` 和 `X-Accel-Buffering: no`（针对 nginx 反向代理）。

### Q3: SSE 连接中断了怎么办？
OpenAI 格式的 SSE 每块数据都是自包含的 JSON。客户端发现连接中断后，可以带上已收到的 token 重新发起请求（`messages` 中包含已收到的内容）。

### Q4: nginx 代理导致 SSE 不能实时推送
**原因**：nginx 默认缓冲响应数据。
**解决**：在 nginx location 配置中添加：
```nginx
proxy_buffering off;
proxy_cache off;
```

### Q5: `__import__('json')` 的写法为什么不用 `import json`？
这是为了在模块顶部减少不必要的 import。在生成器中每次 yield 才调用 json.dumps。不过这样做每次都会调用 `__import__`，性能不如顶部 `import json`。这是 GrassSea 代码中一个小优化点。

## 练习任务

1. **实现 SSE 客户端**：编写一个 Python 脚本，接收 SSE 流并实时将内容追加到文件中（模拟日志记录）。

2. **对比流式速度**：发送同一个问题，分别测 stream=true 和 stream=false 的"首字节时间"（TTFB, Time To First Byte）和"总完成时间"，比较差异。

3. **错误处理增强**：在 `_stream_response` 中添加重连逻辑——如果 LLM 流中断，尝试用非流式获取剩余内容并拼接。

4. **多客户端测试**：同时启动 5 个 SSE 消费者，测试模型网关的并发流式输出能力。观察是否有"串行化"现象。
