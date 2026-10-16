# 03 - Grafana 看板搭建

> ⚠️ **范围说明（项目定位：个人使用）**
>
> 本章讲解的集群部署 / CI/CD / 可观测性属于通用工程知识，**当前项目不包含这部分能力**：
> 相关流水线与部署清单已从仓库移除，对应容器配置也已从 `docker-compose.yml` 移除。
> 本章可作为学习资料阅读，但无需在本项目中落地。

## 学习目标

1. 理解 Grafana 的数据源（Data Source）和看板（Dashboard）概念
2. 掌握 Grafana 面板（Panel）的配置方法
3. 能够将 Prometheus 指标可视化为折线图、柱状图等
4. 了解 GrassSea 运营看板的设计思路

## 前置知识

- 理解阶段十一第2章的 Prometheus 指标采集
- 了解 PromQL 的基础查询语法
- 了解 JSON 的基本格式

## 概念讲解

### Grafana 在可观测性栈中的位置

你可能听过"LGTM 技术栈"这个说法，它代表了现代可观测性的四件套：

```
LGTM 可观测性技术栈:

  L = Loki      (日志聚合)        ← 替代 ELK 中的 Elasticsearch
  G = Grafana   (可视化看板)      ← 你现在要学的东西
  T = Tempo     (分布式追踪后端)   ← 替代 Jaeger/Zipkin
  M = Mimir     (指标长期存储)     ← Prometheus 的扩展存储

简化版（GrassSea 使用）:

  Prometheus ──▶ 采集指标数据（时序数据库）
       │
       ▼
  Grafana   ──▶ 从 Prometheus 读取数据，渲染图表
       │
       ▼
  用户       ──▶ 在浏览器中查看看板
```

### Grafana 的核心概念

```
Grafana 的层次结构:

  Organization (组织)
  └── Data Source (数据源) — Prometheus / PostgreSQL / Loki
      └── Dashboard (看板) — 一个完整的监控页面
          └── Row (行) — 逻辑分组
              └── Panel (面板) — 一个具体的图表
                  ├── Query (查询) — PromQL / SQL
                  ├── Visualization (可视化) — 折线图/柱状图/表格/仪表
                  └── Alert (告警) — 阈值触发通知

实际示例:
  Organization: "GrassSea AI Team"
    Data Source: "Prometheus" (连接 http://prometheus:9090)
      Dashboard: "GrassSea AI — 运营看板"
        Row: "API 性能"
          Panel: "API 请求速率" (折线图, PromQL: rate(...))
          Panel: "API P95 延迟" (折线图)
          Panel: "错误率" (仪表盘)
        Row: "知识库服务"
          Panel: "文档上传量" (柱状图)
          Panel: "检索耗时" (热力图)
```

### Panel 的可视化类型

Grafana 提供了 20+ 种可视化类型，GrassSea 看板主要使用：

```
Time series (时序折线图) — 最常用
┌──────────────────────────────────────┐
│  /\    /\                             │
│ /  \  /  \___  查看指标随时间的变化   │
│/    \/      \                         │
│           适合: 请求速率、CPU 使用率   │
└──────────────────────────────────────┘

Stat (统计数字) — 单个大数字
┌──────────────┐
│   在线服务    │
│     5/5      │  一眼看出当前状态
│  100% 正常   │
│             适合: 服务数、错误数     │
└──────────────┘

Gauge (仪表盘) — 带阈值的半圆
┌──────────────────────┐
│    ┌─────────┐       │
│   ╱  绿色    ╲       │
│  │   42%      │     显示当前值在合理范围内
│   ╲ 黄色     ╱       │
│    └─────────┘       │
│         红色区域      │
│   适合: CPU、内存使用率│
└──────────────────────┘

Table (表格) — 多行数据
┌──────────────────────────────┐
│ 服务名     │ 请求数 │ 错误率 │
│────────────┼────────┼────────│
│ 模型网关    │ 15234  │ 0.2%   │
│ 知识库服务  │ 8921   │ 1.5%   │
│  适合: 多服务对比           │
└──────────────────────────────┘
```

## 项目代码精讲

### Grafana 数据源配置

GrassSea 的 Grafana 配置通过文件自动挂载：

**数据源**（`infrastructure/docker/grafana/datasources/prometheus.yml`）：

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

**逐段解析**：
1. `apiVersion: 1` — Grafana 配置文件的 API 版本号。
2. `type: prometheus` — 数据源类型。Grafana 支持数十种数据源（MySQL、PostgreSQL、Elasticsearch、InfluxDB 等）。
3. `access: proxy` — 访问模式。`proxy` 表示 Grafana 服务器代为请求数据源（浏览器不直接连 Prometheus）；`direct` 表示浏览器直接请求数据源。`proxy` 更安全，不需要暴露 Prometheus 到外网。
4. `url: http://prometheus:9090` — 数据源地址。这里使用 Docker 容器名 `prometheus` 作为主机名，Docker DNS 会自动解析。
5. `isDefault: true` — 设为默认数据源。新建 Panel 时自动选择这个数据源。
6. `editable: true` — 允许通过 Grafana UI 修改数据源配置。

### 看板 Panel 配置

**GrassSea 运营看板**（`infrastructure/docker/grafana/dashboards/grasssea-main.json`）的核心 Panel：

```json
{
  "id": 1,
  "title": "API 请求速率",
  "type": "timeseries",
  "targets": [
    {
      "expr": "rate(http_requests_total[5m])",
      "legendFormat": "{{method}} {{endpoint}}",
      "refId": "A"
    }
  ],
  "gridPos": { "h": 10, "w": 12, "x": 0, "y": 0 },
  "fieldConfig": {
    "defaults": {
      "custom": {
        "drawStyle": "line",
        "lineWidth": 2,
        "fillOpacity": 10,
        "showPoints": "auto"
      },
      "unit": "short"
    }
  }
}
```

**逐段解析**：

1. `"type": "timeseries"` — 使用时序折线图类型。

2. `"targets"` — 数据查询配置（核心）：
   - `"expr"` — PromQL 查询表达式。`rate(http_requests_total[5m])` 计算最近 5 分钟的每秒请求速率。
   - `"legendFormat"` — 图例格式。`{{method}}` 和 `{{endpoint}}` 是 Prometheus 返回的 Label 值，会自动替换为实际值。例如会显示为 `"GET /rag/query"`。

3. `"gridPos"` — Panel 在看板中的位置和大小：
   - `h: 10, w: 12` — 高度 10 格，宽度 12 格（看板总宽 24 格）
   - `x: 0, y: 0` — 左上角坐标为 (0, 0)

4. `"fieldConfig"` — 图表样式配置：
   - `drawStyle: "line"` — 绘制为折线
   - `lineWidth: 2` — 线宽 2 像素
   - `fillOpacity: 10` — 填充区域透明度 10%（几乎看不到填充）
   - `showPoints: "auto"` — 自动决定是否显示数据点
   - `unit: "short"` — 使用短格式单位（如 1.5k 而不是 1500）

### 看板的全局设置

```json
{
  "title": "GrassSea AI — 运营看板",
  "uid": "grasssea-main",
  "refresh": "30s",
  "time": { "from": "now-6h", "to": "now" },
  "style": "dark",
  "tags": ["grasssea"],
  "schemaVersion": 38
}
```

- `refresh: "30s"` — 每 30 秒自动刷新看板数据
- `time` — 默认显示最近 6 小时的数据
- `uid` — 看板的唯一标识符，用于 URL 引用（`/d/grasssea-main`）
- `tags` — 便于在 Grafana 中搜索和分类看板

## 手把手实践

### 实验一：通过 Docker Compose 启动 Grafana

1. 在项目根目录执行：`docker-compose up -d prometheus grafana`
2. 访问 `http://localhost:3000`（Grafana 默认端口）
3. 默认用户名/密码：`admin/admin`
4. 进入 Configuration -> Data Sources，确认 Prometheus 数据源已自动配置
5. 进入 Dashboards -> GrassSea AI 运营看板，观察图表

### 实验二：手动创建 Panel

1. 在 Grafana 中创建一个新 Dashboard
2. 点击 "Add panel"，选择 "Time series"
3. 在查询框中输入：`rate(http_requests_total[5m])`
4. 切换到 "Table view" 查看原始数据
5. 调整时间范围（右上角），观察图表变化

## 视频学习资源

请在 B站（bilibili.com）搜索以下关键词：

- "Grafana 入门教程 搭建看板" -- 从零开始搭建 Grafana 看板
- "Grafana Prometheus 可视化" -- 将 Prometheus 数据变成图表
- "Grafana Dashboard 设计" -- 学习看板设计的最佳实践
- "Grafana Alert 告警配置" -- 设置监控告警通知

## 常见问题与排错

**Q1：Grafana 显示 "No data" 怎么办？**

A：三步排查：1) 检查数据源连接是否正常（Data Sources -> Test）；2) 检查 Prometheus 是否能抓到数据（Prometheus -> Status -> Targets）；3) 检查 PromQL 查询是否正确——先在 Prometheus 控制台的 Graph 页面测试同样的查询。

**Q2：看板刷新太慢怎么办？**

A：减小 `refresh` 值（如从 30s 改为 10s）。但注意：刷新频率越高，对 Prometheus 和 Grafana 的负载越大。生产环境建议 30s-60s。

**Q3：JSON 看板文件直接修改后不生效？**

A：Grafana 的 Provisioning 机制只在启动时加载一次。修改 JSON 文件后需要重启 Grafana 容器，或者在 Grafana UI 中手动导入 JSON。

**Q4：Panel 中 `legendFormat` 的 `{{method}}` 不显示？**

A：检查 PromQL 查询的返回数据中是否真的有 `method` 这个 Label。`legendFormat` 中的变量名必须与 Prometheus 返回的 Label 名完全一致（区分大小写）。

## 练习任务

1. **概念题**：Grafana 中的 Data Source、Dashboard、Panel 分别是什么？它们之间的关系是什么？
2. **实践题**：在 Grafana 中创建一个新的 Panel，展示最近 15 分钟的 5xx 错误率（提示：PromQL 使用 `status=~"5.."` 过滤状态码）。
3. **设计题**：为 GrassSea 的知识库服务设计一个看板方案，列出你需要的 Panel 和对应的 PromQL 查询（不需要实际创建，写出方案即可）。
4. **挑战题**：阅读 `grasssea-main.json` 完整文件，理解 Panel 的 `fieldConfig` 中 `thresholds` 的配置方式。在此基础上，为 "API 请求速率" Panel 添加颜色阈值——正常（< 100 req/s）为绿色，警告（100-500）为黄色，危险（> 500）为红色。
