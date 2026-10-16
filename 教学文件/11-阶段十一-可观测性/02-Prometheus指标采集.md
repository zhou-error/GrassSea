# 02 - Prometheus 指标采集

> ⚠️ **范围说明（项目定位：个人使用）**
>
> 本章讲解的集群部署 / CI/CD / 可观测性属于通用工程知识，**当前项目不包含这部分能力**：
> 相关流水线与部署清单已从仓库移除，对应容器配置也已从 `docker-compose.yml` 移除。
> 本章可作为学习资料阅读，但无需在本项目中落地。

## 学习目标

1. 理解 Prometheus 的 Pull 模型（拉取式采集）
2. 掌握 Counter、Gauge、Histogram 三种核心指标类型
3. 理解 Prometheus 配置文件的结构和采集目标配置
4. 能够在 FastAPI 应用中暴露 `/metrics` 端点

## 前置知识

- 理解 HTTP 协议的基本概念
- 了解什么是"监控"（Monitoring）
- 了解 YAML 文件的基本格式

## 概念讲解

### Prometheus 的 Pull 模型

传统的监控工具（如 Nagios、Zabbix）使用 Push 模型：被监控的服务主动把数据推送到监控中心。Prometheus 反其道而行，使用 Pull 模型：Prometheus Server 定时去各个服务"拉取"指标数据。

```
Push 模型（传统）:
┌──────────┐  推送数据    ┌──────────────┐
│ 服务A     │────────────▶│               │
│ 服务B     │────────────▶│ 监控中心      │
│ 服务C     │────────────▶│               │
└──────────┘              └──────────────┘
  问题: 监控中心被攻击 → 所有服务数据泄露
        服务挂了 → 监控中心不知道（因为它不会主动推了）

Pull 模型（Prometheus）:
┌──────────────┐  定时抓取    ┌──────────┐
│              │────────────▶│ /metrics  │ 服务A
│  Prometheus  │◀────────────│           │
│  Server      │             └──────────┘
│              │  定时抓取    ┌──────────┐
│              │────────────▶│ /metrics  │ 服务B
│              │◀────────────│           │
└──────────────┘             └──────────┘
  优势: Prometheus 掌握主动权，知道哪些服务"失联"了
        服务只需暴露一个 HTTP 端点，无需知道监控中心在哪里
```

### 三种核心指标类型

```
Counter (计数器) — 只增不减
┌────────────────────────────────────────────────┐
│ 适用场景: 请求总数、错误次数、任务完成数        │
│                                                │
│ http_requests_total{method="GET"} = 15423      │
│ http_requests_total{method="POST"} = 8921      │
│                                                │
│ 特点: 只会增加，不会减少（除非服务重启）        │
│ 用法: rate(http_requests_total[5m])            │
│       ↑ 计算每秒增长率，而不是直接看总数        │
└────────────────────────────────────────────────┘

Gauge (仪表盘) — 可增可减
┌────────────────────────────────────────────────┐
│ 适用场景: 内存使用量、并发连接数、队列长度      │
│                                                │
│ active_connections = 42                        │
│ queue_length = 158                             │
│                                                │
│ 特点: 可以上升也可以下降                       │
│ 用法: 直接使用，或 avg_over_time(gauge[5m])    │
└────────────────────────────────────────────────┘

Histogram (直方图) — 分布统计
┌────────────────────────────────────────────────┐
│ 适用场景: 请求延迟、响应体大小                  │
│                                                │
│ http_request_duration_seconds_bucket{le="0.1"} = 500  │
│ http_request_duration_seconds_bucket{le="0.5"} = 1200 │
│ http_request_duration_seconds_bucket{le="1.0"} = 1450 │
│                                                │
│ 解读: 500个请求在100ms内完成                    │
│       1200个请求在500ms内完成                   │
│       1450个请求在1000ms内完成                  │
│                                                │
│ 用法: histogram_quantile(0.95, ...)            │
│       ↑ 计算 P95 延迟（95%的请求在此时间内）   │
└────────────────────────────────────────────────┘
```

### PromQL 快速入门

PromQL 是 Prometheus 的查询语言。几个常用模式：

```
# 计算每秒请求速率（最近5分钟）
rate(http_requests_total[5m])

# 计算错误率（最近5分钟）
rate(http_requests_total{status=~"5.."}[5m])
/
rate(http_requests_total[5m])

# 计算 P99 延迟
histogram_quantile(0.99,
  rate(http_request_duration_seconds_bucket[5m]))

# 内存使用百分比
(process_resident_memory_bytes / total_memory_bytes) * 100
```

## 项目代码精讲

### Prometheus 配置文件结构

GrassSea 的 Prometheus 配置在 `infrastructure/docker/prometheus/prometheus.yml`：

```yaml
# 第4-5行: 全局配置
global:
  scrape_interval: 15s        # 每15秒抓取一次
  evaluation_interval: 15s    # 每15秒评估告警规则
```

**逐段解析**：
- `scrape_interval` — 抓取频率。15秒是合理的默认值。太短（如1秒）会增加 Prometheus 和被监控服务的负载；太长（如5分钟）会导致粒度太粗，短时波动看不到。
- `evaluation_interval` — 告警规则评估频率。当定义"如果 5xx 错误率 > 5% 就告警"的规则时，Prometheus 每隔这个时间检查一次。

```yaml
# 第8-18行: GrassSea 服务采集
scrape_configs:
  - job_name: "grasssea-services"
    static_configs:
      - targets:
          - "host.docker.internal:8000"   # API 网关
          - "host.docker.internal:8001"   # 对话服务
          - "host.docker.internal:8002"   # 智能体服务
          - "host.docker.internal:8003"   # 知识库服务
          - "host.docker.internal:8004"   # 模型网关
    metrics_path: /metrics
    scrape_interval: 10s
```

**逐段解析**：
1. `job_name` — 采集任务的名称。同一 Job 下的 Target 通常属于同一类服务。
2. `static_configs` — 静态配置方式，手动列出所有目标。GrassSea 在 Docker 环境中使用 `host.docker.internal` 来从容器内访问宿主机上运行的服务。生产环境（K3s）中会改用 Kubernetes 服务发现。
3. `metrics_path: /metrics` — 指定采集路径。每个 FastAPI 服务需要暴露这个端点，返回 Prometheus 格式的指标数据。
4. `scrape_interval: 10s` — 对 GrassSea 服务使用更频繁的抓取（10秒），因为业务指标变化快。

```yaml
# 第20-31行: 基础设施采集
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]

  - job_name: "redis"
    static_configs:
      - targets: ["redis:6379"]

  - job_name: "rabbitmq"
    static_configs:
      - targets: ["rabbitmq:15692"]
    metrics_path: /metrics
```

系统还会抓取 Prometheus 自身、Redis 和 RabbitMQ 的指标。RabbitMQ 使用 15692 端口（管理插件的 metrics 端口）。

### 在 FastAPI 中暴露 /metrics 端点

虽然 GrassSea 的 `/metrics` 端点代码未展示在已读取的文件中，但典型的实现如下：

```python
from prometheus_client import Counter, Histogram, generate_latest
from fastapi import Response

# 定义指标
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)

# 暴露 /metrics 端点
@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )
```

`Counter` 和 `Histogram` 的定义中都有 `label` 参数。Label 让你能按不同维度切分数据（如按 HTTP 方法、按端点、按状态码）。但 Label 也带来了"基数爆炸"的风险——不要把 user_id 这种高基数的值设为 label。

## 手把手实践

### 实验一：查看 Prometheus 的原始指标

1. 启动一个 GrassSea 服务
2. 访问 `http://localhost:8000/metrics`（或对应端口）
3. 观察原始指标格式：
   ```
   # HELP http_requests_total Total HTTP requests
   # TYPE http_requests_total counter
   http_requests_total{method="GET", endpoint="/health"} 42
   ```
4. 理解格式：`# HELP` 是注释，`# TYPE` 是类型声明，不带 `#` 的是实际数据行。

### 实验二：PromQL 实践

1. 启动 Prometheus（通过 Docker Compose）
2. 访问 `http://localhost:9090` 进入 Prometheus 控制台
3. 在查询框中输入以下 PromQL，观察图表：
   - `rate(http_requests_total[5m])` — 请求速率
   - `http_requests_total` — 请求总数
   - `up` — 各服务是否在线（1=正常，0=离线）

## 视频学习资源

请在 B站（bilibili.com）搜索以下关键词：

- "Prometheus 入门 监控" -- 了解 Prometheus 基础
- "PromQL 查询语法 教程" -- 学习 PromQL 常用查询
- "Grafana Prometheus 可视化" -- 将指标变成图表
- "Prometheus 四种指标类型" -- 深入理解 Counter/Gauge/Histogram/Summary

## 常见问题与排错

**Q1：为什么 Prometheus 看不到某个 Target？**

A：常见原因：1) 服务未暴露 `/metrics` 端点；2) 网络不通（防火墙/容器网络）；3) `scrape_configs` 中的地址写错。先在 Prometheus 的 Status -> Targets 页面查看状态，红色表示抓取失败。

**Q2：Label 太多导致内存爆炸怎么办？**

A：这就是"高基数问题"。每个唯一的 Label 组合会创建一条新的时间序列。如果把 `user_id` 设为 label，有 10 万用户就会产生 10 万条时间序列。解决：只在 label 中使用低基数值（如 `method`、`status`），高基数值（如 `user_id`）放到日志中。

**Q3：`rate()` 函数为什么要加 `[5m]`？**

A：`rate()` 计算的是"每秒增长率"，需要一个时间窗口来采样。`[5m]` 表示使用最近 5 分钟的数据。窗口太短（如 30s）会导致图表剧烈抖动，窗口太长（如 1h）会抹平短时波动。5 分钟是大多数场景的合理选择。

## 练习任务

1. **概念题**：Counter 和 Gauge 的核心区别是什么？分别适用于什么场景？
2. **实践题**：在 FastAPI 服务中添加两个自定义指标：一个 Counter 记录任务执行次数，一个 Histogram 记录任务执行耗时。
3. **分析题**：如果 `rate(http_requests_total{status="500"}[5m])` 的值在某个时间点突然飙升，你应该如何排查？请写出你的排查步骤。
4. **配置题**：修改 `prometheus.yml`，添加一个抓取 PostgreSQL 监控指标的任务（提示：PostgreSQL exporter 通常监听 9187 端口）。
