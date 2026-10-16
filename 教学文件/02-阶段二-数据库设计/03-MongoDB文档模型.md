# 03 - MongoDB 文档模型

## 学习目标

学完本文件后，你将能够：
1. 理解 MongoDB 文档模型与 SQL 表模型的本质差异
2. 掌握 Motor 异步驱动的使用方法
3. 理解 MongoDB 索引设计和 TTL 过期策略
4. 读懂 GrassSea 的 6 个 MongoDB 集合设计

## 前置知识

- 了解 JSON 格式
- 理解上一节 PostgreSQL 模型的表概念
- 了解 Python 字典（dict）的基本操作

## 概念讲解

### 一、MongoDB vs PostgreSQL —— 两种思维模式

**PostgreSQL 的思维**：先设计表结构（列名、类型、约束），再插入数据。数据必须符合表结构。

```
                        PostgreSQL（表=模具）
┌─────────────────────┐
│  projects 表         │     每行必须符合结构：
│ ┌──────┬──────┬────┐│
│ │ name │ code │status│    ✅ {name:"GS", code:"P01", status:"active"}
│ ├──────┼──────┼────┤│    ❌ {name:"GS", extra_field:"xxx"}  ← 多余字段
│ │  GS  │ P01  │active│
│ ├──────┼──────┼────┤│
│ │  HX  │ P02  │archived│
│ └──────┴──────┴────┘│
└─────────────────────┘
```

**MongoDB 的思维**：直接把 JSON 文档存进去，不需要预先定义结构。每条文档可以有不同的字段。

```
                        MongoDB（集合=文件夹）
┌──────────────────────────────────────┐
│  conversation_history 集合            │
│                                      │
│  📄 doc1: {                         │
│    session_id: "s1",                │
│    messages: [{role:"user", ...}],  │
│    state: "IDLE"                    │
│  }                                  │
│                                      │
│  📄 doc2: {                         │
│    session_id: "s2",                │
│    user_id: "u2",                   │
│    messages: [...],                 │
│    intent: "knowledge_qa",          │
│    token_usage: {total: 1500},      │  ← doc1 和 doc2 字段不完全相同
│    extra_custom_field: "anything"   │  ← 也是合法的！
│  }                                  │
└──────────────────────────────────────┘
```

**一句话区分**：PostgreSQL 像 Excel（固定列），MongoDB 像文件夹（每个文件内容自由）。

### 二、什么时候用 MongoDB

| 场景 | 适合 MongoDB？ | 理由 |
|------|---------------|------|
| 对话记录 | 是 | 嵌套消息数组，字段灵活 |
| 用户订单 | 否 | 需要事务、JOIN 关联 |
| 审查报告 | 是 | 半结构化、JSON 天然匹配 |
| 权限管理 | 否 | 严格的关联关系 |
| LLM 调用日志 | 是 | 写多读少、字段可变 |
| 型值表 | 否 | 结构固定、数值计算 |

### 三、Motor —— MongoDB 的异步 Python 驱动

Motor 是 MongoDB 官方推荐的异步 Python 驱动。它在 PyMongo 基础上封装了 async/await 支持。

```python
# 同步方式 (PyMongo)                  # 异步方式 (Motor)
from pymongo import MongoClient      from motor.motor_asyncio import AsyncIOMotorClient

client = MongoClient(uri)            client = AsyncIOMotorClient(uri)
db = client["mydb"]                  db = client["mydb"]
collection = db["mycoll"]            collection = db["mycoll"]

result = collection.find_one({})     result = await collection.find_one({})
```

在 FastAPI 中，所有数据库操作都在异步函数中执行，所以必须使用异步驱动。如果使用同步 PyMongo，会阻塞整个事件循环。

### 四、MongoDB 索引

和 PostgreSQL 的索引类似，MongoDB 的索引加速查询。但 MongoDB 的索引更灵活：

```python
# 单字段索引
collection.create_index("user_id")

# 复合索引
collection.create_index([("session_id", 1), ("created_at", -1)])

# TTL 索引（自动过期删除）
collection.create_index("created_at", expireAfterSeconds=7776000)  # 90天后自动删除
```

**TTL 索引**是 MongoDB 的特色功能：文档会在指定时间后自动删除。GrassSea 用 TTL 索引自动清理 90 天前的对话记录。

## 项目代码精讲

GrassSea 的 MongoDB 模型定义在 `shared/models/mongodb/collections.py`。

### 集合总览

```python
class MongoCollections:
    CONVERSATION_HISTORY = "conversation_history"    # 对话记录
    REVIEW_REPORTS = "review_reports"                # 审查报告
    AGENT_CONFIGS = "agent_configs"                  # Agent 配置
    TASK_DAGS = "task_dags"                          # 任务 DAG
    RESEARCH_REPORTS = "research_reports"            # 调研报告
    LLM_CALL_LOGS = "llm_call_logs"                  # LLM 调用日志
```

### 集合 1：conversation_history（对话记录）

```python
COLLECTION_INDEXES = {
    MongoCollections.CONVERSATION_HISTORY: [
        (["session_id", "created_at"], {"unique": False}),
        (["user_id"], {"unique": False}),
        (["created_at"], {"unique": False, "expireAfterSeconds": 7776000}),
    ],
}

CONVERSATION_SCHEMA = {
    "session_id": str,
    "user_id": str,
    "messages": list[dict],     # [{role, content, timestamp, sources}]
    "intent": str | None,
    "state": str,
    "token_usage": dict,
    "created_at": datetime,
    "updated_at": datetime,
}
```

**索引分析**：

| 索引 | 用途 |
|------|------|
| `session_id + created_at` | 查询某个会话的消息（按时间排序） |
| `user_id` | 查询某个用户的所有对话 |
| `created_at` (TTL) | 90 天后自动删除旧对话 |


**嵌套的 messages 数组**：这是 MongoDB 最大的优势——消息直接嵌套在会话文档中，不需要 JOIN 查询。

```json
{
  "session_id": "abc123",
  "user_id": "user-1",
  "messages": [
    {"role": "user", "content": "计算这艘船的稳性", "timestamp": "..."},
    {"role": "assistant", "content": "好的，正在计算...", "timestamp": "...",
     "sources": [{"title": "稳性计算报告", "page": 3}]},
    {"role": "user", "content": "再检查一下破舱稳性", "timestamp": "..."}
  ],
  "state": "IDLE",
  "token_usage": {"prompt": 2500, "completion": 800, "total": 3300}
}
```

如果用 PostgreSQL 存储，需要 2 张表 + JOIN：

```sql
-- conversations 表
SELECT * FROM conversations WHERE session_id = 'abc123';

-- messages 表
SELECT * FROM messages WHERE conversation_id = ... ORDER BY created_at;
```

### 集合 2：review_reports（审查报告）

```python
REVIEW_REPORT_SCHEMA = {
    "project_id": str,
    "user_id": str,
    "title": str,
    "summary": str,
    "violations": list[dict],    # 不合规项列表
    "suggestions": list[dict],   # 修改建议
    "references": list[dict],    # 引用的规范条文
    "attachments": list[str],    # MinIO 文件路径
    "status": str,               # draft / final
    "created_at": datetime,
    "updated_at": datetime,
}
```

船舶审查报告的典型结构：

```json
{
  "project_id": "proj-001",
  "title": "X 船稳性审查报告",
  "violations": [
    {"clause": "SOLAS II-1/5", "severity": "high",
     "description": "完整稳性不满足要求", "suggested_fix": "增加压载水"}
  ],
  "suggestions": [...],
  "references": [
    {"standard": "SOLAS 2024", "clause": "II-1/5.2", "page": 234}
  ],
  "status": "draft"
}
```

`violations` 和 `suggestions` 是动态数组——有些报告 3 条不合规，有些 20 条。MongoDB 处理这种变长数组非常自然。

### 集合 3：agent_configs（Agent 配置）

```python
AGENT_CONFIG_SCHEMA = {
    "agent_id": str,
    "name": str,
    "role": str,
    "capabilities": list[dict],
    "model_preference": str,
    "max_concurrent_tasks": int,
    "version": str,
    "tools": list[str],
    "status": str,              # online / offline / degraded
    "last_heartbeat": datetime,
}
```

Agent 配置存在 MongoDB 而不是 PostgreSQL 的原因是：配置结构灵活，不同 Agent 的能力项（`capabilities`）差异很大。PM Agent 有"任务分解"能力，CAD Agent 有"绘图"能力——用固定列难以表示。

### 集合 4：task_dags（任务 DAG）

```python
TASK_DAG_SCHEMA = {
    "task_id": str,
    "session_id": str,
    "dag": dict,                # DAG 结构 {nodes: [...], edges: [...]}
    "status": str,
    "current_step": str | None,
    "results": dict,
    "progress": float,
    "created_at": datetime,
    "updated_at": datetime,
}
```

DAG（有向无环图）是任务规划的核心数据结构。它表示任务之间的依赖关系：

```json
{
  "task_id": "task-001",
  "dag": {
    "nodes": [
      {"id": "step1", "tool": "web_search", "params": {...}},
      {"id": "step2", "tool": "hydrostatics", "params": {...}},
      {"id": "step3", "tool": "report_gen", "params": {...}}
    ],
    "edges": [
      {"from": "step1", "to": "step3"},
      {"from": "step2", "to": "step3"}
    ]
  }
}
```

### 集合 5：research_reports（调研报告）

```python
RESEARCH_REPORT_SCHEMA = {
    "user_id": str,
    "title": str,
    "abstract": str,
    "topics": list[str],
    "sources": list[dict],
    "content": str,              # Markdown 格式
    "created_at": datetime,
}
```

### 集合 6：llm_call_logs（LLM 调用日志）

```python
LLM_CALL_LOG_SCHEMA = {
    "user_id": str,
    "session_id": str,
    "model": str,
    "task_type": str,
    "input_tokens": int,
    "output_tokens": int,
    "total_tokens": int,
    "latency_ms": float,
    "status": str,               # success / error
    "error_message": str | None,
    "created_at": datetime,
}
```

注意：LLM 日志同时存储在 TimescaleDB（用于时序聚合分析）和 MongoDB（用于单条查询和 TTL 自动清理）。

### Conversation Repository —— Motor 实战

在 `shared/models/repository/conversation.py` 中，可以看到 Motor 的实际用法：

```python
class ConversationRepository:
    collection_name = MongoCollections.CONVERSATION_HISTORY

    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db[self.collection_name]

    async def create_session(self, session_id: str, user_id: str, initial_state: str = "IDLE") -> str:
        doc = {
            "session_id": session_id,
            "user_id": user_id,
            "messages": [],
            "intent": None,
            "state": initial_state,
            "token_usage": {"prompt": 0, "completion": 0, "total": 0},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        await self.collection.insert_one(doc)
        return session_id

    async def add_message(self, session_id: str, role: str, content: str, sources=None) -> None:
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow(),
            "sources": sources or [],
        }
        await self.collection.update_one(
            {"session_id": session_id},
            {
                "$push": {"messages": message},       # 在数组中追加
                "$set": {"updated_at": datetime.utcnow()},
            },
        )

    async def update_token_usage(self, session_id: str, prompt: int, completion: int) -> None:
        await self.collection.update_one(
            {"session_id": session_id},
            {
                "$inc": {                              # $inc = 原子自增
                    "token_usage.prompt": prompt,
                    "token_usage.completion": completion,
                    "token_usage.total": prompt + completion,
                },
                "$set": {"updated_at": datetime.utcnow()},
            },
        )
```

**关键 MongoDB 操作符**：

| 操作符 | 含义 | 示例 |
|--------|------|------|
| `$push` | 向数组追加元素 | `$push: {messages: new_msg}` |
| `$set` | 设置字段值 | `$set: {status: "completed"}` |
| `$inc` | 原子自增 | `$inc: {token_usage.total: 500}` |

## 手把手实践

### 任务：用 Motor 操作 MongoDB

**步骤 1**：确保 MongoDB 运行（Docker）

```bash
docker compose up -d mongodb
```

**步骤 2**：安装依赖

```bash
pip install motor
```

**步骤 3**：创建测试脚本

```python
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient("mongodb://grasssea:grasssea@localhost:27017/grasssea")
    db = client["grasssea"]
    collection = db["test_collection"]

    # 插入
    result = await collection.insert_one({"name": "测试文档", "value": 42})
    print(f"插入ID: {result.inserted_id}")

    # 查询
    doc = await collection.find_one({"name": "测试文档"})
    print(f"查询结果: {doc}")

    # 更新（$set）
    await collection.update_one(
        {"name": "测试文档"},
        {"$set": {"value": 100}}
    )

    # 删除
    await collection.delete_one({"name": "测试文档"})
    print("删除成功")

    client.close()

asyncio.run(main())
```

## 视频学习资源

在 B 站搜索以下关键词：
1. "MongoDB 入门教程" — MongoDB 基本概念和 CRUD 操作
2. "Motor Python 异步 MongoDB" — 异步驱动的使用方法
3. "MongoDB 索引设计" — 索引优化实战

## 常见问题与排错

### Q1: MongoDB 和 PostgreSQL 可以混用吗？
可以，GrassSea 就是这么做的。用户信息在 PostgreSQL 中，对话记录在 MongoDB 中，两者通过 `user_id` 关联（注意：MongoDB 中没有真正的外键约束，关联靠应用层保证）。

### Q2: MongoDB 没有表结构，怎么写代码？
虽然 MongoDB 不强制 schema，但 GrassSea 通过 Python 的 dataclass 和注释定义了逻辑 schema（如 `CONVERSATION_SCHEMA`）。生产环境建议使用 pydantic 验证文档结构。

### Q3: TTL 索引生效慢怎么办？
TTL 索引的后台清理线程每 60 秒运行一次，不是立即删除。如果需要立即清理，手动调用 `delete_many()`。

### Q4: `$push` 和 `$addToSet` 有什么区别？
- `$push`：向数组追加元素（允许重复）
- `$addToSet`：向数组追加不重复的元素

对话记录使用 `$push` 因为需要按时间顺序保留所有消息。

## 练习任务

1. **Schema 对比**：对比 `task_records`（PostgreSQL）和 `task_dags`（MongoDB）的设计，分析为什么任务记录存 PG 而任务 DAG 存 MongoDB。

2. **索引优化**：当前 `conversation_history` 的索引是 `[session_id, created_at]`。分析如果大量查询是"获取用户最近 20 条会话"，这个索引是否最优？如果要优化，应该怎么改？

3. **编写 Repository**：仿照 `ConversationRepository`，编写一个 `ReviewReportRepository` 类，包含 `create_report`、`get_by_project`、`update_status` 方法。

4. **监控思考**：LLM 调用日志存在 MongoDB，同时又存在 TimescaleDB。分析这种"双写"策略的利弊。
