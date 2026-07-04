# 🌊 白草沧智（GrassSea AI）

> **以草木之真知，破船海之万难**

面向**船舶与海洋工程**领域的 AI 原生多智能体协作平台。以大语言模型（LLM）+ 专业知识库 + 多智能体编排 + 专业工具链为核心，为船舶行业的全生命周期（概念设计、详细设计、建造、运维）提供智能化支持。

---

## 🏗️ 系统架构

```
多端交互层 → 智能体编排层 → 业务智能体层 → 能力中台层 → 数据底座层
```

| 层级 | 说明 |
|------|------|
| **多端交互层** | React 18 SPA (Web)、API Gateway、WebSocket |
| **智能体编排层** | 意图识别、任务规划 (DAG)、会话状态机 (FSM)、多智能体协同 |
| **业务智能体层** | PM Agent、船舶工程师、CAD Agent、审查 Agent、研究员、文档 Agent |
| **能力中台层** | RAG 引擎、知识图谱 (Neo4j)、模型网关、仿真引擎、工具库 (13 个) |
| **数据底座层** | PostgreSQL + TimescaleDB、MongoDB、Milvus、MinIO、Redis、RabbitMQ |

---

## 🚀 快速开始

### 环境要求

| 软件 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 后端服务 |
| Node.js | 18+ | 前端构建 |
| Docker Desktop | 24.x+ | 中间件容器 |
| Git | 任意 | 版本管理 |

### 一键启动（Windows）

在资源管理器中打开项目目录，**双击 `start.bat`**：

1. 自动检查 Python / Node.js / Docker
2. 启动 5 个 Docker 中间件并等待就绪
3. 启动 4 个 Python 后端服务（独立窗口）
4. 自动安装前端依赖（首次）
5. 启动前端 Vite 开发服务器
6. 浏览器自动打开 `http://localhost:3000`

**停止**：双击 `stop.bat`

### 手动启动

```bash
# 1. 启动中间件
docker compose up -d postgres mongodb redis rabbitmq minio

# 2. 初始化
pip install -e ".[dev]"
python scripts/init_minio.py
python scripts/seed_data.py

# 3. 启动后端服务
python -m uvicorn services.model_gateway.main:app --host 0.0.0.0 --port 8004 --reload &
python -m uvicorn services.knowledge_service.main:app --host 0.0.0.0 --port 8003 --reload &
python -m uvicorn services.agent_service.main:app --host 0.0.0.0 --port 8002 --reload &
python -m uvicorn services.chat_service.main:app --host 0.0.0.0 --port 8011 --reload &

# 4. 启动前端
cd frontend && npm install && npm run dev
```

### 服务端口

| 服务 | 端口 | 地址 |
|------|------|------|
| 前端 (Vite) | 3000 | `http://localhost:3000` |
| 对话服务 (API) | 8011 | `http://localhost:8011/health` |
| 智能体编排 | 8002 | `http://localhost:8002/health` |
| 知识库/RAG | 8003 | `http://localhost:8003/health` |
| 模型网关 | 8004 | `http://localhost:8004/health` |

### 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `admin` | `admin123` | 系统管理员 |
| `engineer` | `engineer123` | 船舶工程师 |
| `guest` | `guest123` | 访客 |

---

## 📚 项目结构

```
grasssea/
├── agents/                     # 业务智能体
│   ├── base/                   #   Agent 基类
│   ├── pm_agent/               #   项目经理 Agent (任务分解/资源分配/进度聚合)
│   ├── naval_arch_agent/       #   船舶工程师 Agent (稳性/阻力/型线设计)
│   ├── cad_agent/              #   CAD Agent (图纸绘制/解析)
│   ├── review_agent/           #   审查 Agent (规范审查/合规报告)
│   ├── research_agent/         #   研究员 Agent (文献检索/简报)
│   └── doc_agent/              #   文档 Agent (报告排版/PDF生成)
│
├── services/                   # 后端微服务
│   ├── chat-service/           #   对话服务 (API网关 + 认证)
│   ├── agent-service/          #   智能体编排 (意图识别/任务规划/FSM/注册中心)
│   ├── knowledge-service/      #   知识库服务 (RAG引擎/文档处理/检索/生成)
│   ├── model-gateway/          #   模型网关 (OpenAI兼容/多模型路由/Token统计)
│   ├── simulation-service/     #   仿真计算服务 (预留)
│   ├── tool-service/           #   工具管理服务 (预留)
│   ├── report-service/         #   报告生成服务 (预留)
│   └── stats-service/          #   数据统计服务 (预留)
│
├── tools/                      # 工具库 (13个)
│   ├── base/                   #   工具基类 + 注册中心 (热插拔)
│   ├── compliance/             #   规范审查 (reg_check)
│   ├── cad/                    #   CAD 工具 (cad_draw/cad_parse/dwg_converter)
│   ├── computation/            #   船舶计算 (hydrostatics/stability/resistance/hull_transform)
│   ├── report/                 #   报告生成 (report_gen)
│   └── file/                   #   文件处理 (xlsx/pdf/ocr/web_search/todo)
│
├── shared/                     # 共享库
│   ├── models/                 #   数据模型 (PostgreSQL/MongoDB/TimescaleDB/Repository)
│   ├── protocols/              #   接口协议 (Agent/Tool)
│   ├── middleware/             #   中间件 (安全/可观测性)
│   └── utils/                  #   工具 (配置/日志)
│
├── frontend/                   # Web 前端 (React 18 + TypeScript + Ant Design)
│   └── src/
│       ├── components/         #   通用组件
│       ├── pages/              #   页面 (Login/Chat/KnowledgeBase/TaskCenter)
│       ├── stores/             #   状态管理 (Zustand)
│       └── api/                #   API 客户端
│
├── infrastructure/             # 基础设施配置
│   ├── docker/                 #   Dockerfile / 初始化脚本
│   ├── k3s/                    #   K3s 部署清单
│   └── nginx/                  #   Nginx 配置
│
├── docs/                       # 项目文档
│   ├── api-spec/
│   └── dev-guide/
│
├── tests/                      # 测试
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── scripts/                    # 运维脚本
├── docker-compose.yml          # Docker 编排
├── pyproject.toml              # Python 配置
├── start.bat / stop.bat        # 一键启停 (Windows)
├── start.sh                    # 一键启动 (Linux/macOS)
└── Makefile                    # 开发命令
```

---

## 🤖 智能体

| Agent | ID | 能力 | 工具 |
|-------|-----|------|------|
| 项目经理 | `pm_agent` | 任务分解、资源分配、进度聚合 | report_gen |
| 船舶工程师 | `naval_arch_agent` | 型线设计、稳性计算、阻力计算、规范审查 | hydrostatics, stability, resistance, hull_transform, cad_draw |
| CAD Agent | `cad_agent` | 图纸绘制、曲线光顺、图纸解析 | cad_draw, cad_parse, dwg_converter |
| 审查 Agent | `review_agent` | 规范条文匹配、合规标注、审查报告 | reg_check, report_gen |
| 研究员 | `research_agent` | 文献检索、信息提炼、每日简报 | web_search, pdf_parser |
| 文档 Agent | `doc_agent` | 报告排版、PDF生成、格式校验 | report_gen |

## 🔧 工具库

| 工具 | ID | 类别 | 说明 |
|------|-----|------|------|
| 规范审查 | `reg_check` | 合规 | 基于规范条文自动审查设计参数 |
| CAD 绘制 | `cad_draw` | CAD | 型线图绘制、曲线光顺 |
| CAD 解析 | `cad_parse` | CAD | DWG/DXF 图纸解析 |
| DWG 转换 | `dwg_converter` | 文件 | DWG ↔ DXF ↔ PDF ↔ PNG |
| 静水力 | `hydrostatics` | 计算 | 排水量、浮心、稳心、邦戎曲线 |
| 稳性分析 | `stability` | 计算 | 完整稳性、破舱稳性、横摇周期 |
| 阻力计算 | `resistance` | 计算 | Holtrop 法、ITTC 法 |
| 船型改造 | `hull_transform` | 计算 | 母型船变换、参数优化 |
| 报告生成 | `report_gen` | 报告 | Markdown → PDF 规范排版 |
| 表格解析 | `xlsx_parser` | 文件 | 型值表结构化提取 |
| PDF 解析 | `pdf_parser` | 文件 | 规范文件文本/表格提取 |
| 图纸 OCR | `ocr_engine` | 文件 | 扫描图纸文字识别 |
| 联网搜索 | `web_search` | 检索 | Brave/Bing API |
| 待办管理 | `todo_manager` | 文件 | 创建/更新/提醒待办 |

---

## 🗄️ 数据库

| 数据库 | 用途 |
|--------|------|
| **PostgreSQL 15** | 用户/权限、项目、任务记录、型值表、待办、Prompt模板 (10 张表) |
| **TimescaleDB** | Token统计、API延迟、工具调用频次、会话统计 (4 张超表) |
| **MongoDB 7** | 对话历史、审查报告、Agent配置、任务DAG、调研报告、LLM调用日志 (6 个集合) |
| **Milvus 2.4** | 知识库向量存储、稠密+稀疏混合检索 |
| **Neo4j 5.x** | 船舶本体知识图谱 (可延后) |
| **MinIO** | 图纸/DWG、PDF 文档、仿真文件、报告 |
| **Redis 7** | 会话缓存、LLM响应缓存、限流计数、分布式锁 |

---

## 🔐 安全

| 措施 | 实现 |
|------|------|
| 认证 | JWT (Access Token 30min + Refresh Token 7d) |
| 鉴权 | RBAC 5 角色 (admin/project_lead/engineer/guest/api_user) + Casbin |
| API Key | HMAC-SHA256 签名认证 |
| 传输加密 | TLS 1.3 |
| 文件访问 | MinIO 预签名 URL (15min 有效) |
| 审计日志 | 全操作记录到 TimescaleDB |
| 密码存储 | SHA256 + Salt (开发) / bcrypt (生产) |

---

## 📊 可观测性

| 组件 | 用途 | 地址 |
|------|------|------|
| OpenTelemetry | 全链路追踪埋点 | — |
| Jaeger | 分布式追踪可视化 | `:16686` |
| Prometheus | 指标采集 | `:9090` |
| Grafana | 运营看板 | `:3000` (admin/grasssea-grafana) |
| 结构化日志 | JSON 格式 + Trace ID | 控制台 |

---

## 🧪 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行并生成覆盖率报告
pytest tests/ -v --cov --cov-report=html

# 仅运行单元测试
pytest tests/unit/ -v

# 运行特定模块测试
pytest tests/ -v -k "rag"
```

---

## 📦 CI/CD

GitHub Actions 流水线 (`.github/workflows/ci.yml`)：

```
Push → Lint (ruff) → Type Check (mypy) → Test (pytest) → Build (Docker) → Deploy (K3s Rolling Update)
```

---

## 🚢 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI (Python) | 0.110+ |
| 任务队列 | Celery + RabbitMQ | 5.x / 3.x |
| LLM 网关 | 自研 Model Gateway | — |
| RAG 框架 | 自研 RAG Engine | — |
| 向量数据库 | Milvus | 2.4+ |
| 关系型数据库 | PostgreSQL + TimescaleDB | 15 / 2.x |
| 文档数据库 | MongoDB | 7.x |
| 对象存储 | MinIO | latest |
| 缓存 | Redis | 7.x |
| 图数据库 | Neo4j (可选) | 5.x |
| 前端 | React + TypeScript + Ant Design | 18 / 5.x |
| 状态管理 | Zustand + TanStack Query | 4.x / 5.x |
| 容器编排 | K3s / Docker Compose | 1.28+ |
| 可观测性 | OpenTelemetry + Jaeger + Prometheus + Grafana | — |
| CI/CD | GitHub Actions | — |

---

## 📖 开发阶段

- [x] **阶段 0**：基础设施与环境搭建
- [x] **阶段 1**：核心数据模型与数据库设计
- [x] **阶段 2**：基础服务层（模型网关 + RAG 引擎）
- [x] **阶段 3**：编排层与基础智能体
- [x] **阶段 4**：前端与多端交互层
- [x] **阶段 5**：完整智能体与工具集成
- [x] **阶段 6**：可观测性、安全与部署

---

## 📄 许可证

MIT License

---

*白草沧智（GrassSea AI）项目组 · 2026-07*
