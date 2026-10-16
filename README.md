# 🌊 白草沧智（GrassSea AI）

> **以草木之真知，破船海之万难**

面向**船舶与海洋工程**领域的 AI 原生多智能体协作平台：大语言模型（LLM）+ 专业知识库（RAG）+ 多智能体编排 + 专业工具链。

> **项目定位：个人使用。** 集群部署、CI/CD、可观测性等运维能力不属于本项目范围，已移除或保留为不启动的可选配置。

---

## 📌 当前状态

| 能力 | 状态 |
|------|------|
| 4 个后端服务启动 + /health | ✅ 已实测可用 |
| 配置 / 日志 / 密钥加密存储 | ✅ 可用（密钥存放于 docker-data/secrets） |
| 模型网关（OpenAI 兼容 + 流式） | ✅ 可用（需配置 API Key） |
| 数据模型（8 张 PG 表 + 4 张时序超表 + 6 个 Mongo 集合） | ✅ **已实测建表成功** |
| 意图识别 / 任务规划 DAG / 会话状态机 | ✅ 可用 |
| 6 个业务 Agent | ✅ 全部注册并实例化 |
| 14 个工具 | ✅ 全部注册；4 个计算工具为真实实现，其余 10 个诚实返回未实现状态 |
| 任务执行引擎 | ✅ 真实派发到 Agent / 工具，支持取消 |
| RAG 检索链路（向量化 → Milvus → 混合检索 → 带引用生成） | ✅ **已端到端实测可用**（本地向量，无需 API Key） |
| 前端 4 页面 | ⚠️ 需 npm install；无登录、无实时推送通道 |
| 登录 / RBAC | ❌ 未实现（个人使用暂不需要） |
| Celery 异步队列 / Neo4j 知识图谱 | ❌ 未实现（仅保留依赖与容器配置） |

---

## 🚀 快速开始

### 环境要求

| 软件 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+（推荐 3.12） | 后端服务 |
| uv | 0.11+ | 依赖管理（.venv 由 uv 创建，不含 pip） |
| Node.js | 18+ | 前端构建 |
| Docker Desktop | 24+ | 中间件容器（仅中间件，不需要 K8s） |

### 1. 启动中间件

```bash
docker compose up -d postgres mongodb redis rabbitmq minio
# 需要 RAG 时追加: milvus-etcd milvus-minio milvus
```

> 或使用 `make up`（等价于上面 8 个服务）。

### 2. 安装后端依赖并建表

```bash
uv sync                            # 或 uv pip install -e ".[dev]"
cp -n .env.example .env            # 首次：复制配置模板
uv run python scripts/init_db.py     # 建表 + 创建 timeseries schema + 超表（幂等）
uv run python scripts/init_minio.py  # 初始化对象存储桶
uv run python scripts/seed_data.py   # 写入系统配置 + 默认用户 admin（幂等）
```

### 3. 启动后端（4 个终端）

```bash
uv run python -m uvicorn services.model_gateway.main:app     --host 0.0.0.0 --port 8004 --reload
uv run python -m uvicorn services.knowledge_service.main:app --host 0.0.0.0 --port 8003 --reload
uv run python -m uvicorn services.agent_service.main:app     --host 0.0.0.0 --port 8002 --reload
uv run python -m uvicorn services.chat_service.main:app      --host 0.0.0.0 --port 8001 --reload
```

> ⚠️ 必须使用项目虚拟环境（`uv run python ...` 或先激活 `.venv`）。系统里的全局 `python` 是 3.14，与本项目依赖不一致。
>
> 建议启动顺序：模型网关 → 知识库 → 智能体 → 对话服务。
> 对话服务启动时会向其余服务推送加密密钥，下游未就绪时会重试约 5 次（最长约 45 秒）。

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

> 种子脚本会写入 7 项系统配置，并创建一个默认本地用户 **`admin`**。
> `projects` / `task_records` 等表的 `user_id` 为 NOT NULL，业务数据的 `owner_id` 用该用户即可。

### 5. 验证

```bash
curl http://localhost:8001/health   # 对话服务
curl http://localhost:8002/health   # 智能体编排（返回已注册 Agent 数量）
curl http://localhost:8003/health   # 知识库
curl http://localhost:8004/health   # 模型网关
```

---

## 🔌 服务与端口

| 服务 | 端口 | 健康检查 | 职责 |
|------|------|----------|------|
| 前端 (Vite) | 3000 | — | React SPA，/api 反代到 8001 |
| 对话服务 chat_service | **8001** | /health | BFF 代理 + 配置管理 API |
| 智能体编排 agent_service | 8002 | /health | 意图识别、任务规划、DAG 执行、WebSocket |
| 知识库 knowledge_service | 8003 | /health | 文档入库、混合检索、重排、答案生成 |
| 模型网关 model_gateway | 8004 | /health | OpenAI 兼容接口、多模型路由、Token 统计 |

> ⚠️ 旧文档曾把对话服务写作 **8011**，以本表 **8001** 为准（代码、.env.example、vite.config.ts、compose 均为 8001）。

---

## 📁 目录结构

```
grasssea/
├── agents/                     # 业务智能体（6 个）
│   ├── pm_agent/               #   项目经理（已注册）
│   ├── review_agent/           #   审查（已注册）
│   ├── naval_arch_agent/       #   船舶工程师
│   ├── cad_agent/              #   CAD
│   ├── research_agent/         #   研究员
│   └── doc_agent/              #   文档
├── services/                   # 后端微服务（下划线包名）
│   ├── chat_service/           #   对话 + 配置 API
│   ├── agent_service/          #   编排：intent / planner / fsm / executor / registry
│   ├── knowledge_service/      #   RAG：ingestion / retrieval / reranker / generator
│   └── model_gateway/          #   模型网关：router / token_tracker
├── tools/                      # 工具库（注册中心 + 13 个工具）
├── shared/                     # 共享库
│   ├── models/                 #   数据模型（postgres / timescale / mongodb / repository）
│   ├── protocols/              #   Agent / Tool 抽象协议
│   ├── middleware/             #   安全 / 可观测性中间件
│   └── utils/                  #   配置 / 日志 / 密钥
├── frontend/                   # React 18 + TypeScript + Ant Design
├── infrastructure/docker/      # Dockerfile 与中间件初始化脚本
├── scripts/                    # init_db / init_minio / seed_data / backup_db
├── tests/                      # unit / integration / e2e
├── docker-compose.yml          # 中间件编排（仅中间件，无运维组件）
├── alembic.ini                 # 迁移配置（连接串取自 .env）
├── pyproject.toml              # Python 配置
├── Makefile                    # 常用命令
└── docker-data/                # 中间件数据与加密密钥（git 忽略）
```

---

## 🔐 配置与密钥

配置分两类：

1. **普通配置** → 写入 .env（由 shared/utils/config.py 读取）。
2. **敏感密钥**（LLM / 搜索 API Key）→ 使用 Fernet 加密后存入 docker-data/secrets/.grasssea_secrets，
   密钥文件为 docker-data/secrets/.grasssea_key，**明文永不落盘、永不写入 .env、永不被提交**。

密钥目录解析顺序：SECRETS_DIR 环境变量 → docker-data/secrets（存在时）→ 项目根目录。
所有服务加载配置时会自动解密并注入这些 Key（.env 中的占位符会被真实密钥覆盖）。

### 向量化（RAG）

由 `EMBEDDING_PROVIDER` 选择后端，默认 `auto` 依次尝试：

| 后端 | 说明 |
|------|------|
| `local` | fastembed + BAAI/bge-small-zh-v1.5（512 维，约 95MB）——**离线可用、无需 API Key，默认首选** |
| `openai` | 任何 OpenAI 兼容的 /embeddings 接口（占位符 Key 会被忽略） |
| `hash` | 字面量哈希向量，仅作兜底，**无语义能力**，日志会告警 |

模型缓存在 `docker-data/fastembed`（可用 `LOCAL_EMBEDDING_CACHE` 覆盖）；
国内下载模型走 `HF_ENDPOINT=https://hf-mirror.com` 并禁用 Xet 协议。

> ⚠️ **更换 embedding 模型后必须重建 Milvus 集合**，否则维度不匹配会报错：
>
> ```bash
> uv run python scripts/reset_knowledge_base.py
> ```
>
> 然后重新上传文档。集合 schema 升级（如新增 document_id 字段）后也需要执行一次。

在线修改配置：PUT /config/update（对话服务）；GET /config/schema 查看可配置项。

> ⚠️ 配置管理 API 与服务端点当前**没有鉴权**。个人使用请只监听本机，不要暴露到公网。


### 知识库接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /rag/documents?knowledge_base=项目知识库 | 上传并索引文档（multipart，字段名 file） |
| GET | /rag/documents | 列出已索引文档（可按 knowledge_base 过滤） |
| DELETE | /rag/documents/{document_id} | 删除文档及其全部 chunk |
| POST | /rag/query | 检索问答；knowledge_bases 留空表示检索全部知识库 |

---

## 🗄️ 数据库

| 数据库 | 用途 |
|--------|------|
| PostgreSQL 15 + TimescaleDB | users、projects、project_members、task_records、todo_items、offset_tables、prompt_templates、system_configs |
| TimescaleDB 超表（timeseries schema） | token_usage_metrics、api_latency_metrics、tool_call_metrics、session_metrics |
| MongoDB 7 | conversation_history、review_reports、agent_configs、task_dags、research_reports、llm_call_logs |
| Milvus 2.4 | 知识库向量检索 |
| MinIO | 图纸 / PDF / 报告等文件 |
| Redis 7 | 会话缓存、限流 |
| RabbitMQ | 消息队列（Celery 尚未接入） |

建表与迁移：

```bash
uv run python scripts/init_db.py                       # 快速建表（含 timeseries schema 与超表转换）
alembic upgrade head                                   # 版本化迁移
alembic revision --autogenerate -m "initial schema"     # 生成基线迁移
```

---

## 🧪 测试与代码质量

```bash
pytest tests/ -v          # 单元 + 集成
ruff check .              # 静态检查
mypy shared/ services/ agents/ tools/
```

---

## 📚 配套教学文件

`教学文件/` 内含 12 个阶段的从零构建教程与附录。
其中**集群部署、CI/CD、可观测性**等章节属于通用知识，**不在本项目范围内**，相关章节已在开头标注。

---

## 📄 许可证

MIT License

---

*白草沧智（GrassSea AI）项目组*
