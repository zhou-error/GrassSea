# 🌊 白草沧智 GrassSea AI

> 面向船舶与海洋工程的 AI 原生多智能体协作平台 —— 以草木之真知，破船海之万难。

把「专业计算 + 规范知识库 + 多智能体编排 + 文档交付」串成一条链路：用自然语言描述设计任务，平台负责分解、计算、检索、成文。

---

## 现状一览

| 模块 | 状态 |
|---|---|
| 4 个 FastAPI 微服务（对话 / 编排 / 知识库 / 模型网关） | ✅ 可用 |
| **7 个业务 Agent**（项目经理 · 审查 · 船舶工程师 · CAD · **Rhino 建模** · 研究 · 文档） | ✅ 全部注册 |
| **21 个工具**，其中 **13 个对模型可见**（5 计算 + 3 工作文件夹 + 4 文档 + **1 Rhino 桥接**） | ✅ 注册并实测 |
| **模型自主调用工具**（function calling） | ✅ 模型自选工具，失败自动回落规则规划 |
| **RAG 知识库**（混合检索 + 重排 + 带引用生成） | ✅ 端到端实测；向量后端可切换 |
| **入库格式**：PDF / TXT / MD / **XLSX** / **DOCX** | ✅ 实测（扫描版 PDF 暂不支持 OCR） |
| **Word 文档**（新建 / 修改 / 全排版 / 转 PDF） | ✅ 实测，含排版模板 |
| **配置可视化编辑**（30 项 / 8 分类，中英双语） | ✅ 设置页可改，类型安全 |
| **启动自检**（密钥可解密 / 目录可写 / 端口可用） | ✅ 失败即中止并给出恢复指引（`--force` 可跳过） |
| **日志落盘** | ✅ `data/logs/app.log`（10MB × 5 滚动） |
| **一键备份 / 恢复** | ✅ `data/` + 密钥 + `.env`；恢复前自动备份当前状态 |
| **诊断包导出** | ✅ 日志 + 脱敏配置 + 环境信息（不含明文密钥） |
| **启动一致性校验** | ✅ planner 引用的 agent/tool 必须存在，不一致即告警 |
| 前端 4 页面（项目 / 知识库 / 智能体 / 设置） | ✅ 可用 |
| 登录 / RBAC / 多租户 | ❌ 未实现（个人使用定位，暂不需要） |
| **DWG/DXF 解析**、OCR、Grasshopper | ❌ 诚实返回「未实现」，不产出伪造结果（见 [BACKLOG](docs/BACKLOG.md)） |

> **诚实失败是本项目的硬约定**：能力未实现时返回明确原因，绝不编造文件路径、规范条款号或文献条目。

---

## 两种运行形态

同一套代码，靠配置切换。

|  | 🖥️ 桌面形态（个人本机） | 🐳 服务器形态 |
|---|---|---|
| 前置 | Python + uv | Docker 24+ |
| 外部中间件 | **零** | PostgreSQL · MongoDB · Redis · RabbitMQ · Milvus · MinIO |
| 向量后端 | `local`（内置 SQLite + numpy） | `milvus` |
| 数据 | `<项目根>/data/` | `./docker-data/` |
| 窗口 | 无边框桌面窗口 | nginx 托管 |

### 桌面形态（推荐）

```bash
uv sync --extra dev
uv run python -m app.launcher --desktop
```

Windows 下也可直接双击 `启动.bat`。

### 服务器形态

```bash
cp .env.example .env
docker compose up -d postgres mongodb redis rabbitmq minio
docker compose up -d milvus-etcd milvus-minio milvus
docker compose -f docker-compose.yml -f docker-compose.app.yml up -d --build
uv run python scripts/init_db.py && uv run python scripts/seed_data.py
```

---

## 核心能力

### 多智能体编排
自然语言 → 意图识别 → 任务规划（规则或 LLM）→ DAG 调度 → 结果中文摘要。
步骤未实现时**跳过而非失败**，并把真实原因告诉用户。

### 模型自主调用工具
工具清单以 OpenAI function-calling 格式交给模型，模型自行决定调用哪个、传什么参数，结果回灌后继续推理。轮次与超时都有上限；不可用时自动回落到规则规划。

### 专业计算（真实公式，非模拟）
静水力、稳性、阻力、型线变换——工具与 Agent 共用同一套公式，结果含单位与判据。

### 知识库 RAG
文档入库（PDF / 文本）→ 分块 → 向量化 → **稠密 + BM25 混合检索（0.7 / 0.3）** → 重排 → 带引用生成。
向量后端可插拔：`local` 零依赖，`milvus` 面向大规模。

### Word 文档与 PDF
- **新建**：封面 + 自动目录 + 页眉页脚页码 + 表格（合并单元格 / 表头跨页重复）+ 图片 + 公式 + 分节横向页
- **修改**：末尾追加 / 占位符替换 / 按标题重写 / 保留文本重排
- **转 PDF**：默认调用本机 Word，无 Office 可装 LibreOffice
- **排版模板**：YAML 可编辑，前端直接改，下次生成即生效

---

### Rhino 三维建模（船体为主）

通过本地桥接驱动**已打开**的 Rhino 8，共 12 个操作：

| 类别 | 操作 |
|---|---|
| 通用 | `create_curve` · `extrude` · `boolean` · `delete` · `query` |
| 船体 | `loft_sections`（断面点表直连放样）· `loft` · `mirror` · `split` · `join` · `offset_srf` · `mass_properties` |

- **线程安全**：所有文档操作经 `InvokeOnUiThread` 回到 Rhino 主线程，跨线程操作会硬崩
- **安全**：令牌鉴权 + 仅监听 127.0.0.1 + 操作白名单 + `boolean/delete` 需 `confirm=true`
- **可回滚**：每次请求一个 undo 记录；失败只删除**本次**创建的对象，绝不动之前的几何
- **诚实**：Rhino 未开或脚本未运行时返回 `bridge_unreachable`，不伪造 object_id

详见 [rhino/README.md](rhino/README.md) 与 [开发规划](docs/RHINO_BRIDGE_PLAN.md)。

## 架构与端口

```
chat_service :8001  ← 前端入口（BFF + 配置 API + 附件 + 静态托管）
      ↓
agent_service :8002 ← 意图 / 规划 / DAG 执行 / Agent 与工具注册 / 工具调用循环
      ↓                    ↘
knowledge_service :8003   model_gateway :8004
（RAG 检索与生成）          （多模型路由，OpenAI 兼容）
```

| 服务 | 端口 | 职责 |
|---|---|---|
| chat_service | 8001 | 前端 API 网关、配置热更新、附件解析 |
| agent_service | 8002 | 编排核心 |
| knowledge_service | 8003 | 文档入库与检索 |
| model_gateway | 8004 | 模型路由与统一接口 |

详见 **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**（含依赖图、调用链、接口契约、风险清单）。

---

## 目录结构

```
agents/            6 个业务智能体
app/               桌面形态入口（launcher 单进程启动器 / desktop 窗口）
services/          4 个 FastAPI 服务
tools/             21 个工具（computation / doc / file / cad / compliance / report）
shared/            共享内核（utils / protocols / models / vectorstore / middleware）
templates/         排版模板（可编辑）
frontend/          React 18 SPA
scripts/           初始化与运维脚本
docs/              项目文档
教学文件/          13 阶段教程（非代码资产）
```

---

## 配置

| 来源 | 说明 |
|---|---|
| `.env` | 端口、中间件地址、开关 |
| 加密密钥库 | `DEEPSEEK_API_KEY` 等敏感项，Fernet 加密存于 `docker-data/secrets/` |
| **设置页** | 30 项可编辑配置（8 分类），中英双语标签，改完即时生效 |

常用开关：`VECTOR_BACKEND`、`TOOL_CALLING_ENABLED`、`PDF_CONVERTER`、`DESKTOP_MODE`。
完整清单见 `.env.example` 与设置页。

---

## 文档索引

| 文档 | 内容 |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构、依赖、调用链、接口契约、风险与改进优先级 |
| [docs/ARCHITECTURE-APPENDIX-INDEX.md](docs/ARCHITECTURE-APPENDIX-INDEX.md) | 全文件与符号索引（脚本生成） |
| [docs/DESKTOP_GUIDE.md](docs/DESKTOP_GUIDE.md) | 桌面版使用、数据目录、已知限制 |
| [docs/TOOL_DEVELOPMENT_GUIDE.md](docs/TOOL_DEVELOPMENT_GUIDE.md) | 如何新增一个工具 |
| [docs/WORD_DOC_GUIDE.md](docs/WORD_DOC_GUIDE.md) | Word 文档能力与模板 |
| [docs/DOCKER_GUIDE.md](docs/DOCKER_GUIDE.md) | 服务器形态部署 |
| [docs/BACKLOG.md](docs/BACKLOG.md) | **待办清单**：已明确但暂缓的事项及理由 |
| [docs/RHINO_BRIDGE_PLAN.md](docs/RHINO_BRIDGE_PLAN.md) | Rhino 桥接的开发规划与协议设计 |
| [rhino/README.md](rhino/README.md) | Rhino 桥接安装、操作速查、故障排查、验收清单 |
| [docs/AUDIT-2026-10-17.md](docs/AUDIT-2026-10-17.md) | **鲁棒性审计报告**：S0-S3 缺陷、检查矩阵、未覆盖项 |
| [教学文件/](教学文件/) | 13 阶段从零构建教程 |

---

## 开发

```bash
# 后端（单进程 + 热重载）
uv run python -m app.launcher --no-window

# 前端（Vite HMR）
cd frontend && npm install && npm run dev

# 自检 / 测试 / 静态检查
uv run python -m app.launcher --check
uv run pytest
uv run ruff check .

# 数据备份与恢复
uv run python scripts/backup.py            # 备份到 data/backups/
uv run python scripts/backup.py --list     # 查看已有备份
uv run python scripts/restore.py --list    # 恢复（会先自动备份当前状态）
```

> 启动时会自动跑一次自检（密钥 / 数据目录 / 端口）。失败会中止启动并打印恢复指引；
> 确认要强行启动可加 `--force`。日志固定在 `data/logs/app.log`。

> 桌面形态下前端改动需 `npm run build` 才会被 `frontend/dist` 托管。

---

## 项目定位

**个人使用**。因此有意不做：登录鉴权、多租户、水平扩展、CI/CD、集群部署。
需要这些能力时建议重新评估架构，而不是在本项目上叠加。

---

## 许可证

MIT
