# 02 - OpenAI 兼容接口

## 学习目标

学完本文件后，你将能够：
1. 理解 OpenAI Chat Completions API 的请求/响应格式
2. 使用 Pydantic 模型定义类型安全的 API 接口
3. 理解同步和异步 LLM 调用的处理流程
4. 读懂 GrassSea 中 `/v1/chat/completions` 的完整实现

## 前置知识

- 了解 HTTP POST 请求和 JSON 格式
- 使用过 Pydantic BaseModel 定义数据模型
- 了解 FastAPI 路由和异步函数

## 概念讲解

### 一、OpenAI Chat Completions API 格式

这是整个模型网关的核心接口。请求格式：

```json
{
  "model": "deepseek-chat",
  "messages": [
    {"role": "system", "content": "你是船舶工程专家"},
    {"role": "user", "content": "解释什么是稳性"}
  ],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 4096,
  "top_p": 1.0,
  "user": "user-123"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | string | 是 | 模型名称，如 "deepseek-chat" |
| `messages` | array | 是 | 消息列表，支持 system/user/assistant 角色 |
| `stream` | bool | 否 | 是否流式输出，默认 false |
| `temperature` | float | 否 | 随机性参数，0-2，默认 0.7 |
| `max_tokens` | int | 否 | 最大输出 token 数 |
| `top_p` | float | 否 | 核采样参数 |
| `user` | string | 否 | 用户标识，用于追踪和计费 |

**messages 数组的角色：**

```
role 类型:
- system:   系统提示词（设定 AI 的行为和身份）
- user:     用户消息
- assistant: AI 的回复（用于多轮对话上下文）

典型多轮对话:
[
  {"role": "system", "content": "你是船舶工程师"},
  {"role": "user", "content": "什么是稳性？"},
  {"role": "assistant", "content": "稳性是指船舶在外力作用下..."},
  {"role": "user", "content": "如何计算稳性？"}
]
```

### 二、Pydantic 模型的进阶用法 —— Field 验证

```python
class ChatCompletionRequest(BaseModel):
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
```

`Field` 不仅设置默认值，还设置了**约束条件**：

```python
# 合法请求
{"temperature": 0.5}   # ✅ 在 0.0-2.0 之间

# 非法请求
{"temperature": 3.0}   # ❌ 422 Unprocessable Entity
# 错误信息: "temperature: ensure this value is less than or equal to 2.0"
```

**这是 FastAPI + Pydantic 的威力**：不用写任何验证代码，只需要在模型定义中声明约束，框架自动校验。

### 三、两种响应模式

```
非流式 (stream=false):                    流式 (stream=true):

请求 ──────────> LLM                      请求 ──────────> LLM
                   │                                         │
                   │ (等待完整响应)                              │ (逐 token 返回)
                   │                                         │
                   v                                         v
              ┌─────────┐                               ┌─────────┐
              │ 完整响应 │                               │ token 1 │
              │ JSON    │                               ├─────────┤
              └─────────┘                               │ token 2 │
                                                        ├─────────┤
优点: 一次返回完整结果                                      │ token 3 │
缺点: 用户需要等待                                          ├─────────┤
                                                        │ ...     │
                                                        └─────────┘

                                                       优点: 用户立刻看到输出
                                                       缺点: 实现复杂（SSE 协议）
```

## 项目代码精讲

### 请求/响应 Pydantic 模型

```python
class ChatMessage(BaseModel):
    role: str = "user"
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "deepseek-chat"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    user: Optional[str] = None

class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"

class ChatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatUsage
```

响应对象的结构对应 OpenAI 的格式：

```json
{
  "id": "chatcmpl-a1b2c3d4",
  "object": "chat.completion",
  "created": 1721635200,
  "model": "deepseek-chat",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "稳性是指船舶在外力作用下发生倾斜..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 45,
    "completion_tokens": 156,
    "total_tokens": 201
  }
}
```

### 核心端点处理流程

```python
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, http_request: Request):
    # 1. 生成追踪 ID
    trace_id = str(uuid.uuid4())[:8]
    set_trace_id(trace_id)

    start_time = time.time()

    # 2. 构造路由请求
    route_request = ModelRouteRequest(
        model=request.model,
        messages=[m.model_dump() for m in request.messages],
        task_type="simple_chat",
    )

    # 3. 执行模型路由
    try:
        route_result = await model_router.route(route_request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 4. 根据 stream 参数选择处理方式
    if request.stream:
        return StreamingResponse(
            _stream_response(request, route_result, trace_id, start_time),
            media_type="text/event-stream",
        )
    else:
        return await _sync_response(request, route_result, trace_id, start_time)
```

**流程图解**：

```
POST /v1/chat/completions
        │
        v
   生成 trace_id → 设置日志上下文
        │
        v
   构造 ModelRouteRequest
   (把 Pydantic 模型转为 dataclass)
        │
        v
   model_router.route()
   (决定使用哪个模型、哪个 API Key)
        │
   ┌────┴────┐
   v         v
 同步      流式
 _sync     _stream
   │         │
   v         v
 model_router.complete()    model_router.complete_stream()
   │         │
   v         v
 token_tracker.record()     token_tracker.record()
   │         │
   v         v
 返回 JSON                 返回 SSE 事件流
```

### _sync_response —— 非流式响应处理

```python
async def _sync_response(
    request: ChatCompletionRequest,
    route_result,
    trace_id: str,
    start_time: float,
) -> ChatCompletionResponse:
    try:
        completion = await model_router.complete(route_result, stream=False)
        content = completion.get("content", "")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM service error: {str(e)}")

    elapsed_ms = (time.time() - start_time) * 1000

    prompt_tokens = completion.get("prompt_tokens", 0)
    completion_tokens = completion.get("completion_tokens", 0)

    # 记录 Token 统计
    if token_tracker:
        await token_tracker.record(
            user_id=request.user or "anonymous",
            session_id=trace_id,
            model=route_result.model,
            task_type=route_result.task_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=elapsed_ms,
        )

    # 构造并返回 OpenAI 兼容格式的响应
    return ChatCompletionResponse(
        id=f"chatcmpl-{trace_id}",
        created=int(time.time()),
        model=route_result.model,
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(role="assistant", content=content),
                finish_reason="stop",
            )
        ],
        usage=ChatUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )
```

关键细节：

1. **错误处理**：LLM 调用失败时返回 502（Bad Gateway），而不是 500。语义上更准确：网关本身没出错，上游服务出错了。

2. **时间统计**：`elapsed_ms = (time.time() - start_time) * 1000`。`time.time()` 返回秒级浮点数，乘以 1000 转为毫秒。

3. **Trace ID 作为 Response ID**：`id=f"chatcmpl-{trace_id}"`。这样 API 返回的响应 ID 和日志中的 trace_id 一致，方便问题排查。

### chat_completions 入口的参数说明

```python
async def chat_completions(
    request: ChatCompletionRequest,   # Pydantic 模型，自动解析 JSON body
    http_request: Request             # FastAPI 原生 Request 对象
):
```

两个参数各有用处：
- `request: ChatCompletionRequest`：自动校验和解析的请求数据
- `http_request: Request`：原始的 HTTP 请求对象（用于获取请求头、IP 等元数据）

## 手把手实践

### 任务：用 curl 测试模型网关

**步骤 1**：启动模型网关

```bash
cd F:/GrassSea
# 确保 .env 中有 DEEPSEEK_API_KEY
python -m uvicorn services.model_gateway.main:app --port 8004 --reload
```

**步骤 2**：测试非流式请求

```bash
curl -X POST http://localhost:8004/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [
      {"role": "user", "content": "用一句话解释船舶稳性"}
    ],
    "stream": false,
    "temperature": 0.7
  }'
```

**步骤 3**：验证响应格式

```json
{
  "id": "chatcmpl-a1b2c3d4",
  "object": "chat.completion",
  "created": 1721635200,
  "model": "deepseek-chat",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "船舶稳性是..."},
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 50,
    "total_tokens": 75
  }
}
```

**步骤 4**：用 Python 调用（使用 OpenAI SDK）

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8004/v1",     # 指向 GrassSea 模型网关
    api_key="not-needed"                      # 网关已配置 API Key
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "你好"}],
)
print(response.choices[0].message.content)
```

## 视频学习资源

在 B 站搜索以下关键词：
1. "OpenAI API chat completions 格式" — 了解标准接口格式
2. "Pydantic Field 验证" — 学习 Field 约束的高级用法
3. "FastAPI 请求响应模型" — Pydantic 与 FastAPI 的集成

## 常见问题与排错

### Q1: 422 Unprocessable Entity
**原因**：请求不符合 Pydantic 模型定义。
**排查**：
```bash
# 查看详细验证错误
curl ... | jq '.detail'
# 常见原因: temperature 超出 0-2, max_tokens 超出限制
```

### Q2: 502 Bad Gateway
**原因**：LLM 上游服务返回错误（API Key 无效、网络不通、速率限制）。
**排查**：查看模型网关日志中的 trace_id，搜索对应的 LLM API 原始错误。

### Q3: 响应格式和 OpenAI 不完全一样
GrassSea 提供了核心字段的兼容（choices、usage、model 等），但某些非必需字段（如 `system_fingerprint`、`logprobs`）未实现。如果使用 OpenAI SDK，通常不会因此报错。

### Q4: `model_dump()` 是什么？
Pydantic v2 中替代 `.dict()` 的方法。将 Pydantic 模型转为 Python 字典：

```python
msg = ChatMessage(role="user", content="你好")
msg.model_dump()  # {"role": "user", "content": "你好"}
```

## 练习任务

1. **编写完整的请求/响应测试**：使用 Python 的 `httpx` 库编写测试脚本，发送 10 种不同参数的请求（不同 model、temperature、max_tokens），验证每种都返回正确格式。

2. **扩展 Pydantic 模型**：在 `ChatCompletionRequest` 中添加 `presence_penalty` 和 `frequency_penalty` 字段（OpenAI 标准参数），设置合理的默认值和约束。

3. **错误场景测试**：编写 5 个异常场景的测试：temperature 超出范围、messages 为空数组、不存在的 model、API Key 无效、网络超时。

4. **响应格式对比**：调用真实的 OpenAI API 和 GrassSea 模型网关，对比两者的响应 JSON 结构，列出所有差异字段。
