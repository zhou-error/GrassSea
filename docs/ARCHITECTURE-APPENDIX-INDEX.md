# 附录 · 全文件与符号索引

> 本文件由脚本从源码**机械生成**，用于保证「不遗漏任何源文件」；正文见 [`ARCHITECTURE.md`](./ARCHITECTURE.md)。
> 工具开发见 [`TOOL_DEVELOPMENT_GUIDE.md`](./TOOL_DEVELOPMENT_GUIDE.md)，桌面版见 [`DESKTOP_GUIDE.md`](./DESKTOP_GUIDE.md)。

| 项 | 值 |
|---|---|
| 生成时间 | 2026-10-16 16:20:37 |
| 代码文件数 | 135 |
| 代码总行数 | 14370 |
| 类数量 | 121 |
| 提取符号数（含多行签名） | 685 |
| HTTP 路由装饰器 | 43 |
| 登记文件总数 | 179 |

**范围声明**：已排除 `node_modules`、`.venv`、`docker-data`、`data`、`.git`、`.freebuff`、`dist`、`__pycache__`、`.uv-cache`；
`教学文件/`、`ProductDesign/`、`AI开发提示词/`、`项目开发日记/` 为非代码资产，见正文第 10 章。
⚠️ 本文件随代码变动，建议每次重构后重新生成。

---

## 1. 文件索引

| # | 文件 | 行数 | 类 | 函数/方法 | 职责 |
|---:|---|---:|---:|---:|---|
| 1 | `agents/__init__.py` | 2 | 0 | 0 | — |
| 2 | `agents/base/__init__.py` | 2 | 0 | 0 | — |
| 3 | `agents/cad_agent/__init__.py` | 2 | 0 | 0 | — |
| 4 | `agents/cad_agent/agent.py` | 47 | 1 | 4 | CAD Agent — 图纸解析、型线绘制、曲线光顺、DWG 操作 |
| 5 | `agents/doc_agent/__init__.py` | 2 | 0 | 0 | — |
| 6 | `agents/doc_agent/agent.py` | 47 | 1 | 4 | 文档工程师 Agent (Doc Agent) — 报告排版、PDF 生成、格式规范校验 |
| 7 | `agents/naval_arch_agent/__init__.py` | 2 | 0 | 0 | — |
| 8 | `agents/naval_arch_agent/agent.py` | 141 | 1 | 6 | 船舶工程师 Agent (Naval Arch Agent) |
| 9 | `agents/pm_agent/__init__.py` | 2 | 0 | 0 | — |
| 10 | `agents/pm_agent/agent.py` | 112 | 1 | 5 | 项目经理 Agent (PM Agent) |
| 11 | `agents/research_agent/__init__.py` | 2 | 0 | 0 | — |
| 12 | `agents/research_agent/agent.py` | 57 | 1 | 5 | 研究员 Agent (Research Agent) — 文献检索、信息提炼、每日简报生成 |
| 13 | `agents/review_agent/__init__.py` | 2 | 0 | 0 | — |
| 14 | `agents/review_agent/agent.py` | 157 | 1 | 4 | 审查 Agent (Review Agent) |
| 15 | `app/__init__.py` | 9 | 0 | 0 | GrassSea 应用入口包 |
| 16 | `app/desktop.py` | 211 | 0 | 8 | GrassSea 桌面窗口 |
| 17 | `app/launcher.py` | 267 | 0 | 8 | GrassSea 单进程启动器 |
| 18 | `frontend/src/App.tsx` | 39 | 0 | 1 | — |
| 19 | `frontend/src/api/index.ts` | 293 | 0 | 39 | — |
| 20 | `frontend/src/components/DAGPanel.tsx` | 364 | 0 | 1 | — |
| 21 | `frontend/src/components/ShimmerBar.tsx` | 21 | 0 | 1 | — |
| 22 | `frontend/src/components/Sidebar.tsx` | 144 | 0 | 1 | — |
| 23 | `frontend/src/components/ToolTraceCard.tsx` | 104 | 0 | 1 | — |
| 24 | `frontend/src/components/TopNav.tsx` | 67 | 0 | 1 | — |
| 25 | `frontend/src/components/stepOutput.tsx` | 121 | 0 | 5 | — |
| 26 | `frontend/src/main.tsx` | 36 | 0 | 0 | — |
| 27 | `frontend/src/pages/Chat.tsx` | 539 | 0 | 2 | — |
| 28 | `frontend/src/pages/KnowledgeBase.tsx` | 530 | 0 | 1 | — |
| 29 | `frontend/src/pages/Settings.tsx` | 176 | 0 | 1 | — |
| 30 | `frontend/src/pages/TaskCenter.tsx` | 508 | 0 | 1 | — |
| 31 | `frontend/src/stores/chatStore.ts` | 46 | 0 | 1 | — |
| 32 | `frontend/src/stores/uiStore.ts` | 16 | 0 | 1 | — |
| 33 | `frontend/vite.config.d.ts` | 3 | 0 | 0 | — |
| 34 | `frontend/vite.config.ts` | 19 | 0 | 0 | — |
| 35 | `scripts/backup_db.py` | 117 | 0 | 5 | 数据库备份脚本 — 每日全量 + WAL 归档 |
| 36 | `scripts/init_db.py` | 73 | 0 | 3 | 数据库一键建表脚本（个人开发环境） |
| 37 | `scripts/init_minio.py` | 90 | 0 | 2 | MinIO bucket 初始化脚本 |
| 38 | `scripts/reset_knowledge_base.py` | 76 | 0 | 3 | 重建知识库索引 |
| 39 | `scripts/seed_data.py` | 96 | 0 | 3 | 数据库种子脚本（幂等，可重复执行） |
| 40 | `services/agent_service/__init__.py` | 2 | 0 | 0 | — |
| 41 | `services/agent_service/executor.py` | 537 | 1 | 15 | 任务执行引擎 |
| 42 | `services/agent_service/fsm.py` | 143 | 2 | 7 | 会话状态机 (Session FSM) |
| 43 | `services/agent_service/intent.py` | 213 | 3 | 6 | 意图识别模块 |
| 44 | `services/agent_service/main.py` | 461 | 3 | 15 | 智能体编排服务 (Agent Orchestration Service) |
| 45 | `services/agent_service/planner.py` | 402 | 3 | 12 | 任务规划模块 |
| 46 | `services/agent_service/registry.py` | 131 | 1 | 13 | 智能体注册中心 |
| 47 | `services/agent_service/tool_loop.py` | 285 | 1 | 9 | 模型自主工具调用循环（OpenAI function calling） |
| 48 | `services/chat_service/__init__.py` | 2 | 0 | 0 | — |
| 49 | `services/chat_service/attachments.py` | 266 | 1 | 10 | 附件处理：接收上传文件 → 提取正文 → 生成描述符 |
| 50 | `services/chat_service/config_api.py` | 303 | 2 | 8 | 系统配置管理 API — 允许用户在 Web 中修改关键配置 |
| 51 | `services/chat_service/main.py` | 350 | 0 | 22 | 对话服务 (Chat Service) — 前端 API 网关，提供路由转发到各后端服务。 |
| 52 | `services/knowledge_service/__init__.py` | 2 | 0 | 0 | — |
| 53 | `services/knowledge_service/generator.py` | 171 | 1 | 7 | 答案生成模块 |
| 54 | `services/knowledge_service/ingestion.py` | 262 | 2 | 11 | 文档预处理流水线 |
| 55 | `services/knowledge_service/main.py` | 332 | 7 | 9 | 知识库服务 (Knowledge Service) |
| 56 | `services/knowledge_service/reranker.py` | 115 | 1 | 5 | 重排序模块 |
| 57 | `services/knowledge_service/retrieval.py` | 334 | 2 | 14 | 混合检索模块 |
| 58 | `services/model_gateway/__init__.py` | 2 | 0 | 0 | — |
| 59 | `services/model_gateway/main.py` | 362 | 5 | 8 | 模型网关服务 (Model Gateway) |
| 60 | `services/model_gateway/router.py` | 409 | 3 | 11 | 模型路由器 |
| 61 | `services/model_gateway/token_tracker.py` | 81 | 1 | 4 | Token 用量统计与计费 |
| 62 | `shared/__init__.py` | 1 | 0 | 0 | — |
| 63 | `shared/middleware/__init__.py` | 2 | 0 | 0 | — |
| 64 | `shared/middleware/observability.py` | 72 | 1 | 2 | 可观测性中间件 — OpenTelemetry 自动埋点 + Prometheus 指标 |
| 65 | `shared/middleware/security.py` | 114 | 2 | 7 | 安全中间件 — RBAC + API Key + 预签名 URL + 审计日志 |
| 66 | `shared/models/__init__.py` | 1 | 0 | 0 | — |
| 67 | `shared/models/alembic/env.py` | 80 | 0 | 4 | Alembic 环境配置 |
| 68 | `shared/models/alembic/versions/__init__.py` | 2 | 0 | 0 | — |
| 69 | `shared/models/database.py` | 185 | 1 | 13 | 数据库连接管理模块（全部惰性化） |
| 70 | `shared/models/mongodb/__init__.py` | 2 | 0 | 0 | — |
| 71 | `shared/models/mongodb/collections.py` | 130 | 1 | 0 | MongoDB 集合定义与索引 |
| 72 | `shared/models/postgres/__init__.py` | 23 | 0 | 0 | — |
| 73 | `shared/models/postgres/base.py` | 30 | 2 | 0 | SQLAlchemy 基类与共享 mixin |
| 74 | `shared/models/postgres/offset_table.py` | 42 | 1 | 1 | 型值表模型 |
| 75 | `shared/models/postgres/project.py` | 55 | 2 | 1 | 项目模型 |
| 76 | `shared/models/postgres/prompt_template.py` | 40 | 1 | 1 | Prompt 模板模型 |
| 77 | `shared/models/postgres/system_config.py` | 27 | 1 | 1 | 系统配置模型 |
| 78 | `shared/models/postgres/task.py` | 64 | 3 | 1 | 任务记录模型 |
| 79 | `shared/models/postgres/todo.py` | 64 | 3 | 1 | 待办事项模型 |
| 80 | `shared/models/postgres/user.py` | 34 | 1 | 1 | 用户模型 |
| 81 | `shared/models/repository/__init__.py` | 14 | 0 | 0 | — |
| 82 | `shared/models/repository/base.py` | 79 | 1 | 8 | Repository 基类 |
| 83 | `shared/models/repository/conversation.py` | 109 | 1 | 9 | Conversation Repository (MongoDB) |
| 84 | `shared/models/repository/project.py` | 57 | 1 | 4 | Project Repository |
| 85 | `shared/models/repository/task.py` | 73 | 1 | 5 | Task Repository |
| 86 | `shared/models/timescale/__init__.py` | 15 | 0 | 0 | — |
| 87 | `shared/models/timescale/metrics.py` | 100 | 4 | 4 | TimescaleDB 时序指标模型 |
| 88 | `shared/protocols/__init__.py` | 2 | 0 | 0 | — |
| 89 | `shared/protocols/agent.py` | 117 | 6 | 11 | 智能体基础协议定义 |
| 90 | `shared/protocols/tool.py` | 115 | 5 | 12 | 工具基础协议定义 |
| 91 | `shared/utils/__init__.py` | 1 | 0 | 0 | — |
| 92 | `shared/utils/config.py` | 235 | 1 | 13 | GrassSea AI — 统一配置管理模块 |
| 93 | `shared/utils/embedding.py` | 219 | 4 | 14 | 统一的文本向量化模块 |
| 94 | `shared/utils/logging.py` | 114 | 0 | 6 | GrassSea AI — 结构化日志模块 |
| 95 | `shared/utils/secrets.py` | 155 | 0 | 7 | API Key 加密存储模块 |
| 96 | `shared/utils/workspace.py` | 258 | 1 | 11 | 工作文件夹访问（桌面模式） |
| 97 | `shared/vectorstore/__init__.py` | 40 | 0 | 1 | 向量存储抽象层 —— 按配置选择后端 |
| 98 | `shared/vectorstore/base.py` | 99 | 2 | 9 | 向量存储协议与数据结构 |
| 99 | `shared/vectorstore/local.py` | 268 | 1 | 13 | 内置向量存储 —— SQLite 持久化 + numpy 精确余弦检索 |
| 100 | `shared/vectorstore/milvus.py` | 240 | 1 | 10 | Milvus 向量存储后端 |
| 101 | `tests/__init__.py` | 2 | 0 | 0 | — |
| 102 | `tests/e2e/__init__.py` | 2 | 0 | 0 | — |
| 103 | `tests/integration/__init__.py` | 2 | 0 | 0 | — |
| 104 | `tests/unit/__init__.py` | 2 | 0 | 0 | — |
| 105 | `tests/unit/test_config.py` | 59 | 1 | 5 | 配置模块单元测试 |
| 106 | `tests/unit/test_logging.py` | 45 | 1 | 5 | 日志模块单元测试 |
| 107 | `tests/unit/test_model_gateway.py` | 88 | 2 | 8 | 模型网关单元测试 |
| 108 | `tests/unit/test_rag.py` | 183 | 5 | 18 | RAG 引擎单元测试 |
| 109 | `tools/__init__.py` | 2 | 0 | 0 | — |
| 110 | `tools/base/__init__.py` | 2 | 0 | 0 | — |
| 111 | `tools/base/registry.py` | 115 | 1 | 8 | 工具注册中心 — 支持热插拔机制 |
| 112 | `tools/bootstrap.py` | 82 | 0 | 1 | 工具引导模块 — 统一实例化并注册 tools/ 下的全部工具 |
| 113 | `tools/cad/__init__.py` | 2 | 0 | 0 | — |
| 114 | `tools/cad/cad_draw.py` | 23 | 1 | 2 | CAD 图纸生成工具 — 型线图绘制、曲线光顺 |
| 115 | `tools/cad/cad_parse.py` | 23 | 1 | 2 | CAD 图纸解析工具 — 从 DWG/DXF 提取尺寸、标注、图层 |
| 116 | `tools/cad/dwg_converter.py` | 23 | 1 | 2 | DWG 格式转换工具 — DWG ↔ DXF ↔ PDF ↔ PNG |
| 117 | `tools/compliance/__init__.py` | 2 | 0 | 0 | — |
| 118 | `tools/compliance/reg_check.py` | 23 | 1 | 2 | 规范合规审查工具 — 基于规范条文自动审查设计参数 |
| 119 | `tools/computation/__init__.py` | 2 | 0 | 0 | — |
| 120 | `tools/computation/hull_transform.py` | 78 | 1 | 2 | 船型改造工具 — 母型船变换、参数优化 |
| 121 | `tools/computation/hydrostatics.py` | 59 | 1 | 2 | 静水力计算工具 |
| 122 | `tools/computation/resistance.py` | 58 | 1 | 2 | 阻力计算工具 — Holtrop 法、ITTC 法 |
| 123 | `tools/computation/stability.py` | 65 | 1 | 2 | 稳性分析工具 — 完整稳性、破舱稳性 |
| 124 | `tools/file/__init__.py` | 2 | 0 | 0 | — |
| 125 | `tools/file/ocr_engine.py` | 23 | 1 | 2 | 图纸 OCR 工具 — 扫描图纸文字/标注识别 |
| 126 | `tools/file/pdf_parser.py` | 23 | 1 | 2 | PDF 解析工具 — 规范文件文本/表格提取 |
| 127 | `tools/file/todo_manager.py` | 23 | 1 | 2 | 待办管理工具 — 创建/更新/提醒待办事项 |
| 128 | `tools/file/web_search.py` | 23 | 1 | 2 | 联网搜索工具 — 补充最新信息 |
| 129 | `tools/file/workspace.py` | 196 | 4 | 9 | 工作文件夹工具 — 让模型按需读写用户选定文件夹中的文件 |
| 130 | `tools/file/xlsx_parser.py` | 23 | 1 | 2 | 表格解析工具 — 型值表结构化提取 |
| 131 | `tools/report/__init__.py` | 2 | 0 | 0 | — |
| 132 | `tools/report/report_gen.py` | 23 | 1 | 2 | 报告生成工具 — Markdown → PDF（规范排版） |
| 133 | `练习/00-01-练习1.py` | 19 | 0 | 2 | — |
| 134 | `练习/00-01-练习3.py` | 31 | 0 | 2 | 练习3：改造同步代码 |
| 135 | `练习/test_async.py` | 55 | 0 | 5 | — |

---

## 2. 逐文件符号明细

### `agents/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `agents/base/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `agents/cad_agent/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `agents/cad_agent/agent.py`

- **行数**：47　**类**：1　**函数/方法**：4
- **职责**：CAD Agent — 图纸解析、型线绘制、曲线光顺、DWG 操作
- **内部依赖**：`shared.protocols.agent`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 24 | class | `CADAgent` | `(BaseAgent)` |
| 25 | method | `CADAgent.__init__` | `(self)` |
| 27 | method | `CADAgent.handle_task` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |
| 34 | method | `CADAgent._draw_lines` | `(self, task: dict, context: dict) → dict` |
| 41 | method | `CADAgent._parse_drawing` | `(self, task: dict, context: dict) → dict` |

### `agents/doc_agent/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `agents/doc_agent/agent.py`

- **行数**：47　**类**：1　**函数/方法**：4
- **职责**：文档工程师 Agent (Doc Agent) — 报告排版、PDF 生成、格式规范校验
- **内部依赖**：`shared.protocols.agent`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 24 | class | `DocAgent` | `(BaseAgent)` |
| 25 | method | `DocAgent.__init__` | `(self)` |
| 27 | method | `DocAgent.handle_task` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |
| 34 | method | `DocAgent._report_gen` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |
| 41 | method | `DocAgent._format_check` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |

### `agents/naval_arch_agent/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `agents/naval_arch_agent/agent.py`

- **行数**：141　**类**：1　**函数/方法**：6
- **职责**：船舶工程师 Agent (Naval Arch Agent)
- **内部依赖**：`shared.protocols.agent`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 27 | class | `NavalArchAgent` | `(BaseAgent)` |
| 30 | method | `NavalArchAgent.__init__` | `(self)` |
| 33 | method | `NavalArchAgent.handle_task` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |
| 46 | method | `NavalArchAgent._stability_calculation` | `(self, params: dict, callbacks: AgentCallbacks) → dict` |
| 95 | method | `NavalArchAgent._hull_design` | `(self, params: dict, callbacks: AgentCallbacks) → dict` |
| 109 | method | `NavalArchAgent._resistance_calculation` | `(self, params: dict, callbacks: AgentCallbacks) → dict` |
| 139 | method | `NavalArchAgent._general_analysis` | `(self, params: dict, callbacks: AgentCallbacks) → dict` |

### `agents/pm_agent/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `agents/pm_agent/agent.py`

- **行数**：112　**类**：1　**函数/方法**：5
- **职责**：项目经理 Agent (PM Agent)
- **内部依赖**：`shared.protocols.agent`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 51 | class | `PMAgent` | `(BaseAgent)` |
| 54 | method | `PMAgent.__init__` | `(self)` |
| 57 | method | `PMAgent.handle_task` | `(self, task: dict, context: dict, callbacks: AgentCallbacks,) → dict` |
| 76 | method | `PMAgent._decompose_task` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |
| 85 | method | `PMAgent._allocate_resources` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |
| 94 | method | `PMAgent._aggregate_results` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |

### `agents/research_agent/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `agents/research_agent/agent.py`

- **行数**：57　**类**：1　**函数/方法**：5
- **职责**：研究员 Agent (Research Agent) — 文献检索、信息提炼、每日简报生成
- **内部依赖**：`shared.protocols.agent`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 25 | class | `ResearchAgent` | `(BaseAgent)` |
| 26 | method | `ResearchAgent.__init__` | `(self)` |
| 28 | method | `ResearchAgent.handle_task` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |
| 37 | method | `ResearchAgent._literature_search` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |
| 44 | method | `ResearchAgent._daily_brief` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |
| 51 | method | `ResearchAgent._trend_analysis` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |

### `agents/review_agent/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `agents/review_agent/agent.py`

- **行数**：157　**类**：1　**函数/方法**：4
- **职责**：审查 Agent (Review Agent)
- **内部依赖**：`shared.protocols.agent`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 55 | class | `ReviewAgent` | `(BaseAgent)` |
| 65 | method | `ReviewAgent.__init__` | `(self)` |
| 68 | method | `ReviewAgent.handle_task` | `(self, task: dict, context: dict, callbacks: AgentCallbacks,) → dict` |
| 82 | method | `ReviewAgent._regulation_check` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |
| 134 | method | `ReviewAgent._generate_report` | `(self, task: dict, context: dict, callbacks: AgentCallbacks) → dict` |

### `app/__init__.py`

- **行数**：9　**类**：0　**函数/方法**：0
- **职责**：GrassSea 应用入口包
- **内部依赖**：（无）

（无类 / 函数定义）

### `app/desktop.py`

- **行数**：211　**类**：0　**函数/方法**：8
- **职责**：GrassSea 桌面窗口
- **内部依赖**：`app`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 39 | function | `find_browser` | `() → str \| None` |
| 51 | function | `wait_for_backend` | `(url: str, timeout: float = 60.0) → bool` |
| 64 | function | `launch_browser_app` | `(url: str, profile_dir: Path, width: int = 1440, height: int = 920) → subprocess.Popen \| None` |
| 91 | function | `try_pywebview` | `(url: str, title: str, width: int, height: int) → bool` |
| 104 | function | `open_in_browser` | `(url: str) → None` |
| 111 | function | `run` | `(url: str, title: str = "白草沧智 GrassSea AI", width: int = 1440, height: int = 920, prefer: str = "auto",) → str` |
| 137 | function | `_profile_in_use` | `(profile_dir: Path) → bool` |
| 157 | function | `main` | `(argv: list[str] \| None = None) → int` |

### `app/launcher.py`

- **行数**：267　**类**：0　**函数/方法**：8
- **职责**：GrassSea 单进程启动器
- **内部依赖**：`app.desktop`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 61 | function | `resolve_port` | `(env_key: str, default: int) → int` |
| 73 | function | `prepare_environment` | `() → dict[str, Any]` |
| 102 | function | `import_apps` | `() → list[tuple[str, Any, int]]` |
| 112 | function | `serve` | `(name: str, app: Any, port: int, servers: dict[str, Any], primary: bool, verbose: bool = False,) → None` |
| 138 | function | `run` | `(verbose: bool = False) → int` |
| 173 | function | `_request_stop` | `(*_: Any) → None` |
| 201 | function | `check` | `() → int` |
| 228 | function | `main` | `(argv: list[str] \| None = None) → int` |

### `frontend/src/App.tsx`

- **行数**：39　**类**：0　**函数/方法**：1
- **内部依赖**：`./components/ShimmerBar`、`./components/Sidebar`、`./components/TopNav`、`./pages/Chat`、`./pages/KnowledgeBase`、`./pages/Settings`、`./pages/TaskCenter`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 11 | component | `App` | `` |

### `frontend/src/api/index.ts`

- **行数**：293　**类**：0　**函数/方法**：39
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 19 | interface | `ToolCallTrace` | `` |
| 28 | interface | `ChatResponse` | `` |
| 39 | interface | `AttachmentDescriptor` | `` |
| 51 | interface | `AttachmentLimits` | `` |
| 58 | const | `chatApi` | `` |
| 71 | const | `uploadAttachmentApi` | `` |
| 90 | const | `attachmentLimitsApi` | `` |
| 94 | interface | `DesktopStatus` | `` |
| 100 | interface | `WorkspaceInfo` | `` |
| 108 | const | `desktopStatusApi` | `` |
| 110 | const | `workspaceInfoApi` | `` |
| 112 | const | `workspaceSetApi` | `` |
| 116 | const | `workspaceSelectApi` | `` |
| 120 | interface | `RagDocumentSource` | `` |
| 124 | interface | `RagDocument` | `` |
| 132 | interface | `RagDocumentListResponse` | `` |
| 137 | interface | `RagUploadResponse` | `` |
| 144 | interface | `RagDeleteResponse` | `` |
| 150 | interface | `RagSourceChunk` | `` |
| 158 | interface | `RagQueryResponse` | `` |
| 166 | const | `ragQueryApi` | `` |
| 173 | const | `listDocumentsApi` | `` |
| 178 | const | `deleteDocumentApi` | `` |
| 182 | type | `UploadProgressHandler` | `` |
| 184 | const | `uploadDocumentApi` | `` |
| 201 | type | `TaskStatus` | `` |
| 203 | interface | `TaskSummary` | `` |
| 214 | interface | `TaskListResponse` | `` |
| 219 | interface | `TaskStep` | `` |
| 228 | interface | `TaskResult` | `` |
| 238 | interface | `TaskStatusResponse` | `` |
| 247 | interface | `AgentInfo` | `` |
| 257 | interface | `AgentListResponse` | `` |
| 262 | const | `listTasksApi` | `` |
| 264 | const | `getTaskStatusApi` | `` |
| 267 | const | `listAgentsApi` | `` |
| 270 | interface | `ToolDefinition` | `` |
| 283 | interface | `ToolListResponse` | `` |
| 290 | const | `listToolsApi` | `` |

### `frontend/src/components/DAGPanel.tsx`

- **行数**：364　**类**：0　**函数/方法**：1
- **内部依赖**：`../api`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 142 | component | `DAGPanel` | `` |

### `frontend/src/components/ShimmerBar.tsx`

- **行数**：21　**类**：0　**函数/方法**：1
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 3 | component | `ShimmerBar` | `` |

### `frontend/src/components/Sidebar.tsx`

- **行数**：144　**类**：0　**函数/方法**：1
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 45 | component | `Sidebar` | `` |

### `frontend/src/components/ToolTraceCard.tsx`

- **行数**：104　**类**：0　**函数/方法**：1
- **内部依赖**：`../api`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 30 | component | `ToolTraceCard` | `` |

### `frontend/src/components/TopNav.tsx`

- **行数**：67　**类**：0　**函数/方法**：1
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 3 | component | `TopNav` | `` |

### `frontend/src/components/stepOutput.tsx`

- **行数**：121　**类**：0　**函数/方法**：5
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 9 | const | `MAX_RESULT_PAIRS` | `` |
| 27 | const | `summaryLines` | `` |
| 54 | const | `stepOutputLines` | `` |
| 99 | const | `bulletText` | `` |
| 103 | const | `LineList` | `` |

### `frontend/src/main.tsx`

- **行数**：36　**类**：0　**函数/方法**：0
- **内部依赖**：`./App`

（无类 / 函数定义）

### `frontend/src/pages/Chat.tsx`

- **行数**：539　**类**：0　**函数/方法**：2
- **内部依赖**：`../api`、`../components/DAGPanel`、`../components/ToolTraceCard`、`../components/stepOutput`、`../stores/chatStore`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 25 | component | `CapsuleTag` | `` |
| 48 | component | `ChatPage` | `` |

### `frontend/src/pages/KnowledgeBase.tsx`

- **行数**：530　**类**：0　**函数/方法**：1
- **内部依赖**：`../api`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 88 | component | `KnowledgePage` | `` |

### `frontend/src/pages/Settings.tsx`

- **行数**：176　**类**：0　**函数/方法**：1
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 21 | component | `SettingsPage` | `` |

### `frontend/src/pages/TaskCenter.tsx`

- **行数**：508　**类**：0　**函数/方法**：1
- **内部依赖**：`../api`、`../components/stepOutput`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 104 | component | `TaskCenterPage` | `` |

### `frontend/src/stores/chatStore.ts`

- **行数**：46　**类**：0　**函数/方法**：1
- **内部依赖**：`../api`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 27 | const | `useChatStore` | `` |

### `frontend/src/stores/uiStore.ts`

- **行数**：16　**类**：0　**函数/方法**：1
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 10 | const | `useUIStore` | `` |

### `frontend/vite.config.d.ts`

- **行数**：3　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `frontend/vite.config.ts`

- **行数**：19　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `scripts/backup_db.py`

- **行数**：117　**类**：0　**函数/方法**：5
- **职责**：数据库备份脚本 — 每日全量 + WAL 归档
- **内部依赖**：`shared.utils.config`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 28 | function | `backup_postgresql` | `() → str` |
| 47 | function | `backup_mongodb` | `() → str` |
| 62 | function | `cleanup_old_backups` | `() → int` |
| 75 | function | `sync_to_minio` | `(local_path: str) → bool` |
| 96 | function | `main` | `()` |

### `scripts/init_db.py`

- **行数**：73　**类**：0　**函数/方法**：3
- **职责**：数据库一键建表脚本（个人开发环境）
- **内部依赖**：`shared.models.database`、`shared.models.postgres`、`shared.models.timescale`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 38 | function | `create_schema_and_tables` | `() → None` |
| 44 | function | `convert_to_hypertables` | `() → str` |
| 62 | function | `main` | `() → None` |

### `scripts/init_minio.py`

- **行数**：90　**类**：0　**函数/方法**：2
- **职责**：MinIO bucket 初始化脚本
- **内部依赖**：`shared.utils.config`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 37 | function | `create_bucket_if_not_exists` | `(client: Minio, bucket_name: str) → None` |
| 50 | function | `main` | `() → None` |

### `scripts/reset_knowledge_base.py`

- **行数**：76　**类**：0　**函数/方法**：3
- **职责**：重建知识库索引
- **内部依赖**：`shared.utils.config`、`shared.vectorstore`、`shared.vectorstore.local`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 29 | function | `reset_local` | `(db_path: Path) → None` |
| 43 | function | `reset_milvus` | `(host: str, port: int) → None` |
| 59 | function | `main` | `() → None` |

### `scripts/seed_data.py`

- **行数**：96　**类**：0　**函数/方法**：3
- **职责**：数据库种子脚本（幂等，可重复执行）
- **内部依赖**：`shared.models.database`、`shared.models.postgres.system_config`、`shared.models.postgres.user`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 47 | function | `seed_system_configs` | `(session: AsyncSession) → tuple[int, int]` |
| 71 | function | `seed_default_user` | `(session: AsyncSession) → tuple[User, bool]` |
| 83 | function | `main` | `() → None` |

### `services/agent_service/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `services/agent_service/executor.py`

- **行数**：537　**类**：1　**函数/方法**：15
- **职责**：任务执行引擎
- **内部依赖**：`services.agent_service.registry`、`shared.models.postgres.task`、`shared.protocols.agent`、`shared.utils.config`、`shared.utils.logging`、`tools.base.registry`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 91 | function | `_format_metrics` | `(values: dict) → str` |
| 113 | class | `TaskExecutor` | `` |
| 116 | method | `TaskExecutor.__init__` | `(self, settings: Settings, registry: AgentRegistry, tool_registry: ToolRegistry \| None = None,)` |
| 130 | method | `TaskExecutor.execute_async` | `(self, task: dict, session_id: str, user_id: str \| None) → None` |
| 147 | method | `TaskExecutor._execute_dag` | `(self, task: dict) → None` |
| 168 | method | `TaskExecutor.finished_count` | `() → int` |
| 302 | method | `TaskExecutor._summarize` | `(results: dict[str, Any]) → list[str]` |
| 352 | method | `TaskExecutor._record_step` | `(step_id: str, result: Any, results: dict[str, Any], completed: set[str], failed: set[str], skipped: set[str],) → None` |
| 376 | method | `TaskExecutor._execute_step` | `(self, step: dict, task: dict) → Any` |
| 478 | method | `TaskExecutor._build_callbacks` | `(self, task: dict) → AgentCallbacks` |
| 482 | method | `TaskExecutor.on_progress` | `(progress_task_id: str, progress: float) → None` |
| 485 | method | `TaskExecutor.on_message` | `(message_task_id: str, message: str) → None` |
| 488 | method | `TaskExecutor.on_error` | `(error_task_id: str, error: str) → None` |
| 493 | method | `TaskExecutor.list_tasks` | `(self) → list[dict]` |
| 511 | method | `TaskExecutor.get_status` | `(self, task_id: str) → dict \| None` |
| 525 | method | `TaskExecutor.cancel_task` | `(self, task_id: str) → bool` |

### `services/agent_service/fsm.py`

- **行数**：143　**类**：2　**函数/方法**：7
- **职责**：会话状态机 (Session FSM)
- **内部依赖**：`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 20 | class | `SessionState` | `(str, Enum)` |
| 94 | class | `SessionFSM` | `` |
| 97 | method | `SessionFSM.__init__` | `(self, session_id: str)` |
| 112 | method | `SessionFSM.on_enter_ERROR` | `(self)` |
| 120 | method | `SessionFSM.on_enter_TIMEOUT` | `(self)` |
| 128 | method | `SessionFSM.on_enter_WAITING_USER` | `(self)` |
| 132 | method | `SessionFSM.touch` | `(self)` |
| 137 | method | `SessionFSM.idle_duration_seconds` | `(self) → float` |
| 141 | method | `SessionFSM.is_timed_out` | `(self) → bool` |

### `services/agent_service/intent.py`

- **行数**：213　**类**：3　**函数/方法**：6
- **职责**：意图识别模块
- **内部依赖**：`shared.utils.config`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 21 | class | `IntentType` | `(str, Enum)` |
| 30 | class | `IntentResult` | `` |
| 89 | class | `IntentClassifier` | `` |
| 92 | method | `IntentClassifier.__init__` | `(self, settings: Settings)` |
| 96 | method | `IntentClassifier.initialize` | `(self) → None` |
| 99 | method | `IntentClassifier.classify` | `(self, text: str) → IntentResult` |
| 119 | method | `IntentClassifier._rule_match` | `(self, text: str) → IntentResult \| None` |
| 154 | method | `IntentClassifier._extract_entities` | `(self, text: str) → dict` |
| 178 | method | `IntentClassifier._llm_classify` | `(self, text: str) → IntentResult \| None` |

### `services/agent_service/main.py`

- **行数**：461　**类**：3　**函数/方法**：15
- **职责**：智能体编排服务 (Agent Orchestration Service)
- **内部依赖**：`services.agent_service.executor`、`services.agent_service.fsm`、`services.agent_service.intent`、`services.agent_service.planner`、`services.agent_service.registry`、`services.agent_service.tool_loop`、`services.chat_service.attachments`、`shared.utils.config`、`shared.utils.logging`、`tools.base.registry`、`tools.bootstrap`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 44 | function | `lifespan` | `(app: FastAPI)` |
| 78 | class | `ChatRequest` | `(BaseModel)` |
| 87 | class | `ChatResponse` | `(BaseModel)` |
| 97 | class | `TaskStatusResponse` | `(BaseModel)` |
| 109 | function | `health` | `()` |
| 121 | function | `list_tasks` | `()` |
| 128 | function | `list_agents` | `()` |
| 135 | function | `list_tool_definitions` | `()` |
| 171 | function | `admin_status` | `()` |
| 183 | function | `reload_config` | `(config: dict[str, str])` |
| 225 | function | `_describe_plan` | `(task: dict) → str` |
| 239 | function | `_merge_notes` | `(answer: str, notes: list[str]) → str` |
| 248 | function | `chat` | `(request: ChatRequest)` |
| 366 | function | `get_task_status` | `(task_id: str)` |
| 375 | function | `websocket_endpoint` | `(websocket: WebSocket, session_id: str)` |
| 396 | function | `_handle_chitchat` | `(message: str) → str` |
| 412 | function | `_handle_with_attachments` | `(message: str) → str` |
| 446 | function | `_handle_knowledge_query` | `(message: str, session_id: str) → dict` |

### `services/agent_service/planner.py`

- **行数**：402　**类**：3　**函数/方法**：12
- **职责**：任务规划模块
- **内部依赖**：`services.agent_service.intent`、`shared.utils.config`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 21 | class | `TaskStep` | `` |
| 34 | class | `TaskDAG` | `` |
| 86 | class | `TaskPlanner` | `` |
| 89 | method | `TaskPlanner.__init__` | `(self, settings: Settings)` |
| 92 | method | `TaskPlanner.plan` | `(self, message: str, intent: IntentResult) → dict` |
| 112 | method | `TaskPlanner.plan_multi_agent` | `(self, message: str, intent: IntentResult) → dict` |
| 175 | method | `TaskPlanner._step_title` | `(self, agent_id: str, action: str) → str` |
| 180 | method | `TaskPlanner._route_agent` | `(self, message: str) → tuple[str, str]` |
| 187 | method | `TaskPlanner._rule_based_plan` | `(self, message: str, intent: IntentResult) → list[TaskStep]` |
| 245 | method | `TaskPlanner._rule_based_multi_plan` | `(self, message: str, intent: IntentResult) → dict` |
| 272 | method | `TaskPlanner._infer_tool` | `(self, message: str) → str \| None` |
| 300 | method | `TaskPlanner._is_runnable` | `(self, step: dict) → bool` |
| 307 | method | `TaskPlanner._normalize_llm_plan` | `(self, plan: dict) → dict` |
| 336 | method | `TaskPlanner.expand` | `(step_id: str, guard: set[str]) → list[str]` |
| 360 | method | `TaskPlanner._llm_plan` | `(self, message: str) → dict` |

### `services/agent_service/registry.py`

- **行数**：131　**类**：1　**函数/方法**：13
- **职责**：智能体注册中心
- **内部依赖**：`agents.cad_agent.agent`、`agents.doc_agent.agent`、`agents.naval_arch_agent.agent`、`agents.pm_agent.agent`、`agents.research_agent.agent`、`agents.review_agent.agent`、`shared.protocols.agent`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 18 | class | `AgentRegistry` | `` |
| 21 | method | `AgentRegistry.__init__` | `(self)` |
| 28 | method | `AgentRegistry.initialize` | `(self) → None` |
| 50 | method | `AgentRegistry.register` | `(self, metadata: AgentMetadata) → bool` |
| 58 | method | `AgentRegistry.register_instance` | `(self, agent: BaseAgent) → bool` |
| 64 | method | `AgentRegistry.get_agent_instance` | `(self, agent_id: str) → BaseAgent \| None` |
| 68 | method | `AgentRegistry.deregister` | `(self, agent_id: str) → bool` |
| 77 | method | `AgentRegistry.discover` | `(self, capability: str) → list[AgentMetadata]` |
| 87 | method | `AgentRegistry.heartbeat` | `(self, agent_id: str) → bool` |
| 96 | method | `AgentRegistry.get_agent` | `(self, agent_id: str) → AgentMetadata \| None` |
| 100 | method | `AgentRegistry.get_status` | `(self, agent_id: str) → AgentStatus \| None` |
| 104 | method | `AgentRegistry.set_status` | `(self, agent_id: str, status: AgentStatus) → None` |
| 108 | method | `AgentRegistry.list_agents` | `(self) → list[dict]` |
| 123 | method | `AgentRegistry.check_health` | `(self) → None` |

### `services/agent_service/tool_loop.py`

- **行数**：285　**类**：1　**函数/方法**：9
- **职责**：模型自主工具调用循环（OpenAI function calling）
- **内部依赖**：`shared.protocols.tool`、`shared.utils.config`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 68 | function | `manifest_to_openai_tool` | `(manifest: ToolManifest) → dict` |
| 84 | class | `ToolCallLoop` | `` |
| 87 | method | `ToolCallLoop.__init__` | `(self, settings: Settings, tool_registry: Any) → None` |
| 93 | method | `ToolCallLoop.list_exposed_tools` | `(self) → list[ToolManifest]` |
| 100 | method | `ToolCallLoop.openai_tools` | `(self) → list[dict]` |
| 106 | method | `ToolCallLoop.run` | `(self, message: str, session_id: str, user_id: str \| None = None,) → dict` |
| 179 | method | `ToolCallLoop._call_model` | `(self, client: httpx.AsyncClient, messages: list[dict], tools: list[dict] \| None) → dict` |
| 205 | method | `ToolCallLoop._execute_one` | `(self, call: dict, messages: list[dict], trace: list[dict], round_index: int, session_id: str, user_id: str \| None,) → None` |
| 251 | method | `ToolCallLoop._stringify` | `(result: dict) → str` |
| 259 | method | `ToolCallLoop._finalize` | `(self, client: httpx.AsyncClient, messages: list[dict], trace: list[dict], rounds: int,) → dict` |

### `services/chat_service/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `services/chat_service/attachments.py`

- **行数**：266　**类**：1　**函数/方法**：10
- **职责**：附件处理：接收上传文件 → 提取正文 → 生成描述符
- **内部依赖**：`shared.utils.config`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 47 | class | `Attachment` | `` |
| 61 | method | `Attachment.chars` | `(self) → int` |
| 64 | method | `Attachment.to_dict` | `(self) → dict` |
| 78 | function | `_uploads_dir` | `() → Path` |
| 87 | function | `_decode_text` | `(content: bytes) → str` |
| 97 | function | `_extract_pdf` | `(content: bytes) → str` |
| 125 | function | `_extract_xlsx` | `(content: bytes) → str` |
| 154 | function | `classify` | `(filename: str, media_type: str = "") → str` |
| 168 | function | `process_upload` | `(filename: str, content: bytes, media_type: str = "") → Attachment` |
| 218 | function | `build_context` | `(attachments: list[dict]) → tuple[str, list[str]]` |
| 259 | function | `image_data_url` | `(stored_path: str, media_type: str) → str \| None` |

### `services/chat_service/config_api.py`

- **行数**：303　**类**：2　**函数/方法**：8
- **职责**：系统配置管理 API — 允许用户在 Web 中修改关键配置
- **内部依赖**：`shared.utils.config`、`shared.utils.logging`、`shared.utils.secrets`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 74 | class | `ConfigItemResponse` | `(BaseModel)` |
| 85 | class | `ConfigUpdateRequest` | `(BaseModel)` |
| 90 | function | `_read_env` | `() → dict[str, str]` |
| 106 | function | `_write_env` | `(envs: dict[str, str]) → None` |
| 142 | function | `_propagate_to_services` | `(key: str, value: str) → dict[str, str]` |
| 147 | function | `_propagate_to_service_urls` | `(payload: dict[str, str]) → dict[str, str]` |
| 169 | function | `_propagate_all_secrets` | `(max_retries: int = 5, retry_delay: float = 3.0) → None` |
| 204 | function | `get_config_schema` | `()` |
| 225 | function | `update_config` | `(request: ConfigUpdateRequest, background_tasks: BackgroundTasks)` |
| 281 | function | `test_llm_connection` | `()` |

### `services/chat_service/main.py`

- **行数**：350　**类**：0　**函数/方法**：22
- **职责**：对话服务 (Chat Service) — 前端 API 网关，提供路由转发到各后端服务。
- **内部依赖**：`services.chat_service.attachments`、`services.chat_service.config_api`、`shared.utils`、`shared.utils.config`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 31 | function | `lifespan` | `(app: FastAPI)` |
| 54 | function | `_strip_api_prefix` | `(request: Request, call_next)` |
| 72 | function | `health` | `()` |
| 79 | function | `proxy_chat` | `(request: Request)` |
| 90 | function | `proxy_rag_query` | `(request: Request)` |
| 101 | function | `proxy_rag_upload` | `(request: Request)` |
| 122 | function | `proxy_rag_documents` | `(request: Request)` |
| 133 | function | `proxy_rag_delete` | `(document_id: str)` |
| 143 | function | `proxy_tasks` | `()` |
| 151 | function | `proxy_agents` | `()` |
| 163 | function | `upload_attachment` | `(file: UploadFile = File(...))` |
| 194 | function | `attachment_limits` | `()` |
| 212 | function | `_require_desktop` | `() → None` |
| 221 | function | `desktop_status` | `()` |
| 232 | function | `workspace_info` | `()` |
| 243 | function | `workspace_list` | `(path: str = "")` |
| 253 | function | `workspace_set` | `(payload: dict)` |
| 266 | function | `workspace_select` | `()` |
| 273 | function | `_pick` | `() → str` |
| 306 | function | `proxy_tools` | `()` |
| 317 | function | `proxy_task_status` | `(task_id: str)` |
| 340 | function | `spa_fallback` | `(full_path: str)` |

### `services/knowledge_service/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `services/knowledge_service/generator.py`

- **行数**：171　**类**：1　**函数/方法**：7
- **职责**：答案生成模块
- **内部依赖**：`shared.utils.config`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 35 | class | `AnswerGenerator` | `` |
| 38 | method | `AnswerGenerator.__init__` | `(self, settings: Settings)` |
| 42 | method | `AnswerGenerator._get_client` | `(self)` |
| 49 | method | `AnswerGenerator.generate` | `(self, query: str, contexts: list[str], sources: list \| None = None,) → str` |
| 87 | method | `AnswerGenerator._format_contexts` | `(self, contexts: list[str], sources: list,) → str` |
| 116 | method | `AnswerGenerator._call_llm` | `(self, messages: list[dict]) → str` |
| 150 | method | `AnswerGenerator._fallback_answer` | `(self, messages: list[dict]) → str` |
| 167 | method | `AnswerGenerator.close` | `(self) → None` |

### `services/knowledge_service/ingestion.py`

- **行数**：262　**类**：2　**函数/方法**：11
- **职责**：文档预处理流水线
- **内部依赖**：`shared.utils.config`、`shared.utils.embedding`、`shared.utils.logging`、`shared.vectorstore`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 22 | class | `DocumentChunk` | `` |
| 24 | method | `DocumentChunk.__init__` | `(self, chunk_id: str, text: str, metadata: dict, chunk_index: int,)` |
| 37 | class | `DocumentIngestionPipeline` | `` |
| 43 | method | `DocumentIngestionPipeline.__init__` | `(self, settings: Settings)` |
| 51 | method | `DocumentIngestionPipeline.initialize` | `(self) → None` |
| 63 | method | `DocumentIngestionPipeline.close` | `(self) → None` |
| 67 | method | `DocumentIngestionPipeline.process_and_index` | `(self, document_id: str, filename: str, content: bytes, content_type: str, knowledge_base: str = "项目知识库",) → int` |
| 116 | method | `DocumentIngestionPipeline._parse_document` | `(self, content: bytes, content_type: str) → str` |
| 130 | method | `DocumentIngestionPipeline._parse_pdf` | `(self, content: bytes) → str` |
| 151 | method | `DocumentIngestionPipeline._clean_text` | `(self, text: str) → str` |
| 161 | method | `DocumentIngestionPipeline._chunk_text` | `(self, text: str, chunk_size: int, chunk_overlap: int, document_id: str, filename: str, knowledge_base: str,) → list[DocumentChunk]` |
| 233 | method | `DocumentIngestionPipeline._index_chunks` | `(self, chunks: list[DocumentChunk]) → None` |
| 254 | method | `DocumentIngestionPipeline._generate_embeddings` | `(self, texts: list[str]) → list[list[float]]` |

### `services/knowledge_service/main.py`

- **行数**：332　**类**：7　**函数/方法**：9
- **职责**：知识库服务 (Knowledge Service)
- **内部依赖**：`services.knowledge_service.generator`、`services.knowledge_service.ingestion`、`services.knowledge_service.reranker`、`services.knowledge_service.retrieval`、`shared.utils.config`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 39 | function | `lifespan` | `(app: FastAPI)` |
| 72 | class | `RAGQueryRequest` | `(BaseModel)` |
| 84 | class | `SearchResult` | `(BaseModel)` |
| 99 | class | `RAGQueryResponse` | `(BaseModel)` |
| 108 | class | `DocumentUploadResponse` | `(BaseModel)` |
| 115 | class | `DocumentItem` | `(BaseModel)` |
| 124 | class | `DocumentListResponse` | `(BaseModel)` |
| 130 | class | `DeleteDocumentResponse` | `(BaseModel)` |
| 140 | function | `health_check` | `()` |
| 150 | function | `admin_status` | `()` |
| 162 | function | `reload_config` | `(config: dict[str, str])` |
| 197 | function | `rag_query` | `(request: RAGQueryRequest)` |
| 253 | function | `upload_document` | `(file: UploadFile = File(...), knowledge_base: str = Query(default="项目知识库"),)` |
| 302 | function | `list_documents` | `(knowledge_base: str \| None = Query(default=None))` |
| 311 | function | `delete_document` | `(document_id: str)` |
| 326 | function | `get_document_status` | `(document_id: str)` |

### `services/knowledge_service/reranker.py`

- **行数**：115　**类**：1　**函数/方法**：5
- **职责**：重排序模块
- **内部依赖**：`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 16 | class | `Reranker` | `` |
| 19 | method | `Reranker.__init__` | `(self, model_name: str = "BAAI/bge-reranker-v2-m3")` |
| 24 | method | `Reranker._ensure_model` | `(self) → None` |
| 41 | method | `Reranker.rerank` | `(self, query: str, candidates: list, top_k: int = 5,) → list` |
| 70 | method | `Reranker._cross_encoder_rerank` | `(self, query: str, candidates: list, top_k: int,) → list` |
| 107 | method | `Reranker._score_based_rerank` | `(self, candidates: list, top_k: int,) → list` |

### `services/knowledge_service/retrieval.py`

- **行数**：334　**类**：2　**函数/方法**：14
- **职责**：混合检索模块
- **内部依赖**：`shared.utils.config`、`shared.utils.embedding`、`shared.utils.logging`、`shared.vectorstore`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 24 | class | `SearchResult` | `` |
| 26 | method | `SearchResult.__init__` | `(self, chunk_id: str, text: str, score: float, source: dict \| None = None, chunk_index: int = 0,)` |
| 41 | class | `HybridRetriever` | `` |
| 47 | method | `HybridRetriever.__init__` | `(self, settings: Settings)` |
| 57 | method | `HybridRetriever.initialize` | `(self) → None` |
| 62 | method | `HybridRetriever.close` | `(self) → None` |
| 66 | method | `HybridRetriever.hybrid_search` | `(self, query: str, top_k: int = 20, knowledge_bases: list[str] \| None = None,) → list[SearchResult]` |
| 97 | method | `HybridRetriever._dense_search` | `(self, query: str, top_k: int, knowledge_bases: list[str] \| None,) → list[SearchResult]` |
| 126 | method | `HybridRetriever._sparse_search` | `(self, query: str, top_k: int, knowledge_bases: list[str] \| None,) → list[SearchResult]` |
| 181 | method | `HybridRetriever._generate_query_embedding` | `(self, query: str) → list[float]` |
| 189 | method | `HybridRetriever.list_documents` | `(self, knowledge_base: str \| None = None) → list[dict]` |
| 218 | method | `HybridRetriever.delete_document` | `(self, document_id: str) → int` |
| 230 | method | `HybridRetriever._ensure_sparse_index` | `(self) → None` |
| 244 | method | `HybridRetriever._rebuild_sparse_index` | `(self) → None` |
| 281 | method | `HybridRetriever._merge_results` | `(self, dense: list[SearchResult], sparse: list[SearchResult],) → list[SearchResult]` |
| 321 | method | `HybridRetriever._tokenize` | `(self, text: str) → list[str]` |

### `services/model_gateway/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `services/model_gateway/main.py`

- **行数**：362　**类**：5　**函数/方法**：8
- **职责**：模型网关服务 (Model Gateway)
- **内部依赖**：`services.model_gateway.router`、`services.model_gateway.token_tracker`、`shared.utils.config`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 33 | function | `lifespan` | `(app: FastAPI)` |
| 61 | class | `ChatMessage` | `(BaseModel)` |
| 75 | class | `ChatCompletionRequest` | `(BaseModel)` |
| 88 | class | `ChatCompletionChoice` | `(BaseModel)` |
| 94 | class | `ChatUsage` | `(BaseModel)` |
| 100 | class | `ChatCompletionResponse` | `(BaseModel)` |
| 112 | function | `health_check` | `()` |
| 122 | function | `version` | `()` |
| 132 | function | `list_models` | `()` |
| 151 | function | `reload_config` | `(config: dict[str, str])` |
| 195 | function | `chat_completions` | `(request: ChatCompletionRequest, http_request: Request)` |
| 239 | function | `_sync_response` | `(request: ChatCompletionRequest, route_result, trace_id: str, start_time: float,) → ChatCompletionResponse` |
| 301 | function | `_stream_response` | `(request: ChatCompletionRequest, route_result, trace_id: str, start_time: float,)` |

### `services/model_gateway/router.py`

- **行数**：409　**类**：3　**函数/方法**：11
- **职责**：模型路由器
- **内部依赖**：`shared.utils.config`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 21 | class | `ModelRouteRequest` | `` |
| 31 | class | `ModelRouteResult` | `` |
| 53 | class | `ModelRouter` | `` |
| 56 | method | `ModelRouter.__init__` | `(self, settings: Settings)` |
| 61 | method | `ModelRouter.initialize` | `(self) → None` |
| 105 | method | `ModelRouter.close` | `(self) → None` |
| 110 | method | `ModelRouter.route` | `(self, request: ModelRouteRequest) → ModelRouteResult` |
| 167 | method | `ModelRouter.complete` | `(self, route: ModelRouteResult, stream: bool = False, messages: list[dict] \| None = None, tools: list[dict] \| None = None, temperature: float \| None = None, max_tokens: int \| None = None,) → dict` |
| 201 | method | `ModelRouter.complete_stream` | `(self, route: ModelRouteResult, messages: list[dict] \| None = None,) → AsyncIterator[dict]` |
| 216 | method | `ModelRouter._call_deepseek` | `(self, route: ModelRouteResult, stream: bool = False, messages: list[dict] \| None = None, tools: list[dict] \| None = None, temperature: float \| None = None, max_tokens: int \| None = None,) → dict` |
| 275 | method | `ModelRouter._call_deepseek_stream` | `(self, route: ModelRouteResult, messages: list[dict] \| None = None) → AsyncIterator[dict]` |
| 306 | method | `ModelRouter._to_anthropic_messages` | `(messages: list[dict] \| None) → tuple[str, list[dict]]` |
| 330 | method | `ModelRouter._call_claude` | `(self, route: ModelRouteResult, stream: bool = False, messages: list[dict] \| None = None, temperature: float \| None = None, max_tokens: int \| None = None,) → dict` |
| 377 | method | `ModelRouter._call_claude_stream` | `(self, route: ModelRouteResult, messages: list[dict] \| None = None) → AsyncIterator[dict]` |

### `services/model_gateway/token_tracker.py`

- **行数**：81　**类**：1　**函数/方法**：4
- **职责**：Token 用量统计与计费
- **内部依赖**：`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 15 | class | `TokenTracker` | `` |
| 18 | method | `TokenTracker.__init__` | `(self)` |
| 22 | method | `TokenTracker.record` | `(self, user_id: str, session_id: str, model: str, task_type: str, prompt_tokens: int, completion_tokens: int, latency_ms: float,) → None` |
| 62 | method | `TokenTracker.flush` | `(self) → None` |
| 69 | method | `TokenTracker.get_user_usage` | `(self, user_id: str, days: int = 30) → dict` |

### `shared/__init__.py`

- **行数**：1　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `shared/middleware/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `shared/middleware/observability.py`

- **行数**：72　**类**：1　**函数/方法**：2
- **职责**：可观测性中间件 — OpenTelemetry 自动埋点 + Prometheus 指标
- **内部依赖**：`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 18 | class | `ObservabilityMiddleware` | `(BaseHTTPMiddleware)` |
| 21 | method | `ObservabilityMiddleware.dispatch` | `(self, request: Request, call_next)` |
| 44 | function | `setup_observability` | `(app: FastAPI) → None` |

### `shared/middleware/security.py`

- **行数**：114　**类**：2　**函数/方法**：7
- **职责**：安全中间件 — RBAC + API Key + 预签名 URL + 审计日志
- **内部依赖**：`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 32 | function | `check_permission` | `(role: str, required: str) → bool` |
| 40 | function | `generate_api_key` | `(user_id: str) → tuple[str, str]` |
| 48 | function | `verify_hmac_signature` | `(payload: bytes, signature: str, secret: str) → bool` |
| 56 | function | `generate_presigned_url` | `(bucket: str, object_path: str, expires_minutes: int = 15) → str` |
| 68 | class | `AuditMiddleware` | `(BaseHTTPMiddleware)` |
| 71 | method | `AuditMiddleware.dispatch` | `(self, request: Request, call_next)` |
| 88 | class | `SecurityHeadersMiddleware` | `(BaseHTTPMiddleware)` |
| 91 | method | `SecurityHeadersMiddleware.dispatch` | `(self, request: Request, call_next)` |
| 101 | function | `setup_security` | `(app: FastAPI) → None` |

### `shared/models/__init__.py`

- **行数**：1　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `shared/models/alembic/env.py`

- **行数**：80　**类**：0　**函数/方法**：4
- **职责**：Alembic 环境配置
- **内部依赖**：`shared.models.database`、`shared.models.postgres`、`shared.models.timescale`、`shared.utils.config`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 37 | function | `run_migrations_offline` | `() → None` |
| 51 | function | `do_run_migrations` | `(connection: Connection) → None` |
| 57 | function | `run_async_migrations` | `() → None` |
| 71 | function | `run_migrations_online` | `() → None` |

### `shared/models/alembic/versions/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `shared/models/database.py`

- **行数**：185　**类**：1　**函数/方法**：13
- **职责**：数据库连接管理模块（全部惰性化）
- **内部依赖**：`shared.utils.config`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 35 | class | `Base` | `(DeclarativeBase)` |
| 48 | function | `_build_pg_engine` | `() → Any` |
| 60 | function | `get_pg_engine` | `() → Any` |
| 68 | function | `get_pg_session_factory` | `() → Any` |
| 82 | function | `__getattr__` | `(name: str) → Any` |
| 95 | function | `get_pg_session` | `() → AsyncGenerator[Any, None]` |
| 113 | function | `init_mongodb` | `() → None` |
| 123 | function | `close_mongodb` | `() → None` |
| 132 | function | `get_mongo_db` | `() → "AsyncIOMotorDatabase"` |
| 145 | function | `init_redis` | `() → None` |
| 154 | function | `close_redis` | `() → None` |
| 162 | function | `get_redis` | `() → Any` |
| 173 | function | `init_milvus` | `() → None` |
| 180 | function | `close_milvus` | `() → None` |

### `shared/models/mongodb/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `shared/models/mongodb/collections.py`

- **行数**：130　**类**：1　**函数/方法**：0
- **职责**：MongoDB 集合定义与索引
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `MongoCollections` | `` |

### `shared/models/postgres/__init__.py`

- **行数**：23　**类**：0　**函数/方法**：0
- **内部依赖**：`shared.models.postgres.base`、`shared.models.postgres.offset_table`、`shared.models.postgres.project`、`shared.models.postgres.prompt_template`、`shared.models.postgres.system_config`、`shared.models.postgres.task`、`shared.models.postgres.todo`、`shared.models.postgres.user`

（无类 / 函数定义）

### `shared/models/postgres/base.py`

- **行数**：30　**类**：2　**函数/方法**：0
- **职责**：SQLAlchemy 基类与共享 mixin
- **内部依赖**：`shared.models.database`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 15 | class | `TimestampMixin` | `` |
| 25 | class | `UUIDMixin` | `` |

### `shared/models/postgres/offset_table.py`

- **行数**：42　**类**：1　**函数/方法**：1
- **职责**：型值表模型
- **内部依赖**：`shared.models.database`、`shared.models.postgres.base`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 20 | class | `OffsetTable` | `(Base, UUIDMixin, TimestampMixin)` |
| 40 | method | `OffsetTable.__repr__` | `(self) → str` |

### `shared/models/postgres/project.py`

- **行数**：55　**类**：2　**函数/方法**：1
- **职责**：项目模型
- **内部依赖**：`shared.models.database`、`shared.models.postgres.base`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 21 | class | `ProjectStatus` | `(str, enum.Enum)` |
| 37 | class | `Project` | `(Base, UUIDMixin, TimestampMixin)` |
| 53 | method | `Project.__repr__` | `(self) → str` |

### `shared/models/postgres/prompt_template.py`

- **行数**：40　**类**：1　**函数/方法**：1
- **职责**：Prompt 模板模型
- **内部依赖**：`shared.models.database`、`shared.models.postgres.base`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 17 | class | `PromptTemplate` | `(Base, UUIDMixin, TimestampMixin)` |
| 38 | method | `PromptTemplate.__repr__` | `(self) → str` |

### `shared/models/postgres/system_config.py`

- **行数**：27　**类**：1　**函数/方法**：1
- **职责**：系统配置模型
- **内部依赖**：`shared.models.database`、`shared.models.postgres.base`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 16 | class | `SystemConfig` | `(Base, UUIDMixin, TimestampMixin)` |
| 25 | method | `SystemConfig.__repr__` | `(self) → str` |

### `shared/models/postgres/task.py`

- **行数**：64　**类**：3　**函数/方法**：1
- **职责**：任务记录模型
- **内部依赖**：`shared.models.database`、`shared.models.postgres.base`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 21 | class | `TaskStatus` | `(str, enum.Enum)` |
| 30 | class | `TaskType` | `(str, enum.Enum)` |
| 38 | class | `TaskRecord` | `(Base, UUIDMixin, TimestampMixin)` |
| 62 | method | `TaskRecord.__repr__` | `(self) → str` |

### `shared/models/postgres/todo.py`

- **行数**：64　**类**：3　**函数/方法**：1
- **职责**：待办事项模型
- **内部依赖**：`shared.models.database`、`shared.models.postgres.base`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 21 | class | `TodoPriority` | `(str, enum.Enum)` |
| 28 | class | `TodoStatus` | `(str, enum.Enum)` |
| 35 | class | `TodoItem` | `(Base, UUIDMixin, TimestampMixin)` |
| 62 | method | `TodoItem.__repr__` | `(self) → str` |

### `shared/models/postgres/user.py`

- **行数**：34　**类**：1　**函数/方法**：1
- **职责**：用户模型
- **内部依赖**：`shared.models.database`、`shared.models.postgres.base`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 21 | class | `User` | `(Base, UUIDMixin, TimestampMixin)` |
| 32 | method | `User.__repr__` | `(self) → str` |

### `shared/models/repository/__init__.py`

- **行数**：14　**类**：0　**函数/方法**：0
- **内部依赖**：`shared.models.repository.base`、`shared.models.repository.conversation`、`shared.models.repository.project`、`shared.models.repository.task`

（无类 / 函数定义）

### `shared/models/repository/base.py`

- **行数**：79　**类**：1　**函数/方法**：8
- **职责**：Repository 基类
- **内部依赖**：`shared.models.database`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 19 | class | `BaseRepository` | `(Generic[ModelType])` |
| 24 | method | `BaseRepository.__init__` | `(self, session: AsyncSession)` |
| 27 | method | `BaseRepository.get_by_id` | `(self, id: UUID \| str) → Optional[ModelType]` |
| 34 | method | `BaseRepository.get_all` | `(self, skip: int = 0, limit: int = 100) → list[ModelType]` |
| 43 | method | `BaseRepository.count` | `(self, **filters: Any) → int` |
| 51 | method | `BaseRepository.create` | `(self, obj: ModelType) → ModelType` |
| 58 | method | `BaseRepository.update` | `(self, obj: ModelType, **values: Any) → ModelType` |
| 67 | method | `BaseRepository.delete` | `(self, obj: ModelType) → None` |
| 72 | method | `BaseRepository.delete_by_id` | `(self, id: UUID \| str) → bool` |

### `shared/models/repository/conversation.py`

- **行数**：109　**类**：1　**函数/方法**：9
- **职责**：Conversation Repository (MongoDB)
- **内部依赖**：`shared.models.mongodb.collections`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 13 | class | `ConversationRepository` | `` |
| 18 | method | `ConversationRepository.__init__` | `(self, db: AsyncIOMotorDatabase)` |
| 21 | method | `ConversationRepository.create_session` | `(self, session_id: str, user_id: str, initial_state: str = "IDLE") → str` |
| 38 | method | `ConversationRepository.add_message` | `(self, session_id: str, role: str, content: str, sources: list[dict] \| None = None,) → None` |
| 60 | method | `ConversationRepository.get_session` | `(self, session_id: str) → Optional[dict]` |
| 64 | method | `ConversationRepository.update_state` | `(self, session_id: str, state: str) → None` |
| 71 | method | `ConversationRepository.update_intent` | `(self, session_id: str, intent: str) → None` |
| 78 | method | `ConversationRepository.update_token_usage` | `(self, session_id: str, prompt: int, completion: int) → None` |
| 94 | method | `ConversationRepository.get_recent_sessions` | `(self, user_id: str, limit: int = 20) → list[dict]` |
| 105 | method | `ConversationRepository.delete_session` | `(self, session_id: str) → bool` |

### `shared/models/repository/project.py`

- **行数**：57　**类**：1　**函数/方法**：4
- **职责**：Project Repository
- **内部依赖**：`shared.models.postgres.project`、`shared.models.repository.base`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 15 | class | `ProjectRepository` | `(BaseRepository[Project])` |
| 19 | method | `ProjectRepository.get_by_code` | `(self, code: str) → Optional[Project]` |
| 26 | method | `ProjectRepository.get_by_owner` | `(self, owner_id: UUID, skip: int = 0, limit: int = 50) → list[Project]` |
| 38 | method | `ProjectRepository.get_active_projects` | `(self, skip: int = 0, limit: int = 50) → list[Project]` |
| 50 | method | `ProjectRepository.archive_project` | `(self, project_id: UUID) → Optional[Project]` |

### `shared/models/repository/task.py`

- **行数**：73　**类**：1　**函数/方法**：5
- **职责**：Task Repository
- **内部依赖**：`shared.models.postgres.task`、`shared.models.repository.base`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 15 | class | `TaskRepository` | `(BaseRepository[TaskRecord])` |
| 19 | method | `TaskRepository.get_by_session` | `(self, session_id: str) → list[TaskRecord]` |
| 28 | method | `TaskRepository.get_by_user` | `(self, user_id: UUID, skip: int = 0, limit: int = 50) → list[TaskRecord]` |
| 41 | method | `TaskRepository.get_by_status` | `(self, status: TaskStatus, skip: int = 0, limit: int = 50) → list[TaskRecord]` |
| 53 | method | `TaskRepository.update_status` | `(self, task_id: UUID, status: TaskStatus, error_message: str \| None = None) → None` |
| 65 | method | `TaskRepository.update_progress` | `(self, task_id: UUID, progress: float) → None` |

### `shared/models/timescale/__init__.py`

- **行数**：15　**类**：0　**函数/方法**：0
- **内部依赖**：`shared.models.timescale.metrics`

（无类 / 函数定义）

### `shared/models/timescale/metrics.py`

- **行数**：100　**类**：4　**函数/方法**：4
- **职责**：TimescaleDB 时序指标模型
- **内部依赖**：`shared.models.database`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 26 | class | `TokenUsageMetric` | `(Base)` |
| 42 | method | `TokenUsageMetric.__repr__` | `(self) → str` |
| 46 | class | `APILatencyMetric` | `(Base)` |
| 60 | method | `APILatencyMetric.__repr__` | `(self) → str` |
| 64 | class | `ToolCallMetric` | `(Base)` |
| 79 | method | `ToolCallMetric.__repr__` | `(self) → str` |
| 83 | class | `SessionMetric` | `(Base)` |
| 98 | method | `SessionMetric.__repr__` | `(self) → str` |

### `shared/protocols/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `shared/protocols/agent.py`

- **行数**：117　**类**：6　**函数/方法**：11
- **职责**：智能体基础协议定义
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `AgentStatus` | `(str, Enum)` |
| 25 | class | `AgentCapability` | `` |
| 36 | class | `AgentMetadata` | `` |
| 48 | class | `AgentCallbacks` | `` |
| 55 | class | `BaseAgent` | `(ABC)` |
| 61 | method | `BaseAgent.__init__` | `(self, metadata: AgentMetadata)` |
| 66 | method | `BaseAgent.metadata` | `(self) → AgentMetadata` |
| 71 | method | `BaseAgent.status` | `(self) → AgentStatus` |
| 76 | method | `BaseAgent.handle_task` | `(self, task: dict[str, Any], # 任务描述（标准化格式） context: dict[str, Any], # 上下文信息 callbacks: AgentCallbacks, # 回调接口) → dict[str, Any]` |
| 85 | method | `BaseAgent.health_check` | `(self) → bool` |
| 89 | method | `BaseAgent.set_status` | `(self, status: AgentStatus) → None` |
| 95 | class | `AgentRegistry` | `(Protocol)` |
| 98 | method | `AgentRegistry.register` | `(self, agent: BaseAgent) → bool` |
| 102 | method | `AgentRegistry.deregister` | `(self, agent_id: str) → bool` |
| 106 | method | `AgentRegistry.discover` | `(self, capability: str) → list[AgentMetadata]` |
| 110 | method | `AgentRegistry.heartbeat` | `(self, agent_id: str) → bool` |
| 114 | method | `AgentRegistry.get_agent` | `(self, agent_id: str) → AgentMetadata \| None` |

### `shared/protocols/tool.py`

- **行数**：115　**类**：5　**函数/方法**：12
- **职责**：工具基础协议定义
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `ToolCategory` | `(str, Enum)` |
| 24 | class | `ToolStatus` | `(str, Enum)` |
| 34 | class | `ToolManifest` | `` |
| 48 | class | `BaseTool` | `(ABC)` |
| 54 | method | `BaseTool.__init__` | `(self, manifest: ToolManifest)` |
| 59 | method | `BaseTool.manifest` | `(self) → ToolManifest` |
| 64 | method | `BaseTool.status` | `(self) → ToolStatus` |
| 69 | method | `BaseTool.execute` | `(self, params: dict[str, Any], context: dict[str, Any], # 用户会话上下文) → dict[str, Any]` |
| 77 | method | `BaseTool.validate_params` | `(self, params: dict[str, Any]) → bool` |
| 81 | method | `BaseTool.health_check` | `(self) → bool` |
| 85 | method | `BaseTool.set_status` | `(self, status: ToolStatus) → None` |
| 91 | class | `ToolRegistry` | `(Protocol)` |
| 94 | method | `ToolRegistry.register` | `(self, tool: BaseTool) → bool` |
| 98 | method | `ToolRegistry.deregister` | `(self, tool_id: str) → bool` |
| 102 | method | `ToolRegistry.get_tool` | `(self, tool_id: str) → BaseTool \| None` |
| 106 | method | `ToolRegistry.list_tools` | `(self, category: ToolCategory \| None = None) → list[ToolManifest]` |
| 112 | method | `ToolRegistry.health_check_all` | `(self) → dict[str, bool]` |

### `shared/utils/__init__.py`

- **行数**：1　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `shared/utils/config.py`

- **行数**：235　**类**：1　**函数/方法**：13
- **职责**：GrassSea AI — 统一配置管理模块
- **内部依赖**：`shared.utils.secrets`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 22 | function | `is_usable_key` | `(value: str \| None) → bool` |
| 29 | class | `Settings` | `(BaseSettings)` |
| 61 | method | `Settings.POSTGRES_URI` | `(self) → str` |
| 68 | method | `Settings.POSTGRES_SYNC_URI` | `(self) → str` |
| 82 | method | `Settings.MONGODB_URI` | `(self) → str` |
| 95 | method | `Settings.REDIS_URI` | `(self) → str` |
| 115 | method | `Settings.MILVUS_URI` | `(self) → str` |
| 127 | method | `Settings.MINIO_URI` | `(self) → str` |
| 138 | method | `Settings.RABBITMQ_URI` | `(self) → str` |
| 148 | method | `Settings.NEO4J_URI` | `(self) → str` |
| 153 | method | `Settings.CELERY_BROKER_URL` | `(self) → str` |
| 157 | method | `Settings.CELERY_RESULT_BACKEND` | `(self) → str` |
| 211 | method | `Settings.PROJECT_ROOT` | `(self) → Path` |
| 216 | function | `get_settings` | `() → Settings` |

### `shared/utils/embedding.py`

- **行数**：219　**类**：4　**函数/方法**：14
- **职责**：统一的文本向量化模块
- **内部依赖**：`shared.utils.config`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 38 | class | `BaseEmbedder` | `` |
| 44 | method | `BaseEmbedder.__init__` | `(self, dim: int) → None` |
| 47 | method | `BaseEmbedder.embed` | `(self, texts: list[str]) → list[list[float]]` |
| 50 | method | `BaseEmbedder.embed_one` | `(self, text: str) → list[float]` |
| 55 | class | `LocalEmbedder` | `(BaseEmbedder)` |
| 61 | method | `LocalEmbedder.__init__` | `(self, settings: Settings) → None` |
| 88 | method | `LocalEmbedder.embed` | `(self, texts: list[str]) → list[list[float]]` |
| 89 | method | `LocalEmbedder._run` | `() → list[list[float]]` |
| 95 | class | `OpenAIEmbedder` | `(BaseEmbedder)` |
| 101 | method | `OpenAIEmbedder.__init__` | `(self, settings: Settings) → None` |
| 110 | method | `OpenAIEmbedder.embed` | `(self, texts: list[str]) → list[list[float]]` |
| 127 | class | `HashEmbedder` | `(BaseEmbedder)` |
| 139 | method | `HashEmbedder.__init__` | `(self, dim: int) → None` |
| 143 | method | `HashEmbedder._features` | `(cls, text: str) → list[str]` |
| 151 | method | `HashEmbedder.embed` | `(self, texts: list[str]) → list[list[float]]` |
| 168 | function | `_build` | `(settings: Settings) → BaseEmbedder` |
| 199 | function | `get_embedder` | `(settings: Settings) → BaseEmbedder` |
| 215 | function | `reset_embedder` | `() → None` |

### `shared/utils/logging.py`

- **行数**：114　**类**：0　**函数/方法**：6
- **职责**：GrassSea AI — 结构化日志模块
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 21 | function | `add_trace_context` | `(logger: structlog.BoundLogger, method_name: str, event_dict: dict) → dict` |
| 34 | function | `setup_logging` | `(level: str = "INFO", json_format: bool = True,) → None` |
| 89 | function | `get_logger` | `(name: str \| None = None) → structlog.stdlib.BoundLogger` |
| 97 | function | `trace_span` | `(trace_id: str, span_id: str \| None = None)` |
| 109 | function | `set_trace_id` | `(trace_id: str) → None` |
| 113 | function | `set_span_id` | `(span_id: str) → None` |

### `shared/utils/secrets.py`

- **行数**：155　**类**：0　**函数/方法**：7
- **职责**：API Key 加密存储模块
- **内部依赖**：`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 33 | function | `_resolve_secrets_dir` | `() → Path` |
| 66 | function | `_get_or_create_key` | `() → bytes` |
| 88 | function | `_get_fernet` | `() → Fernet` |
| 93 | function | `load_secrets` | `() → dict[str, str]` |
| 115 | function | `save_secrets` | `(secrets: dict[str, str]) → None` |
| 140 | function | `update_secret` | `(key: str, value: str) → None` |
| 152 | function | `is_sensitive_key` | `(key: str) → bool` |

### `shared/utils/workspace.py`

- **行数**：258　**类**：1　**函数/方法**：11
- **职责**：工作文件夹访问（桌面模式）
- **内部依赖**：`shared.utils.config`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 43 | class | `WorkspaceError` | `(Exception)` |
| 47 | function | `is_enabled` | `() → bool` |
| 52 | function | `_require_enabled` | `() → None` |
| 57 | function | `get_root` | `() → Path \| None` |
| 71 | function | `set_root` | `(path: str) → Path` |
| 87 | function | `resolve` | `(rel_path: str = "") → Path` |
| 101 | function | `list_dir` | `(rel_path: str = "", max_entries: int = MAX_LIST_ENTRIES) → dict` |
| 144 | function | `read_file` | `(rel_path: str, max_chars: int = MAX_READ_CHARS) → dict` |
| 180 | function | `write_file` | `(rel_path: str, content: str, overwrite: bool = False) → dict` |
| 209 | function | `tree` | `(rel_path: str = "", max_depth: int = 2, max_entries: int = 200) → dict` |
| 218 | method | `WorkspaceError.walk` | `(directory: Path, depth: int) → None` |
| 250 | function | `summary_lines` | `() → list[str]` |

### `shared/vectorstore/__init__.py`

- **行数**：40　**类**：0　**函数/方法**：1
- **职责**：向量存储抽象层 —— 按配置选择后端
- **内部依赖**：`shared.utils.config`、`shared.vectorstore.base`、`shared.vectorstore.local`、`shared.vectorstore.milvus`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 22 | function | `get_vector_store` | `(settings: Settings) → VectorStore` |

### `shared/vectorstore/base.py`

- **行数**：99　**类**：2　**函数/方法**：9
- **职责**：向量存储协议与数据结构
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 19 | class | `VectorRecord` | `` |
| 34 | class | `VectorStore` | `(ABC)` |
| 47 | method | `VectorStore.__init__` | `(self, settings, collection_name: str = "grasssea_knowledge") → None` |
| 53 | method | `VectorStore.available` | `(self) → bool` |
| 60 | method | `VectorStore.initialize` | `(self) → None` |
| 64 | method | `VectorStore.close` | `(self) → None` |
| 70 | method | `VectorStore.upsert` | `(self, records: list[VectorRecord], embeddings: list[list[float]]) → int` |
| 80 | method | `VectorStore.search` | `(self, embedding: list[float], top_k: int, knowledge_bases: list[str] \| None = None,) → list[VectorRecord]` |
| 89 | method | `VectorStore.fetch_all` | `(self, limit: int = 16384) → list[VectorRecord]` |
| 93 | method | `VectorStore.delete_document` | `(self, document_id: str) → int` |
| 97 | method | `VectorStore.count` | `(self) → int` |

### `shared/vectorstore/local.py`

- **行数**：268　**类**：1　**函数/方法**：13
- **职责**：内置向量存储 —— SQLite 持久化 + numpy 精确余弦检索
- **内部依赖**：`shared.utils.logging`、`shared.vectorstore.base`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 41 | class | `LocalVectorStore` | `(VectorStore)` |
| 46 | method | `LocalVectorStore.__init__` | `(self, settings, collection_name: str = "grasssea_knowledge") → None` |
| 59 | method | `LocalVectorStore.resolve_db_path` | `(settings) → Path` |
| 68 | method | `LocalVectorStore._resolve_db_path` | `(self) → Path` |
| 73 | method | `LocalVectorStore._connect` | `(self) → sqlite3.Connection` |
| 81 | method | `LocalVectorStore.initialize` | `(self) → None` |
| 96 | method | `LocalVectorStore.close` | `(self) → None` |
| 104 | method | `LocalVectorStore._invalidate_cache` | `(self) → None` |
| 109 | method | `LocalVectorStore._load_matrix` | `(self) → None` |
| 144 | method | `LocalVectorStore.upsert` | `(self, records: list[VectorRecord], embeddings: list[list[float]]) → int` |
| 185 | method | `LocalVectorStore.search` | `(self, embedding: list[float], top_k: int, knowledge_bases: list[str] \| None = None,) → list[VectorRecord]` |
| 227 | method | `LocalVectorStore.fetch_all` | `(self, limit: int = 16384) → list[VectorRecord]` |
| 244 | method | `LocalVectorStore.delete_document` | `(self, document_id: str) → int` |
| 258 | method | `LocalVectorStore.count` | `(self) → int` |

### `shared/vectorstore/milvus.py`

- **行数**：240　**类**：1　**函数/方法**：10
- **职责**：Milvus 向量存储后端
- **内部依赖**：`shared.utils.logging`、`shared.vectorstore.base`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 19 | class | `MilvusVectorStore` | `(VectorStore)` |
| 24 | method | `MilvusVectorStore.__init__` | `(self, settings, collection_name: str = "grasssea_knowledge") → None` |
| 31 | method | `MilvusVectorStore.initialize` | `(self) → None` |
| 59 | method | `MilvusVectorStore.close` | `(self) → None` |
| 70 | method | `MilvusVectorStore._read_dim` | `(collection) → int \| None` |
| 79 | method | `MilvusVectorStore._ensure_collection` | `(self)` |
| 99 | method | `MilvusVectorStore.upsert` | `(self, records: list[VectorRecord], embeddings: list[list[float]]) → int` |
| 157 | method | `MilvusVectorStore.search` | `(self, embedding: list[float], top_k: int, knowledge_bases: list[str] \| None = None,) → list[VectorRecord]` |
| 199 | method | `MilvusVectorStore.fetch_all` | `(self, limit: int = 16384) → list[VectorRecord]` |
| 224 | method | `MilvusVectorStore.delete_document` | `(self, document_id: str) → int` |
| 232 | method | `MilvusVectorStore.count` | `(self) → int` |

### `tests/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `tests/e2e/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `tests/integration/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `tests/unit/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `tests/unit/test_config.py`

- **行数**：59　**类**：1　**函数/方法**：5
- **职责**：配置模块单元测试
- **内部依赖**：`shared.utils.config`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 10 | class | `TestSettings` | `` |
| 13 | method | `TestSettings.test_default_settings` | `(self) → None` |
| 20 | method | `TestSettings.test_postgres_uri_property` | `(self) → None` |
| 34 | method | `TestSettings.test_mongodb_uri_property` | `(self) → None` |
| 48 | method | `TestSettings.test_redis_uri_no_password` | `(self) → None` |
| 54 | method | `TestSettings.test_get_settings_singleton` | `(self) → None` |

### `tests/unit/test_logging.py`

- **行数**：45　**类**：1　**函数/方法**：5
- **职责**：日志模块单元测试
- **内部依赖**：`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 10 | class | `TestLogging` | `` |
| 13 | method | `TestLogging.test_setup_logging_json` | `(self) → None` |
| 19 | method | `TestLogging.test_setup_logging_console` | `(self) → None` |
| 25 | method | `TestLogging.test_get_logger` | `(self) → None` |
| 32 | method | `TestLogging.test_trace_context` | `(self) → None` |
| 39 | method | `TestLogging.test_set_trace_id` | `(self) → None` |

### `tests/unit/test_model_gateway.py`

- **行数**：88　**类**：2　**函数/方法**：8
- **职责**：模型网关单元测试
- **内部依赖**：`services.model_gateway.router`、`shared.utils.config`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 11 | class | `TestModelRouter` | `` |
| 15 | method | `TestModelRouter.settings` | `(self)` |
| 22 | method | `TestModelRouter.router` | `(self, settings)` |
| 29 | method | `TestModelRouter.test_route_simple_chat` | `(self, router)` |
| 40 | method | `TestModelRouter.test_route_complex_reasoning` | `(self, router)` |
| 50 | method | `TestModelRouter.test_route_unknown_model_fallback` | `(self, router)` |
| 60 | method | `TestModelRouter.test_task_model_map_completeness` | `(self)` |
| 69 | class | `TestModelRouteRequest` | `` |
| 72 | method | `TestModelRouteRequest.test_default_values` | `(self)` |
| 79 | method | `TestModelRouteRequest.test_custom_values` | `(self)` |

### `tests/unit/test_rag.py`

- **行数**：183　**类**：5　**函数/方法**：18
- **职责**：RAG 引擎单元测试
- **内部依赖**：`services.knowledge_service.generator`、`services.knowledge_service.ingestion`、`services.knowledge_service.reranker`、`services.knowledge_service.retrieval`、`shared.utils.config`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `TestDocumentIngestion` | `` |
| 18 | method | `TestDocumentIngestion.settings` | `(self)` |
| 22 | method | `TestDocumentIngestion.pipeline` | `(self, settings)` |
| 25 | method | `TestDocumentIngestion.test_clean_text` | `(self, pipeline)` |
| 34 | method | `TestDocumentIngestion.test_chunk_text` | `(self, pipeline)` |
| 52 | method | `TestDocumentIngestion.test_chunk_text_empty` | `(self, pipeline)` |
| 60 | method | `TestDocumentIngestion.test_chunk_text_single_paragraph` | `(self, pipeline)` |
| 71 | class | `TestReranker` | `` |
| 75 | method | `TestReranker.reranker` | `(self)` |
| 78 | method | `TestReranker.test_score_based_rerank` | `(self, reranker)` |
| 91 | method | `TestReranker.test_rerank_with_few_candidates` | `(self, reranker)` |
| 98 | class | `TestHybridRetriever` | `` |
| 101 | method | `TestHybridRetriever.test_tokenize` | `(self)` |
| 111 | method | `TestHybridRetriever.test_tokenize_english` | `(self)` |
| 120 | class | `TestAnswerGenerator` | `` |
| 124 | method | `TestAnswerGenerator.settings` | `(self)` |
| 128 | method | `TestAnswerGenerator.generator` | `(self, settings)` |
| 131 | method | `TestAnswerGenerator.test_format_contexts` | `(self, generator)` |
| 147 | method | `TestAnswerGenerator.test_fallback_answer` | `(self, generator)` |
| 156 | method | `TestAnswerGenerator.test_format_contexts_without_sources` | `(self, generator)` |
| 165 | class | `TestPromptTemplate` | `` |
| 168 | method | `TestPromptTemplate.test_rag_system_prompt` | `(self)` |
| 174 | method | `TestPromptTemplate.test_rag_user_prompt_template` | `(self)` |

### `tools/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `tools/base/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `tools/base/registry.py`

- **行数**：115　**类**：1　**函数/方法**：8
- **职责**：工具注册中心 — 支持热插拔机制
- **内部依赖**：`shared.protocols.tool`、`shared.utils.logging`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 16 | class | `ToolRegistry` | `` |
| 19 | method | `ToolRegistry.__init__` | `(self)` |
| 23 | method | `ToolRegistry.register` | `(self, tool: BaseTool) → bool` |
| 44 | method | `ToolRegistry.deregister` | `(self, tool_id: str) → bool` |
| 53 | method | `ToolRegistry.get_tool` | `(self, tool_id: str) → BaseTool \| None` |
| 57 | method | `ToolRegistry.list_tools` | `(self, category: ToolCategory \| None = None) → list[ToolManifest]` |
| 64 | method | `ToolRegistry.execute_tool` | `(self, tool_id: str, params: dict, context: dict) → dict` |
| 87 | method | `ToolRegistry.health_check_all` | `(self) → dict[str, bool]` |
| 105 | method | `ToolRegistry._validate_tool` | `(self, tool: BaseTool) → bool` |

### `tools/bootstrap.py`

- **行数**：82　**类**：0　**函数/方法**：1
- **职责**：工具引导模块 — 统一实例化并注册 tools/ 下的全部工具
- **内部依赖**：`shared.protocols.tool`、`shared.utils.logging`、`tools.base.registry`、`tools.cad.cad_draw`、`tools.cad.cad_parse`、`tools.cad.dwg_converter`、`tools.compliance.reg_check`、`tools.computation.hull_transform`、`tools.computation.hydrostatics`、`tools.computation.resistance`、`tools.computation.stability`、`tools.file.ocr_engine`、`tools.file.pdf_parser`、`tools.file.todo_manager`、`tools.file.web_search`、`tools.file.workspace`、`tools.file.xlsx_parser`、`tools.report.report_gen`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 57 | function | `build_tool_registry` | `() → ToolRegistry` |

### `tools/cad/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `tools/cad/cad_draw.py`

- **行数**：23　**类**：1　**函数/方法**：2
- **职责**：CAD 图纸生成工具 — 型线图绘制、曲线光顺
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `CadDrawTool` | `(BaseTool)` |
| 15 | method | `CadDrawTool.__init__` | `(self)` |
| 17 | method | `CadDrawTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/cad/cad_parse.py`

- **行数**：23　**类**：1　**函数/方法**：2
- **职责**：CAD 图纸解析工具 — 从 DWG/DXF 提取尺寸、标注、图层
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `CadParseTool` | `(BaseTool)` |
| 15 | method | `CadParseTool.__init__` | `(self)` |
| 17 | method | `CadParseTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/cad/dwg_converter.py`

- **行数**：23　**类**：1　**函数/方法**：2
- **职责**：DWG 格式转换工具 — DWG ↔ DXF ↔ PDF ↔ PNG
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `DwgConverterTool` | `(BaseTool)` |
| 15 | method | `DwgConverterTool.__init__` | `(self)` |
| 17 | method | `DwgConverterTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/compliance/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `tools/compliance/reg_check.py`

- **行数**：23　**类**：1　**函数/方法**：2
- **职责**：规范合规审查工具 — 基于规范条文自动审查设计参数
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `RegCheckTool` | `(BaseTool)` |
| 15 | method | `RegCheckTool.__init__` | `(self)` |
| 17 | method | `RegCheckTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/computation/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `tools/computation/hull_transform.py`

- **行数**：78　**类**：1　**函数/方法**：2
- **职责**：船型改造工具 — 母型船变换、参数优化
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 20 | class | `HullTransformTool` | `(BaseTool)` |
| 23 | method | `HullTransformTool.__init__` | `(self) → None` |
| 26 | method | `HullTransformTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/computation/hydrostatics.py`

- **行数**：59　**类**：1　**函数/方法**：2
- **职责**：静水力计算工具
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 19 | class | `HydrostaticsTool` | `(BaseTool)` |
| 22 | method | `HydrostaticsTool.__init__` | `(self) → None` |
| 25 | method | `HydrostaticsTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/computation/resistance.py`

- **行数**：58　**类**：1　**函数/方法**：2
- **职责**：阻力计算工具 — Holtrop 法、ITTC 法
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 21 | class | `ResistanceTool` | `(BaseTool)` |
| 24 | method | `ResistanceTool.__init__` | `(self) → None` |
| 27 | method | `ResistanceTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/computation/stability.py`

- **行数**：65　**类**：1　**函数/方法**：2
- **职责**：稳性分析工具 — 完整稳性、破舱稳性
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 21 | class | `StabilityTool` | `(BaseTool)` |
| 24 | method | `StabilityTool.__init__` | `(self) → None` |
| 27 | method | `StabilityTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/file/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `tools/file/ocr_engine.py`

- **行数**：23　**类**：1　**函数/方法**：2
- **职责**：图纸 OCR 工具 — 扫描图纸文字/标注识别
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `OcrEngineTool` | `(BaseTool)` |
| 15 | method | `OcrEngineTool.__init__` | `(self)` |
| 17 | method | `OcrEngineTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/file/pdf_parser.py`

- **行数**：23　**类**：1　**函数/方法**：2
- **职责**：PDF 解析工具 — 规范文件文本/表格提取
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `PdfParserTool` | `(BaseTool)` |
| 15 | method | `PdfParserTool.__init__` | `(self)` |
| 17 | method | `PdfParserTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/file/todo_manager.py`

- **行数**：23　**类**：1　**函数/方法**：2
- **职责**：待办管理工具 — 创建/更新/提醒待办事项
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `TodoManagerTool` | `(BaseTool)` |
| 15 | method | `TodoManagerTool.__init__` | `(self)` |
| 17 | method | `TodoManagerTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/file/web_search.py`

- **行数**：23　**类**：1　**函数/方法**：2
- **职责**：联网搜索工具 — 补充最新信息
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `WebSearchTool` | `(BaseTool)` |
| 15 | method | `WebSearchTool.__init__` | `(self)` |
| 17 | method | `WebSearchTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/file/workspace.py`

- **行数**：196　**类**：4　**函数/方法**：9
- **职责**：工作文件夹工具 — 让模型按需读写用户选定文件夹中的文件
- **内部依赖**：`shared.protocols.tool`、`shared.utils`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 111 | class | `_WorkspaceToolBase` | `(BaseTool)` |
| 114 | method | `_WorkspaceToolBase.execute` | `(self, params: dict, context: dict) → dict` |
| 117 | method | `_WorkspaceToolBase._guard` | `(self) → dict \| None` |
| 131 | method | `_WorkspaceToolBase._fail` | `(exc: Exception) → dict` |
| 135 | class | `WorkspaceListTool` | `(_WorkspaceToolBase)` |
| 138 | method | `WorkspaceListTool.__init__` | `(self) → None` |
| 141 | method | `WorkspaceListTool.execute` | `(self, params: dict, context: dict) → dict` |
| 153 | class | `WorkspaceReadTool` | `(_WorkspaceToolBase)` |
| 156 | method | `WorkspaceReadTool.__init__` | `(self) → None` |
| 159 | method | `WorkspaceReadTool.execute` | `(self, params: dict, context: dict) → dict` |
| 174 | class | `WorkspaceWriteTool` | `(_WorkspaceToolBase)` |
| 177 | method | `WorkspaceWriteTool.__init__` | `(self) → None` |
| 180 | method | `WorkspaceWriteTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/file/xlsx_parser.py`

- **行数**：23　**类**：1　**函数/方法**：2
- **职责**：表格解析工具 — 型值表结构化提取
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `XlsxParserTool` | `(BaseTool)` |
| 15 | method | `XlsxParserTool.__init__` | `(self)` |
| 17 | method | `XlsxParserTool.execute` | `(self, params: dict, context: dict) → dict` |

### `tools/report/__init__.py`

- **行数**：2　**类**：0　**函数/方法**：0
- **内部依赖**：（无）

（无类 / 函数定义）

### `tools/report/report_gen.py`

- **行数**：23　**类**：1　**函数/方法**：2
- **职责**：报告生成工具 — Markdown → PDF（规范排版）
- **内部依赖**：`shared.protocols.tool`

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 14 | class | `ReportGenTool` | `(BaseTool)` |
| 15 | method | `ReportGenTool.__init__` | `(self)` |
| 17 | method | `ReportGenTool.execute` | `(self, params: dict, context: dict) → dict` |

### `练习/00-01-练习1.py`

- **行数**：19　**类**：0　**函数/方法**：2
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 6 | function | `fetch_user_info` | `(user_id: str) → str` |
| 14 | function | `main` | `()` |

### `练习/00-01-练习3.py`

- **行数**：31　**类**：0　**函数/方法**：2
- **职责**：练习3：改造同步代码
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 7 | function | `get_all_data` | `()` |
| 19 | function | `get_all_data` | `()` |

### `练习/test_async.py`

- **行数**：55　**类**：0　**函数/方法**：5
- **内部依赖**：（无）

| 行号 | 类型 | 符号 | 签名 |
|---:|---|---|---|
| 4 | function | `greet` | `(name: str) → str` |
| 11 | function | `main` | `()` |
| 23 | function | `main` | `()` |
| 36 | function | `fetch_url` | `(url: str) → str` |
| 43 | function | `main` | `()` |
