# 05 - Token 追踪与统计

## 学习目标

学完本文件后，你将能够：
1. 理解 Token 统计的意义（成本控制、用量分析）
2. 掌握批量缓冲写入的设计模式
3. 理解 Token 追踪在不同存储中的分工
4. 读懂 GrassSea 的 `TokenTracker` 完整实现

## 前置知识

- 了解 LLM 的 Token 概念（LLM 处理文本的最小单位）
- 了解 MongoDB 和 TimescaleDB 的基本用途
- 掌握 Python 列表和字典的基本操作

## 概念讲解

### 一、为什么需要 Token 追踪

LLM 的调用是有成本的。每个模型按 Token 计费：

```
DeepSeek V3:   输入 ¥1/M tokens,  输出 ¥2/M tokens
Claude Sonnet: 输入 $3/M tokens, 输出 $15/M tokens
GPT-4o:       输入 $2.5/M tokens, 输出 $10/M tokens
```

如果没有追踪：
- 不知道这个月花了多少钱
- 不知道哪个用户用量异常
- 不知道哪个任务类型最耗 Token
- 无法做成本优化

**Token 追踪回答的问题**：

| 问题 | SQL 示例 | 用途 |
|------|---------|------|
| 本月花了多少 Token？ | `SUM(total_tokens) WHERE time > month_start` | 成本核算 |
| 哪个用户用量最多？ | `GROUP BY user_id ORDER BY SUM(total_tokens) DESC` | 识别异常 |
| 哪种任务最耗 Token？ | `GROUP BY task_type ORDER BY AVG(total_tokens) DESC` | 优化方向 |
| 哪个模型最划算？ | `GROUP BY model ORDER BY SUM(total_tokens)/COUNT(*)` | 模型选型 |
| API 延迟正常吗？ | `AVG(latency_ms) GROUP BY model` | 性能监控 |

### 二、批量缓冲写入模式

每完成一次 LLM 调用就写一次数据库，在高并发下会成为瓶颈。GrassSea 使用**批量缓冲写入**：

```
每次 LLM 调用:

非批量写入（低效）:                    批量缓冲写入（高效）:

LLM 调用 → 写 DB                       LLM 调用 → 缓冲数组
LLM 调用 → 写 DB                       LLM 调用 → 缓冲数组
LLM 调用 → 写 DB                       LLM 调用 → 缓冲数组
LLM 调用 → 写 DB                       LLM 调用 → 缓冲数组  (达到 100 条)
                                        └────批次写 DB────┘

100 次调用 = 100 次 DB 写入             100 次调用 = 1 次 DB 批量写入
```

```
TokenTracker 内部:

_buffer = []           ← 缓冲区（内存中）
_max_buffer_size = 100  ← 缓冲区上限

record() 被调用:
  ├── 将记录追加到 _buffer
  ├── 打印日志（立即）
  └── 如果 len(_buffer) >= 100:
       └── flush() → 批量写入数据库，清空缓冲区
```

### 三、双存储策略

GrassSea 将 Token 记录存储在两个地方：

```
LLM 调用
  │
  ├── TokenTracker.record()
  │     │
  │     ├── MongoDB (llm_call_logs)
  │     │     用途: 单条查询、错误追溯、TTL 自动过期
  │     │     保留: 90 天
  │     │
  │     └── TimescaleDB (token_usage_metrics)
  │           用途: 时序聚合、按天/周/月统计、Grafana 作图
  │           保留: 长期
  │
  └── 日志 (结构化 JSON)
        用途: 实时监控、报警
```

```
MongoDB (llm_call_logs)              TimescaleDB (token_usage_metrics)
┌──────────────────────────┐        ┌──────────────────────────────┐
│ 每条 LLM 调用的完整记录    │        │ 按时间聚合的统计数据            │
│                          │        │                              │
│ - user_id                │        │ - time (主键 = 时间)           │
│ - session_id             │        │ - user_id                    │
│ - model                  │        │ - model                      │
│ - task_type              │        │ - task_type                   │
│ - input_tokens           │        │ - input_tokens                │
│ - output_tokens          │        │ - output_tokens               │
│ - total_tokens           │        │ - total_tokens                │
│ - latency_ms             │        │ - session_id                 │
│ - status                 │        │                              │
│ - error_message          │        │ 适合: 时序聚合查询              │
│ - created_at (TTL 90天)  │        │ SELECT SUM(total_tokens)     │
│                          │        │ WHERE time > now()-30d       │
│ 适合: 单条查询、错误追溯   │        │ GROUP BY model               │
│ db.llm_call_logs         │        │                              │
│   .find({session:"xxx"}) │        └──────────────────────────────┘
└──────────────────────────┘
```

## 项目代码精讲

### TokenTracker 完整实现

```python
class TokenTracker:
    """Token 用量追踪器"""

    def __init__(self):
        self._buffer: list[dict] = []
        self._max_buffer_size = 100     # 缓冲区大小

    async def record(
        self,
        user_id: str,
        session_id: str,
        model: str,
        task_type: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
    ) -> None:
        """记录一次 LLM 调用"""
        record = {
            "user_id": user_id,
            "session_id": session_id,
            "model": model,
            "task_type": task_type,
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "latency_ms": latency_ms,
            "status": "success",
            "created_at": datetime.utcnow(),
        }

        # 追加到内存缓冲区
        self._buffer.append(record)

        # 立即打印日志（不等待批量写入）
        logger.info(
            "Token usage",
            model=model,
            task_type=task_type,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=round(latency_ms, 1),
        )

        # 缓冲区满时批量写入
        if len(self._buffer) >= self._max_buffer_size:
            await self.flush()

    async def flush(self) -> None:
        """批量写入缓冲区"""
        count = len(self._buffer)
        self._buffer.clear()
        if count > 0:
            logger.debug("Token tracker flushed", records=count)
```

### record() 的时间线

```
record() 被调用
  │
  ├── 1. 构造记录字典
  │     user_id, model, tokens, latency, ...
  │
  ├── 2. buffer.append(record)
  │     立即追加到内存，不阻塞
  │
  ├── 3. logger.info("Token usage", ...)
  │     实时输出日志（用于监控面板）
  │     这一步是同步的，保证日志即时性
  │
  └── 4. 如果 buffer 满了
        └── flush() → 批量写 MongoDB + TimescaleDB
```

### 调用时机

```python
# main.py 中的 _sync_response()
elapsed_ms = (time.time() - start_time) * 1000

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

# main.py 中的 _stream_response()
# 同样在流结束时记录（收到所有 token 后）
elapsed_ms = (time.time() - start_time) * 1000

if token_tracker:
    await token_tracker.record(
        user_id=request.user or "anonymous",
        session_id=trace_id,
        model=route_result.model,
        task_type=route_result.task_type,
        prompt_tokens=route_result.prompt_tokens or 0,
        completion_tokens=route_result.completion_tokens or 0,
        latency_ms=elapsed_ms,
    )
```

流式调用中，`prompt_tokens` 和 `completion_tokens` 来自 `route_result`，这些值在流结束后由 `complete_stream` 填充。

### get_user_usage —— 用量查询

```python
async def get_user_usage(self, user_id: str, days: int = 30) -> dict:
    """获取用户用量统计"""
    # 生产环境：
    # SELECT SUM(total_tokens) FROM timeseries.token_usage_metrics
    # WHERE user_id = $1 AND time > now() - interval '$2 days'

    return {
        "user_id": user_id,
        "total_tokens": 0,
        "total_calls": 0,
        "days": days,
    }
```

`get_user_usage` 目前是一个**桩方法**（stub method）——返回默认值，生产环境需要实现实际的 SQL 查询。这种设计在开发阶段很常见：先定义接口，后续补全实现。

### 缓冲区刷新的隐患和优化

当前实现的一个问题：如果缓冲区有 50 条记录，服务关闭时这些记录会丢失（未刷新）。

**优化方案**：

```python
# 在 lifespan 的关闭阶段显式刷新
async def lifespan(app):
    yield
    # 关闭前刷新
    if token_tracker:
        await token_tracker.flush()
        logger.info("Token tracker flushed on shutdown", remaining=len(token_tracker._buffer))
```

## 手把手实践

### 任务：为 TokenTracker 添加 TimescaleDB 写入

**步骤 1**：获取 TimescaleDB 会话

```python
from shared.models.database import get_pg_session

async def _write_to_timescaledb(self, records: list[dict]):
    async for session in get_pg_session():
        for record in records:
            metric = TokenUsageMetric(
                time=record["created_at"],
                user_id=record["user_id"],
                model=record["model"],
                task_type=record["task_type"],
                input_tokens=record["input_tokens"],
                output_tokens=record["output_tokens"],
                total_tokens=record["total_tokens"],
                session_id=record["session_id"],
            )
            session.add(metric)
        await session.commit()
        break  # 只取一个 session
```

**步骤 2**：修改 flush 方法

```python
async def flush(self) -> None:
    count = len(self._buffer)
    if count == 0:
        return

    records_to_write = self._buffer.copy()
    self._buffer.clear()

    try:
        await self._write_to_timescaledb(records_to_write)
        logger.info("Token tracker flushed to TimescaleDB", records=count)
    except Exception as e:
        logger.error("Failed to flush token records", error=str(e))
        # 写回缓冲区（或写入死信队列）
        self._buffer.extend(records_to_write)
```

**步骤 3**：实现 get_user_usage（真正的查询）

```python
async def get_user_usage(self, user_id: str, days: int = 30) -> dict:
    async for session in get_pg_session():
        from datetime import datetime, timedelta
        from sqlalchemy import func

        since = datetime.utcnow() - timedelta(days=days)
        result = await session.execute(
            select(
                func.sum(TokenUsageMetric.total_tokens),
                func.count(),
            ).where(
                TokenUsageMetric.user_id == user_id,
                TokenUsageMetric.time >= since,
            )
        )
        total_tokens, total_calls = result.one()
        break

    return {
        "user_id": user_id,
        "total_tokens": total_tokens or 0,
        "total_calls": total_calls or 0,
        "days": days,
    }
```

### 用 Grafana 查看 Token 统计

连接到 PostgreSQL 后在 Grafana 中创建面板：

```sql
-- Token 用量随时间变化（按天）
SELECT
  date_trunc('day', time) AS "time",
  SUM(total_tokens) AS "tokens"
FROM timeseries.token_usage_metrics
WHERE time > now() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1;

-- 各模型用量占比（饼图）
SELECT model, SUM(total_tokens) AS "tokens"
FROM timeseries.token_usage_metrics
WHERE time > now() - INTERVAL '30 days'
GROUP BY model;
```

## 视频学习资源

在 B 站搜索以下关键词：
1. "LLM Token 计费 成本控制" — 了解 Token 的成本概念
2. "Grafana 面板 TimescaleDB" — 使用时序数据构建监控面板
3. "批量写入 Buffer 模式" — 高并发场景下的批量写入优化

## 常见问题与排错

### Q1: 缓冲区中的数据在服务崩溃时会丢失吗？
会。当前实现是纯内存缓冲区，没有持久化。生产环境应该：
- 使用 Redis 作为中间缓冲区（持久化 + 高性能）
- 或使用消息队列（RabbitMQ → 异步写入 Worker）

### Q2: Token 计数不准确怎么办？
每次 LLM API 返回的 `usage` 字段是准确的 Token 数。但如果 API 没有返回（某些提供商不支持），需要本地用 tiktoken 库计算：

```python
import tiktoken
encoder = tiktoken.get_encoding("cl100k_base")
tokens = len(encoder.encode(text))
```

### Q3: 100 的缓冲区大小合理吗？
取决于调用频率：
- 每秒 10 次调用 → 每 10 秒写入一次（合理）
- 每秒 1 次调用 → 每 100 秒写入一次（可以降低到 20）
- 每秒 1000 次调用 → 每 0.1 秒写入一次（需要增大到 1000 或改用异步写入）

### Q4: 如何处理 LLM 调用失败时不记录 Token？
当前 `record()` 中 `status` 硬编码为 `"success"`。应该在调用方判断：

```python
try:
    completion = await model_router.complete(...)
    await token_tracker.record(status="success", ...)
except Exception:
    await token_tracker.record(status="error", ...)
```

## 练习任务

1. **完善 TokenTracker**：按手把手实践的指导，补全 TokenTracker 的 TimescaleDB 写入逻辑和 `get_user_usage` 查询方法。

2. **设计用量限制**：在 TokenTracker 中添加 `check_quota(user_id, max_tokens_per_day)` 方法，如果用户超过每日限额，拒绝调用。

3. **成本计算器**：编写一个函数，根据模型定价表（每百万 Token 的价格）和用户的 Token 用量，计算出总费用。

4. **告警规则设计**：设计 3 条 Token 相关的告警规则（如"单日 Token 用量超过阈值"、"API 延迟 P99 超过 5 秒"、"错误率超过 10%"），写出每条的 Prometheus 或 Grafana 表达式。
