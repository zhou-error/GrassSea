# 04 - TimescaleDB 时序数据

## 学习目标

学完本文件后，你将能够：
1. 理解什么是时序数据和为什么需要专门的时序数据库
2. 掌握 TimescaleDB 超表（Hypertable）的概念
3. 理解 PostgreSQL 中 schema 的作用
4. 读懂 GrassSea 的 4 张时序指标表设计

## 前置知识

- 了解 PostgreSQL 的基本概念（表、查询、索引）
- 理解上一节 PostgreSQL 模型中的 SQLAlchemy ORM
- 知道什么是时间戳（timestamp）

## 概念讲解

### 一、什么是时序数据

时序数据（Time-series Data）是以时间为索引的数据。每条记录都有一个时间戳，数据按时间顺序产生。

```
常见时序数据：

Token 用量统计:  09:00 → 1500 tokens   09:01 → 2300 tokens   09:02 → 800 tokens
API 延迟:        09:00 → 120ms          09:01 → 85ms           09:02 → 340ms
工具调用频次:     09:00 → 3次            09:01 → 7次            09:02 → 1次
```

**时序数据的特征**：

| 特征 | 含义 | 影响 |
|------|------|------|
| 写入密集 | 每秒可能有成百上千条写入 | 需要高效的写入路径 |
| 追加为主 | 很少修改或删除历史数据 | 不需要事务 |
| 时间查询 | 查询总是带时间范围 | 需要时间维度的索引 |
| 聚合分析 | 常用 SUM/AVG/COUNT 按时间段聚合 | 需要高效聚合函数 |
| 数据量大 | 持续增长，很快达到百万/亿级 | 需要自动分区 |

### 二、普通 PostgreSQL 的问题

如果用普通 PostgreSQL 表存储时序数据：

```sql
-- 普通表
CREATE TABLE token_usage (
    time TIMESTAMP,
    user_id VARCHAR(100),
    model VARCHAR(50),
    input_tokens INT,
    output_tokens INT
);

-- 典型的时序查询
SELECT model, SUM(output_tokens)
FROM token_usage
WHERE time > now() - INTERVAL '30 days'
GROUP BY model;
```

当数据量达到千万行，这个查询会变得很慢，因为需要扫描所有行。索引可以加速过滤，但聚合操作仍然慢。

### 三、TimescaleDB 的解决方案 —— 超表（Hypertable）

超表是 TimescaleDB 的核心概念。它**自动按时间分区**，但使用起来和普通表完全一样。

```
普通 PostgreSQL 表:                     TimescaleDB 超表:

┌─────────────────────────────┐       ┌─────────────────────────────┐
│      token_usage            │       │   token_usage (超表)        │
│                             │       │                             │
│  所有行在一个大块中           │       │  自动分成多个数据块 (chunk)  │
│  查询需要扫描整个表           │       │  按时间范围自动分区           │
│                             │       │                             │
│  row1, row2, ..., row100W   │       │  ┌──────────┐  2024-01      │
│                             │       │  │  chunk1  │               │
└─────────────────────────────┘       │  ├──────────┤  2024-02      │
                                      │  │  chunk2  │               │
普通表扫描: 100万行                     │  ├──────────┤  2024-03      │
超表扫描: 只扫描需要的 chunk             │  │  chunk3  │               │
                                      │  └──────────┘               │
                                      └─────────────────────────────┘

查询30天的数据: 只扫描30天对应的chunk(s)，跳过其他chunk。这叫"分区裁剪"。
```

**创建超表只需一行 SQL**：

```sql
SELECT create_hypertable('token_usage_metrics', 'time');
--                        表名                     时间列
```

之后所有操作和普通表一样（INSERT、SELECT、UPDATE），TimescaleDB 自动处理分区。

### 四、PostgreSQL Schema —— 命名空间

GrassSea 将时序表放在独立的 `timeseries` schema 下：

```sql
-- 不在默认 public schema 中
CREATE TABLE token_usage_metrics (...) -- 默认在 public 中

-- 在独立的 timeseries schema 中
CREATE TABLE timeseries.token_usage_metrics (...) -- 在 timeseries 中
```

schema 的好处：
- **逻辑隔离**：时序表不会和业务表混在一起
- **权限控制**：可以针对 schema 设置不同权限
- **清晰组织**：一看就知道哪些是时序数据

SQLAlchemy 中指定 schema：

```python
class TokenUsageMetric(Base):
    __tablename__ = "token_usage_metrics"
    __table_args__ = {"schema": "timeseries"}
```

## 项目代码精讲

GrassSea 的时序模型定义在 `shared/models/timescale/metrics.py`。

### 表 1：token_usage_metrics（Token 用量统计）

```python
class TokenUsageMetric(Base):
    __tablename__ = "token_usage_metrics"
    __table_args__ = {"schema": "timeseries"}

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
```

**设计要点**：

1. **主键是时间**：`time` 作为主键，这决定了数据按时间有序存储
2. **维度字段**：`user_id`、`model`、`task_type`——分析时按这些维度聚合
3. **度量字段**：`input_tokens`、`output_tokens`、`total_tokens`——要统计的数值

**典型分析查询**：

```sql
-- 过去 7 天每种模型的 Token 用量
SELECT
    model,
    date_trunc('day', time) as day,
    SUM(total_tokens) as daily_tokens
FROM timeseries.token_usage_metrics
WHERE time > now() - INTERVAL '7 days'
GROUP BY model, date_trunc('day', time)
ORDER BY day, daily_tokens DESC;
```

```sql
-- 每个用户的 Token 用量排名（过去 30 天）
SELECT user_id, SUM(total_tokens) as total
FROM timeseries.token_usage_metrics
WHERE time > now() - INTERVAL '30 days'
GROUP BY user_id
ORDER BY total DESC
LIMIT 10;
```

### 表 2：api_latency_metrics（API 延迟统计）

```python
class APILatencyMetric(Base):
    __tablename__ = "api_latency_metrics"
    __table_args__ = {"schema": "timeseries"}

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, default=200)
```

可用于回答：
- 哪个 API 端点响应最慢？（按 endpoint 聚合平均延迟）
- 什么时间段延迟最高？（按小时聚合）
- P95/P99 延迟是多少？（TimescaleDB 支持 percentile 函数）

### 表 3：tool_call_metrics（工具调用频次）

```python
class ToolCallMetric(Base):
    __tablename__ = "tool_call_metrics"
    __table_args__ = {"schema": "timeseries"}

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    tool_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), nullable=True)
    task_id: Mapped[str] = mapped_column(String(100), nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0)
    success: Mapped[bool] = mapped_column(Integer, default=1)
```

可用于回答：
- 哪个工具调用最频繁？
- 哪个工具失败率最高？（`success=0` 的比例）
- 工具调用的平均耗时？

### 表 4：session_metrics（会话统计）

```python
class SessionMetric(Base):
    __tablename__ = "session_metrics"
    __table_args__ = {"schema": "timeseries"}

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    intent: Mapped[str] = mapped_column(String(50), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0)
    token_total: Mapped[int] = mapped_column(Integer, default=0)
```

这张表记录每个会话的最终统计，而非每次 LLM 调用的细节。

### 初始化：创建超表和 TimescaleDB 扩展

`infrastructure/docker/postgres/init/01-init-extensions.sql` 在容器首次启动时执行：

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE SCHEMA IF NOT EXISTS timeseries;
```

然后需要通过 Alembic 迁移或手动 SQL 将普通表转换为超表：

```sql
-- 将 token_usage_metrics 转换为超表
SELECT create_hypertable('timeseries.token_usage_metrics', 'time');

-- 将 api_latency_metrics 转换为超表
SELECT create_hypertable('timeseries.api_latency_metrics', 'time');
```

## 手把手实践

### 任务：查询 TimescaleDB 中的 Token 统计

**步骤 1**：连接 PostgreSQL

```bash
docker exec -it grasssea-postgres psql -U grasssea -d grasssea
```

**步骤 2**：确认 TimescaleDB 已安装

```sql
SELECT * FROM pg_extension WHERE extname = 'timescaledb';
```

**步骤 3**：查看超表信息

```sql
-- 查看所有超表
SELECT * FROM timescaledb_information.hypertables;

-- 查看 chunk 分布
SELECT * FROM timescaledb_information.chunks;
```

**步骤 4**：写入测试数据

```sql
INSERT INTO timeseries.token_usage_metrics (time, user_id, model, task_type, input_tokens, output_tokens, total_tokens)
VALUES
  (now() - INTERVAL '1 day', 'user1', 'deepseek-chat', 'simple_chat', 500, 300, 800),
  (now() - INTERVAL '1 day', 'user1', 'deepseek-chat', 'knowledge_qa', 1200, 800, 2000),
  (now() - INTERVAL '2 days', 'user2', 'claude-sonnet', 'simple_chat', 400, 600, 1000),
  (now(), 'user1', 'deepseek-chat', 'simple_chat', 300, 200, 500);
```

**步骤 5**：执行聚合查询

```sql
-- 按天统计 Token 用量
SELECT
  date_trunc('day', time) as day,
  model,
  SUM(total_tokens) as total
FROM timeseries.token_usage_metrics
GROUP BY day, model
ORDER BY day DESC;

-- 按用户统计 Token 用量排名
SELECT user_id, COUNT(*) as calls, SUM(total_tokens) as total
FROM timeseries.token_usage_metrics
GROUP BY user_id
ORDER BY total DESC;
```

## 视频学习资源

在 B 站搜索以下关键词：
1. "TimescaleDB 入门" — 理解超表和时序数据的基本概念
2. "PostgreSQL schema 命名空间" — 理解 schema 的作用和最佳实践
3. "时序数据库 InfluxDB vs TimescaleDB" — 对比不同时序数据库的优劣

## 常见问题与排错

### Q1: TimescaleDB 和普通 PostgreSQL 表有什么区别？
TimescaleDB 是 PostgreSQL 的扩展。本质上它还是 PostgreSQL，只是多了超表和其他时序优化函数。你仍然可以用 SQL、用 ORM、用所有 PostgreSQL 生态。

### Q2: 超表一定比普通表快吗？
对于时序查询（带时间范围的聚合），超表快得多（分区裁剪）。对于单条查询（`WHERE id = xxx`），差别不大。

### Q3: chunk 的大小怎么设置？
默认 7 天。可以通过 `chunk_time_interval` 参数调整：
```sql
SELECT create_hypertable('mytable', 'time', chunk_time_interval => INTERVAL '1 day');
```
chunk 太小（如 1 小时）：分区过多，管理开销大
chunk 太大（如 1 年）：分区裁剪效果差

### Q4: 时序数据需要保留多久？
GrassSea 的策略：保留 90 天的细粒度数据，90 天之前的聚合后删除。TimescaleDB 支持自动数据保留策略：
```sql
SELECT add_retention_policy('timeseries.token_usage_metrics', INTERVAL '90 days');
```

## 练习任务

1. **分析查询编写**：为每张时序表编写 2 个典型的业务分析 SQL（共 8 条），包含时间过滤和维度聚合。

2. **数据量估算**：假设 GrassSea 每天有 1000 次 LLM 调用、500 次 API 请求、200 次工具调用、50 个会话。估算 30 天、90 天、365 天的数据量。

3. **Grafana 面板设计**：设计 3 个 Grafana 面板（Token 用量趋势、API 延迟分布、工具调用成功率），写出每个面板的 SQL 查询。

4. **压缩研究**：TimescaleDB 支持数据压缩（对老 chunk 进行列式压缩）。研究压缩配置，计算 90 天数据的压缩率。
