# GrassSea AI — 团队可维护文件清单

> 生成日期: 2026-07-04 · 总文件数: **155** · 总代码行数: **~16,000**

本文档列出项目中所有团队可直接修改维护的源文件（已排除 `node_modules`、`.git`、`dist`、`__pycache__` 等自动生成目录）。

---

## 根目录配置 (12 文件)

```
.env.example                        73  行  环境变量模板
.gitignore                          56  行  Git 忽略规则
Makefile                           109  行  开发命令
README.md                          298  行  项目文档
docker-compose.yml                 298  行  Docker 编排
killall.bat                         22  行  一键杀进程
pyproject.toml                      90  行  Python 项目配置
start.bat                          197  行  一键启动 (Windows)
start.sh                           129  行  一键启动 (Linux/macOS)
stop.bat                            39  行  一键停止 (Windows)
```

---

## 共享库 `shared/` (24 文件, ~1,500 行)

### 配置与工具 `shared/utils/`
```
shared/utils/__init__.py             1  行
shared/utils/config.py             169  行  全局配置管理 (Settings)
shared/utils/logging.py            113  行  结构化日志
```

### 数据模型 `shared/models/`
```
shared/models/database.py          133  行  数据库连接 (PG/Mongo/Redis/Milvus)

shared/models/postgres/__init__.py  23  行
shared/models/postgres/base.py      29  行  SQLAlchemy 基类
shared/models/postgres/user.py      66  行  用户/角色模型
shared/models/postgres/project.py   53  行  项目模型
shared/models/postgres/task.py      63  行  任务记录模型
shared/models/postgres/offset_table.py  41  行  型值表模型
shared/models/postgres/todo.py      63  行  待办事项模型
shared/models/postgres/system_config.py 26  行  系统配置模型
shared/models/postgres/prompt_template.py 39  行  Prompt 模板模型

shared/models/mongodb/collections.py 129  行  MongoDB 集合与索引

shared/models/timescale/__init__.py  14  行
shared/models/timescale/metrics.py   99  行  时序指标模型

shared/models/alembic/alembic.ini    42  行  数据库迁移配置
shared/models/alembic/env.py         73  行  迁移环境
```

### Repository 数据访问层 `shared/models/repository/`
```
shared/models/repository/__init__.py      14  行
shared/models/repository/base.py          78  行  通用 CRUD
shared/models/repository/user.py          62  行  用户 Repository
shared/models/repository/project.py       56  行  项目 Repository
shared/models/repository/task.py          72  行  任务 Repository
shared/models/repository/conversation.py 108  行  对话 Repository (MongoDB)
```

### 接口协议 `shared/protocols/`
```
shared/protocols/agent.py           116  行  Agent 协议与注册中心
shared/protocols/tool.py            114  行  Tool 协议与注册中心
```

### 中间件 `shared/middleware/`
```
shared/middleware/observability.py   71  行  OpenTelemetry 埋点
shared/middleware/security.py       151  行  JWT/RBAC/API Key/审计
```

---

## 后端服务 `services/` (11 文件, ~2,200 行)

### 模型网关 `services/model_gateway/`
```
services/model_gateway/main.py      269  行  /v1/chat/completions + SSE 流式
services/model_gateway/router.py    303  行  多模型路由 (DeepSeek/Claude)
services/model_gateway/token_tracker.py 80  行  Token 统计
```

### 知识库/RAG `services/knowledge_service/`
```
services/knowledge_service/main.py  233  行  RAG 查询/文档上传 API
services/knowledge_service/ingestion.py 338  行  文档预处理 + Milvus 索引
services/knowledge_service/retrieval.py 302  行  双路混合检索 (稠密+BM25)
services/knowledge_service/reranker.py  114  行  Cross-encoder 重排序
services/knowledge_service/generator.py 170  行  带引用标注的答案生成
```

### 智能体编排 `services/agent_service/`
```
services/agent_service/main.py      202  行  编排 API + WebSocket
services/agent_service/intent.py    194  行  意图识别 (规则+LLM)
services/agent_service/planner.py   232  行  任务规划 (DAG + ReAct)
services/agent_service/fsm.py       142  行  会话状态机 (18 状态)
services/agent_service/registry.py  104  行  智能体注册中心
services/agent_service/executor.py  168  行  DAG 执行引擎
```

### 对话/API 网关 `services/chat_service/`
```
services/chat_service/main.py       101  行  API 网关 + 路由转发
services/chat_service/auth.py       143  行  JWT 登录/注册
services/chat_service/config_api.py 171  行  Web 配置管理 API
```

---

## 业务智能体 `agents/` (10 文件, ~470 行)

```
agents/pm_agent/agent.py            110  行  项目经理 Agent
agents/naval_arch_agent/agent.py    130  行  船舶工程师 Agent (稳性/阻力/型线)
agents/review_agent/agent.py        119  行  审查 Agent (规范+合规报告)
agents/cad_agent/agent.py            42  行  CAD Agent (绘图/解析)
agents/research_agent/agent.py       32  行  研究员 Agent (文献/简报)
agents/doc_agent/agent.py            32  行  文档 Agent (排版/PDF)
```

---

## 工具库 `tools/` (15 文件, ~380 行)

```
tools/base/registry.py              114  行  工具注册中心 (热插拔)

tools/compliance/reg_check.py        39  行  规范合规审查
tools/computation/hydrostatics.py    27  行  静水力计算
tools/computation/stability.py       30  行  稳性分析
tools/computation/resistance.py      30  行  阻力计算 (Holtrop)
tools/computation/hull_transform.py  25  行  船型改造

tools/cad/cad_draw.py                24  行  CAD 图纸生成
tools/cad/cad_parse.py               18  行  CAD 图纸解析
tools/cad/dwg_converter.py           19  行  DWG 格式转换

tools/file/xlsx_parser.py            23  行  表格解析
tools/file/pdf_parser.py             22  行  PDF 解析
tools/file/ocr_engine.py             23  行  图纸 OCR
tools/file/web_search.py             23  行  联网搜索
tools/file/todo_manager.py           24  行  待办管理

tools/report/report_gen.py           26  行  报告生成
```

---

## 前端 `frontend/` (17 文件, ~6,300 行)

### 配置
```
frontend/package.json                34  行  npm 依赖声明
frontend/tsconfig.json               23  行  TypeScript 配置
frontend/vite.config.ts              17  行  Vite 构建配置
frontend/index.html                  13  行  HTML 入口
```

### 入口与样式
```
frontend/src/main.tsx                35  行  React 入口
frontend/src/App.tsx                 52  行  路由 + 三栏布局
frontend/src/index.css               98  行  全局样式 (Quiet Luxury 设计系统)
```

### 通用组件 `frontend/src/components/`
```
frontend/src/components/TopNav.tsx    67  行  顶部磨砂玻璃导航
frontend/src/components/Sidebar.tsx  143  行  左侧竖向功能栏
frontend/src/components/ShimmerBar.tsx 20  行  底部渐变进度条
frontend/src/components/DAGPanel.tsx 118  行  DAG 任务拓扑可视化
```

### 页面 `frontend/src/pages/`
```
frontend/src/pages/Login.tsx         133  行  登录页
frontend/src/pages/Chat.tsx          229  行  工程对话画布
frontend/src/pages/KnowledgeBase.tsx 113  行  知识库管理
frontend/src/pages/TaskCenter.tsx     94  行  智能体任务中心
frontend/src/pages/Settings.tsx      175  行  系统配置页
```

### 状态管理 `frontend/src/stores/`
```
frontend/src/stores/authStore.ts      29  行  认证状态 (Zustand)
frontend/src/stores/chatStore.ts      37  行  对话状态 (Zustand)
frontend/src/stores/uiStore.ts        15  行  UI 状态
```

### API `frontend/src/api/`
```
frontend/src/api/index.ts             52  行  Axios 客户端
```

---

## 基础设施 `infrastructure/` (16 文件, ~600 行)

### Docker
```
infrastructure/docker/Dockerfile                  40  行  通用服务镜像
infrastructure/docker/Dockerfile.model-gateway    34  行  模型网关镜像
infrastructure/docker/postgres/init/01-init-extensions.sql  8  行  TimescaleDB 扩展
infrastructure/docker/mongodb/init/init.js        37  行  MongoDB 索引
infrastructure/docker/prometheus/prometheus.yml   31  行  Prometheus 配置
infrastructure/docker/grafana/dashboards/grasssea-main.json 58  行  运营看板
infrastructure/docker/grafana/datasources/prometheus.yml  9  行  数据源
infrastructure/docker/nginx/grasssea.conf         49  行  Nginx 生产配置
```

### K3s 部署
```
infrastructure/k3s/namespace.yaml         10  行  Namespace
infrastructure/k3s/configmap.yaml         31  行  非敏感配置
infrastructure/k3s/secret.yaml            23  行  密钥模板
infrastructure/k3s/deployments/model-gateway.yaml  65  行  Deployment + Service
infrastructure/k3s/ingress.yaml           40  行  Ingress (TLS)
infrastructure/k3s/persistent-volumes.yaml 43  行  PVC
infrastructure/k3s/casbin-rbac.yaml       17  行  RBAC 模型
infrastructure/k3s/casbin-policy.csv      38  行  RBAC 策略
```

### Nginx
```
infrastructure/nginx/grasssea.conf        47  行  开发环境反向代理
```

---

## 运维脚本 `scripts/` (3 文件, ~340 行)

```
scripts/init_minio.py                 89  行  MinIO bucket 初始化
scripts/seed_data.py                 133  行  数据库种子数据
scripts/backup_db.py                 116  行  数据库备份 (PG + Mongo)
```

---

## 测试 `tests/` (4 文件, ~370 行)

```
tests/unit/test_config.py             58  行  配置模块测试
tests/unit/test_logging.py            44  行  日志模块测试
tests/unit/test_model_gateway.py      87  行  模型网关测试
tests/unit/test_rag.py               182  行  RAG 引擎测试
```

---

## CI/CD `.github/` (1 文件)

```
.github/workflows/ci.yml              70  行  Lint → Test → Build → Deploy
```

---

## 设计文档与日记 (6 文件)

```
AI开发提示词/01-项目框架设计提示词.md   143  行
AI开发提示词/02-分阶段开发提示词.md     263  行
AI开发提示词/03-webUI设计提示词.md       39  行
docs/dev-guide/deployment.md            93  行  部署指南
项目开发日记/2026-06-25.md             37  行
项目开发日记/2026-06-26.md             18  行
项目开发日记/2026-07-03.md             15  行
```

---

## 📊 统计总览

| 类别 | 文件数 | 代码行数 |
|------|--------|----------|
| 共享库 `shared/` | 24 | ~1,500 |
| 后端服务 `services/` | 11 | ~2,200 |
| 智能体 `agents/` | 10 | ~470 |
| 工具库 `tools/` | 15 | ~380 |
| 前端 `frontend/` | 17 | ~1,100 |
| 基础设施 | 16 | ~600 |
| 脚本 `scripts/` | 3 | ~340 |
| 测试 `tests/` | 4 | ~370 |
| 配置与文档 | 18 | ~1,500 |
| 根目录配置 | 10 | ~1,200 |
| **总计** | **~155** | **~9,700** |

> 注：行数不含 `package-lock.json`（自动生成，4,961 行）和设计提示词文档。

---

## 🎯 按修改频率分类

### 高频修改（业务逻辑迭代）
- `agents/*/agent.py` — 各智能体的核心逻辑
- `tools/*/*.py` — 工具实现
- `services/agent_service/intent.py` — 意图识别规则
- `services/agent_service/planner.py` — 任务规划逻辑
- `frontend/src/pages/*.tsx` — 前端页面

### 中频修改（配置与扩展）
- `services/knowledge_service/*.py` — RAG 参数调优
- `services/model_gateway/router.py` — 模型路由策略
- `shared/models/postgres/*.py` — 新增数据表
- `shared/protocols/*.py` — 接口协议扩展

### 低频修改（基础设施）
- `docker-compose.yml` — 中间件编排
- `infrastructure/k3s/*.yaml` — K3s 部署清单
- `.github/workflows/ci.yml` — CI/CD 流水线
- `shared/utils/config.py` — 配置项定义
