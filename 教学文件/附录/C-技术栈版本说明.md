# 附录C - 技术栈版本说明

> GrassSea 项目所用全部技术的版本、用途和兼容性说明。

## Python 生态

| 技术 | 版本 | 用途 | 说明 |
|------|------|------|------|
| Python | 3.11+ | 编程语言 | 最低要求 3.11，支持 async/await、ContextVar 等特性 |
| FastAPI | >=0.110.0 | Web 框架 | 异步高性能 API 框架，自动生成 OpenAPI 文档 |
| Uvicorn | >=0.27.0 | ASGI 服务器 | 运行 FastAPI 应用的 HTTP 服务器 |
| Pydantic | >=2.6.0 | 数据校验 | 类型安全的数据验证和序列化 |
| pydantic-settings | >=2.1.0 | 配置管理 | 从环境变量/.env 加载配置 |
| SQLAlchemy | >=2.0.25 | ORM | 异步 PostgreSQL 数据库操作 |
| asyncpg | >=0.29.0 | PostgreSQL 驱动 | 高性能异步 PostgreSQL 客户端 |
| Alembic | >=1.13.0 | 数据库迁移 | 管理数据库 schema 版本 |
| Motor | >=3.3.0 | MongoDB 驱动 | 异步 MongoDB 客户端 |
| Redis | >=5.0.0 | 缓存/队列 | Redis Python 客户端 |
| Celery | >=5.3.0 | 任务队列 | 异步任务处理 |
| httpx | >=0.27.0 | HTTP 客户端 | 异步 HTTP 请求 |

## AI / LLM

| 技术 | 版本 | 用途 | 说明 |
|------|------|------|------|
| OpenAI | >=1.12.0 | LLM API | 兼容 OpenAI SDK 的 API 调用 |
| tiktoken | >=0.5.0 | Token 计数 | OpenAI 的 tokenizer |
| LangChain | >=0.1.0 | AI 框架 | 提供 RAG、Chain 等抽象 |
| langchain-community | >=0.0.20 | 社区集成 | 各种第三方工具集成 |
| BAAI/bge-large-zh-v1.5 | - | 本地 Embedding | 中文文本向量化模型 |
| text-embedding-3-large | - | 云端 Embedding | OpenAI Embedding 模型，维度 3072 |

## 向量检索与数据处理

| 技术 | 版本 | 用途 | 说明 |
|------|------|------|------|
| PyMilvus | >=2.4.0 | 向量数据库 | 连接 Milvus 2.4 的 Python SDK |
| NumPy | >=1.26.0 | 数值计算 | 数组计算基础库 |
| Pandas | >=2.2.0 | 数据分析 | 表格数据处理 |
| PyPDF2 | >=3.0.0 | PDF 读取 | PDF 文本提取 |
| PyMuPDF | >=1.23.0 | PDF 处理 | 增强版 PDF 操作（比 PyPDF2 功能更强） |
| Unstructured | >=0.12.0 | 文档解析 | 多格式文档预处理（PDF/Word/HTML） |
| openpyxl | >=3.1.0 | Excel 处理 | xlsx 文件读写 |

## 中间件 / 基础设施

| 技术 | 版本 | 用途 |
|------|------|------|
| PostgreSQL | 15 | 关系型数据库 |
| TimescaleDB | 2.14.2 | 时序数据库扩展（审计日志） |
| MongoDB | 7.0 | 文档数据库（会话、对话记录） |
| Redis | 7.2 | 缓存和消息队列 |
| Milvus | 2.4.0 | 向量数据库 |
| MinIO | latest (2024) | 对象存储（文件/S3） |
| RabbitMQ | 3.12 | 消息队列 |
| Neo4j | 5.15.0 | 图数据库（知识图谱） |

## 可观测性

| 技术 | 版本 | 用途 | 说明 |
|------|------|------|------|
| OpenTelemetry API | >=1.22.0 | 分布式追踪 | Trace/Span 的 Python API |
| OpenTelemetry SDK | >=1.22.0 | 追踪实现 | 自动埋点和数据导出 |
| OTel FastAPI Instrumentation | >=0.43b0 | FastAPI 自动埋点 | 自动为 FastAPI 端点创建 Span |
| Prometheus（不在本项目范围） | 2.49.0 | 指标采集 | 时序数据库 + 采集引擎 |
| Grafana（不在本项目范围） | 10.3.1 | 可视化看板 | 数据可视化和告警 |
| Jaeger（不在本项目范围） | 1.53 | 链路追踪后端 | 分布式追踪查询和可视化 |
| structlog | >=24.0.0 | 结构化日志 | JSON 格式日志输出 |

## 部署 / CI/CD

| 技术 | 版本 | 用途 | 说明 |
|------|------|------|------|
| Docker | - | 容器引擎 | 镜像构建和运行 |
| Docker Compose | v2 | 本地编排 | 多容器本地环境管理 |
| K3s（不在本项目范围） | - | Kubernetes 发行版 | 轻量级 K8s 生产部署 |
| GitHub Actions（不在本项目范围） | - | CI/CD | 自动化测试、构建、部署 |
| Harbor | - | 镜像仓库 | 私有 Docker Registry |
| Nginx | alpine | 反向代理/静态服务 | 前端部署和 API 路由 |

## 前端

| 技术 | 版本 | 用途 | 说明 |
|------|------|------|------|
| React | 18+ | UI 框架 | 前端界面 |
| TypeScript | 5+ | 类型系统 | JavaScript 超集 |
| Vite | 5+ | 构建工具 | 快速的开发服务器和打包 |
| Node.js | 20 | JS 运行时 | 前端开发和构建环境 |
| Nginx | alpine | Web 服务器 | 生产环境静态文件服务 |

## 开发工具

| 技术 | 版本 | 用途 | 说明 |
|------|------|------|------|
| pytest | >=8.0.0 | 测试框架 | Python 单元测试 |
| pytest-asyncio | >=0.23.0 | 异步测试 | 支持 async/await 测试 |
| pytest-cov | >=4.1.0 | 覆盖率 | 测试代码覆盖率 |
| Ruff | >=0.2.0 | 代码检查 | 快速 Python linter + formatter |
| MyPy | >=1.8.0 | 类型检查 | 静态类型分析 |
| Bandit | >=1.7.0 | 安全扫描 | Python 代码安全检查 |
| pre-commit | >=3.6.0 | Git hooks | 提交前自动检查 |

## 其他依赖

| 技术 | 版本 | 用途 | 说明 |
|------|------|------|------|
| python-multipart | >=0.0.6 | 文件上传 | FastAPI 文件上传支持 |
| websockets | >=12.0 | WebSocket | 实时通信 |
| aio-pika | >=9.3.0 | RabbitMQ 客户端 | 异步 AMQP |
| boto3 | >=1.34.0 | AWS SDK | S3 兼容存储（MinIO） |
| python-dotenv | >=1.0.0 | 环境变量 | 从 .env 文件加载配置 |
| tenacity | >=8.2.0 | 重试机制 | 网络调用失败自动重试 |
| transitions | >=0.9.0 | 状态机 | 有限状态机（工作流引擎） |
| cryptography | - | 加密库 | Fernet 对称加密（API Key 存储） |

## Python 版本兼容性

| Python 版本 | 支持状态 | 说明 |
|-------------|----------|------|
| 3.11 | 主要支持 | 推荐使用 |
| 3.12 | 兼容 | 新语法特性可用但非必需 |
| 3.10 | 不推荐 | 缺少 ContextVar 的完善支持 |

## Docker 镜像版本对应

| 镜像 | 标签 | 对应版本 |
|------|------|----------|
| python | 3.11-slim-bookworm | Python 3.11 + Debian 12 |
| node | 20-alpine | Node.js 20 + Alpine Linux |
| nginx | alpine | 最新 Alpine Nginx |
| timescale/timescaledb | 2.14.2-pg15 | TimescaleDB 2.14.2 + PostgreSQL 15 |
| mongo | 7.0 | MongoDB 7.0 |
| redis | 7.2-alpine | Redis 7.2 + Alpine |
| milvusdb/milvus | v2.4.0 | Milvus 2.4.0 |
| rabbitmq | 3.12-management-alpine | RabbitMQ 3.12 + 管理插件 |
| neo4j | 5.15.0-community | Neo4j 5.15 社区版 |
| grafana/grafana（不在范围） | 10.3.1 | Grafana 10.3.1 |
| prom/prometheus（不在范围） | v2.49.0 | Prometheus 2.49.0 |
| jaegertracing/all-in-one（不在范围） | 1.53 | Jaeger 1.53 |
