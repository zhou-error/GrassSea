# 附录A - 项目文件对照表

> 教学章节与项目源文件的完整对应关系。遇到不理解的代码时，对照此表找到源文件阅读。

## 阶段一：项目初始化

| 教学章节 | 项目文件 |
|----------|----------|
| 01-项目结构设计 | 项目根目录整体结构 |
| 02-pyproject.toml配置 | `pyproject.toml` |
| 03-Docker开发环境 | `docker-compose.yml`, `.env.example` |

## 阶段四：RAG知识库引擎

| 教学章节 | 项目文件 |
|----------|----------|
| 01-RAG概念与架构 | `services/knowledge_service/main.py` |
| 02-文档预处理 | `services/knowledge_service/ingestion.py` |
| 03-向量化与混合检索 | `services/knowledge_service/retrieval.py` |
| 04-重排序与生成 | `services/knowledge_service/reranker.py`, `services/knowledge_service/generator.py` |

## 阶段七：工具库系统

| 教学章节 | 项目文件 |
|----------|----------|
| 01-工具协议与注册中心 | `shared/protocols/tool.py`, `tools/base/registry.py` |
| 02-计算类工具 | `tools/computation/hydrostatics.py`, `tools/computation/stability.py`, `tools/computation/resistance.py` |
| 03-CAD类工具 | `tools/cad/cad_draw.py`, `tools/cad/cad_parse.py`, `tools/cad/dwg_converter.py` |
| 04-合规审查工具 | `tools/compliance/reg_check.py` |
| 05-文件处理工具 | `tools/file/pdf_parser.py`, `tools/file/xlsx_parser.py`, `tools/file/ocr_engine.py`, `tools/file/todo_manager.py`, `tools/file/web_search.py` |
| 06-报告生成工具 | `tools/report/report_gen.py` |

## 阶段十：安全与认证

| 教学章节 | 项目文件 |
|----------|----------|
| 01-JWT认证机制 | `shared/middleware/security.py` (ROLE_PERMISSIONS, check_permission) |
| 02-RBAC权限控制 | `shared/middleware/security.py`（K3s / Casbin 清单已移除，不在本项目范围） |
| 03-API-Key签名认证 | `shared/middleware/security.py` (generate_api_key, verify_hmac_signature), `shared/utils/secrets.py` |
| 04-安全中间件与审计 | `shared/middleware/security.py` (AuditMiddleware, SecurityHeadersMiddleware, setup_security) |

## 阶段十一：可观测性

| 教学章节 | 项目文件 |
|----------|----------|
| 01-OpenTelemetry埋点 | `shared/middleware/observability.py`, `shared/utils/logging.py` |
| 02-Prometheus指标采集 | 不在本项目范围（配置保留为可选 profile） |
| 03-Grafana看板搭建 | 不在本项目范围（配置保留为可选 profile） |

## 阶段十二：测试与部署

| 教学章节 | 项目文件 |
|----------|----------|
| 01-pytest单元测试 | `tests/unit/test_config.py`, `tests/unit/test_logging.py`, `tests/unit/test_model_gateway.py`, `tests/unit/test_rag.py` |
| 02-集成测试 | `tests/integration/` |
| 03-Docker镜像构建 | `infrastructure/docker/Dockerfile`, `infrastructure/docker/Dockerfile.frontend` |
| 04-CICD流水线 | 不在本项目范围（流水线已移除） |
| 05-K3s生产部署（已移除） | `infrastructure/k3s/namespace.yaml`, `infrastructure/k3s/configmap.yaml`, `infrastructure/k3s/secret.yaml`, `infrastructure/k3s/ingress.yaml`, `infrastructure/k3s/persistent-volumes.yaml` |

## 项目完整文件索引

### 核心共享模块 (`shared/`)

| 文件 | 职责 |
|------|------|
| `shared/utils/config.py` | 全局配置管理（基于 pydantic-settings） |
| `shared/utils/logging.py` | 结构化日志（基于 structlog） |
| `shared/utils/secrets.py` | API Key 加密存储（Fernet + AES） |
| `shared/middleware/security.py` | 安全中间件（RBAC, HMAC签名, CORS, 审计） |
| `shared/middleware/observability.py` | 可观测性中间件（Trace ID, OpenTelemetry） |
| `shared/models/database.py` | 数据库连接管理 |
| `shared/models/postgres/` | PostgreSQL 数据模型 |
| `shared/models/mongodb/` | MongoDB 数据模型 |
| `shared/models/timescale/` | TimescaleDB 指标模型 |
| `shared/models/repository/` | 数据访问层 (Repository 模式) |
| `shared/protocols/agent.py` | 智能体协议定义 |
| `shared/protocols/tool.py` | 工具协议定义 (BaseTool, ToolManifest) |

### 微服务 (`services/`)

| 文件 | 职责 |
|------|------|
| `services/model_gateway/` | 模型网关 — 多模型路由与调用 |
| `services/chat_service/` | 对话服务 — 会话管理 |
| `services/agent_service/` | 智能体服务 — 多 Agent 编排 |
| `services/knowledge_service/` | 知识库服务 — RAG 检索增强生成 |

### 智能体 (`agents/`)

| 文件 | 职责 |
|------|------|
| `agents/pm_agent/` | 项目经理智能体 |
| `agents/review_agent/` | 规范审查智能体 |
| `agents/naval_arch_agent/` | 船舶设计智能体 |
| `agents/cad_agent/` | CAD 绘图智能体 |
| `agents/research_agent/` | 资料检索智能体 |
| `agents/doc_agent/` | 文档撰写智能体 |

### 工具库 (`tools/`)

| 文件 | 职责 |
|------|------|
| `tools/base/registry.py` | 工具注册中心 |
| `tools/computation/` | 数值计算工具（静水力、稳性、阻力） |
| `tools/cad/` | CAD 操作工具 |
| `tools/compliance/` | 合规审查工具 |
| `tools/report/` | 报告生成工具 |
| `tools/file/` | 文件处理工具（PDF, Excel, OCR, Web搜索） |

### 基础设施 (`infrastructure/`)

| 文件 | 职责 |
|------|------|
| `infrastructure/docker/Dockerfile` | Python 微服务通用镜像 |
| `infrastructure/docker/Dockerfile.frontend` | 前端多阶段构建镜像 |
| `infrastructure/docker/nginx/grasssea.conf` | Nginx 反向代理配置 |
| `infrastructure/docker/postgres/init/` | PostgreSQL 初始化脚本 |
| `infrastructure/docker/prometheus/prometheus.yml` | Prometheus 采集配置 |
| `infrastructure/docker/grafana/` | Grafana 看板和数据源配置 |
| ~~`infrastructure/k3s/`~~ | 已移除（不在本项目范围） |

### CI/CD 和配置

| 文件 | 职责 |
|------|------|
| ~~`.github/workflows/ci.yml`~~ | 已移除（不在本项目范围） |
| `pyproject.toml` | Python 项目配置（依赖、工具链） |
| `docker-compose.yml` | 本地开发环境（中间件服务） |
| `docker-compose.app.yml` | 应用服务编排 |
| ~~`docker-compose.full.yml`~~ | 已删除（与上面两个文件功能重叠） |
| `.env.example` | 环境变量模板 |

### 测试 (`tests/`)

| 文件 | 职责 |
|------|------|
| `tests/unit/test_config.py` | 配置模块单元测试 |
| `tests/unit/test_logging.py` | 日志模块单元测试 |
| `tests/unit/test_model_gateway.py` | 模型网关单元测试 |
| `tests/unit/test_rag.py` | RAG 引擎单元测试 |
| `tests/integration/` | 集成测试目录 |
| `tests/e2e/` | 端到端测试目录 |
