# GrassSea AI — 部署指南

> 本文是**精简部署指引**。详细的桌面版用法见 [DESKTOP_GUIDE](../DESKTOP_GUIDE.md)，
> Docker 的完整概念讲解见 [DOCKER_GUIDE](../DOCKER_GUIDE.md)，
> 架构与模块边界见 [ARCHITECTURE](../ARCHITECTURE.md)。

## 1. 先选形态

| | 🖥️ 桌面形态（个人本机） | 🐳 服务器形态 |
|---|---|---|
| 适用 | 自己在 Windows 上用 | 部署到服务器 / 多用户 / 大规模 |
| 前置 | 仅 Python + uv | Docker 24+（**不需要 K8s**） |
| 命令 | `uv run python -m app.launcher --desktop` | `docker compose -f docker-compose.yml -f docker-compose.app.yml up -d` |
| 中间件 | **零** | PostgreSQL · MongoDB · Redis · RabbitMQ · Milvus · MinIO |
| 向量后端 | `VECTOR_BACKEND=local` | `VECTOR_BACKEND=milvus` |
| 数据 | `<项目根>/data/` | `./docker-data/` |

> ⚠️ **K3s / Kubernetes 部署已移除**（`infrastructure/k3s/` 已删除）。本项目的编排形态只有
> 「单进程桌面」与「单机 Docker Compose」两种。

## 2. 环境要求

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | 3.11+（推荐 3.12） | 桌面形态与服务运行环境 |
| uv | 0.11+ | 依赖管理 |
| Node.js | 18+ | 仅前端构建需要 |
| Docker Desktop | 24+ | 仅服务器形态需要 |

## 3. 桌面形态部署（推荐个人使用）

```bash
uv sync --extra dev
uv run python -m app.launcher --check      # 先自检
uv run python -m app.launcher --desktop    # 启动
```

首次使用知识库会自动下载本地向量模型（约 95MB）。数据全部落在 `data/`（已 gitignore）。

## 4. 服务器形态部署

```bash
cp .env.example .env          # 按需修改端口与口令
docker compose up -d postgres mongodb redis rabbitmq minio
docker compose up -d milvus-etcd milvus-minio milvus        # 需要知识库时
docker compose -f docker-compose.yml -f docker-compose.app.yml up -d --build
```

初始化与验证：

```bash
uv run python scripts/init_db.py
uv run python scripts/seed_data.py
curl http://localhost:8001/health
```

## 5. 关键环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `APP_ENV` | development | 环境标识 |
| `DEEPSEEK_API_KEY` | 空 | LLM 密钥（也可在设置页加密保存） |
| `VECTOR_BACKEND` | local | `local`（内置）/ `milvus`（Docker 中默认） |
| `DESKTOP_MODE` | false | 由 `--desktop` 自动置 true |
| `WORKSPACE_ROOT` | 空 | 预置工作文件夹 |
| `TOOL_CALLING_ENABLED` | true | 模型自主调用工具总开关 |
| `TOOL_CALL_MAX_ROUNDS` | 6 | 工具调用最大轮次 |
| `POSTGRES_*` / `MONGODB_*` / `REDIS_*` / `RABBITMQ_*` / `MILVUS_*` / `MINIO_*` | 见 `.env.example` | **仅服务器形态需要** |

## 6. 常见问题

| 症状 | 处理 |
|---|---|
| 桌面版打不开窗口 | 见 [DESKTOP_GUIDE](../DESKTOP_GUIDE.md) 第 5 节（窗口方式分级策略） |
| `uv sync` 超时 | 设 `UV_DEFAULT_INDEX` 为国内镜像 |
| 桌面版知识库为空 | 向量后端是 `local`，需重新上传文档；原有 Milvus 数据不会自动迁移 |
| 换 embedding 模型后报维度错误 | `uv run python scripts/reset_knowledge_base.py` 后重新入库 |
