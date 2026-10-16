# GrassSea AI — Docker 部署与开发指南

> 本文档假设你对 Docker 一无所知，从零开始解释每一个概念和操作。

---

## 目录

1. [Docker 是什么？](#1-docker-是什么)
2. [你的项目在 Docker 中长什么样](#2-你的项目在-docker-中长什么样)
3. [第一步：安装 Docker Desktop](#3-第一步安装-docker-desktop)
4. [第二步：配置 API Key](#4-第二步配置-api-key)
5. [第三步：启动项目](#5-第三步启动项目)
6. [日常操作命令](#6-日常操作命令)
7. [如何边部署边开发](#7-如何边部署边开发)
8. [文件结构速查](#8-文件结构速查)
9. [端口速查表](#9-端口速查表)
10. [常见问题排查](#10-常见问题排查)

---

## 1. Docker 是什么？

### 打个比方

想象你要开一家餐厅：

| 传统做法 | Docker 做法 |
|---------|------------|
| 买服务器、装系统、装数据库、装依赖... 每台机器都要重复一遍 | 把所有东西打包成**标准化集装箱**，到哪都能直接运行 |
| "在我电脑上能跑啊" | 集装箱在哪跑都一样 |
| 装 PostgreSQL 要半小时 | `docker-compose up -d`，1 分钟搞定 |

**Docker 就像一个集装箱系统**：
- **镜像 (Image)** = 集装箱的设计图纸（只读模板）
- **容器 (Container)** = 根据图纸造出来的、正在运行的集装箱实例
- **docker-compose** = 调度中心，告诉 Docker "请按照这张清单，启动这些集装箱"

### 对你意味着什么

你不需要在 Windows 上手动安装 PostgreSQL、MongoDB、Redis、Milvus... 这些复杂软件。Docker 帮你一键启动所有东西，而且**互不干扰、随时可删、数据持久保存到 F 盘**。

---

## 2. 你的项目在 Docker 中长什么样

```
┌──────────────────────────────────────────────────────────┐
│                     Docker 网络 (grasssea-net)              │
│                                                          │
│  ┌────────────────────┐  ┌────────────────────┐          │
│  │  前端 (Nginx)       │  │  中间件层            │          │
│  │  端口 80            │  │  ┌───────────────┐  │          │
│  │  React SPA          │  │  │ PostgreSQL    │  │          │
│  │  ↓ 反向代理          │  │  │ :5432         │  │          │
│  └──┬─────┬─────┬─────┘  │  ├───────────────┤  │          │
│     │     │     │        │  │ MongoDB :27017│  │          │
│     ▼     ▼     ▼        │  ├───────────────┤  │          │
│  ┌──────────────┐        │  │ Redis :6379   │  │          │
│  │ 应用服务层     │        │  ├───────────────┤  │          │
│  │              │        │  │ Milvus :19530 │  │          │
│  │ model-gateway│        │  ├───────────────┤  │          │
│  │   :8004      │        │  │ MinIO :9000   │  │          │
│  │ chat-service │        │  ├───────────────┤  │          │
│  │   :8001      │        │  │ RabbitMQ:5672 │  │          │
│  │ agent-service│        │  ├───────────────┤  │          │
│  │   :8002      │        │  │ Neo4j :7687   │  │          │
│  │ knowledge-svc│        │  │  (可选)        │  │          │
│  │   :8003      │        │  └───────────────┘  │          │
│  └──────────────┘        └────────────────────┘          │
│                                                          │
│  所有数据 → F:/GrassSea/docker-data/ (不占C盘!)           │
└──────────────────────────────────────────────────────────┘
```

**关键理解**：每个方块是一个独立容器，它们通过网络名字互相通信（比如代码里写 `POSTGRES_HOST=postgres`，Docker 自动把 `postgres` 翻译成对应容器的 IP）。

---

## 3. 第一步：安装 Docker Desktop

### 3.1 下载安装

1. 打开 https://www.docker.com/products/docker-desktop/
2. 下载 **Docker Desktop for Windows**
3. 双击安装，全部默认选项即可
4. 安装完成后**重启电脑**

### 3.2 ⚠️ 重要：把 Docker 数据迁移到 F 盘

Docker Desktop 默认把所有镜像、容器数据放在 C 盘，很快就会吃掉几十 GB。必须迁移到 F 盘：

1. 打开 **Docker Desktop**
2. 点击右上角 **齿轮图标 (Settings)**
3. 左侧选择 **Resources** → **Advanced**
4. 找到 **Disk image location**，点击 **Browse**
5. 选择 `F:\Docker\` （需先在 F 盘创建此文件夹）
6. 点击 **Apply & Restart**

```
设置前: C:\Users\你的用户名\AppData\Local\Docker\  ← 吃C盘
设置后: F:\Docker\                                  ← 全在F盘
```

### 3.3 验证安装

打开 **PowerShell** 或 **CMD**，输入：

```bash
docker --version
# 应该输出类似: Docker version 27.x.x

docker-compose --version
# 应该输出类似: Docker Compose version v2.x.x
```

---

## 4. 第二步：配置 API Key

项目需要连接 AI 大模型（DeepSeek / Claude / OpenAI）。编辑 `.env` 文件（项目根目录），填写你的 API Key：

```bash
# 用记事本打开 F:\GrassSea\.env

# 至少填一个 Key：
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx     # 你的 DeepSeek Key
# CLAUDE_API_KEY=sk-ant-xxxxxxxxxxxxx    # 可选
# OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx     # 可选
```

**安全提醒**：`.env` 文件不会被 Docker 打包进镜像，不会被 Git 上传（已在 `.gitignore` 中），放心。

---

## 5. 第三步：启动项目

### 方案 A：一键全栈启动（推荐新手）

在项目根目录下打开终端，只需一条命令：

```bash
cd F:\GrassSea
docker-compose -f docker-compose.yml -f docker-compose.app.yml up -d
```

它会自动完成：
1. 拉取所有镜像（PostgreSQL、MongoDB、Redis...）
2. 构建你的应用镜像（Python 服务 + 前端）
3. 启动所有服务
4. 数据自动存到 `F:\GrassSea\docker-data\`

**首次启动需要下载镜像，大约 5-15 分钟（取决于网速）。请耐心等待。**

### 方案 B：分步启动（适合开发）

```bash
# 第1步：只启动中间件（数据库、缓存等）
docker-compose up -d

# 第2步：应用代码在本机开发运行（改代码秒生效）
cd services/model_gateway  && uvicorn main:app --reload --port 8004
cd services/chat_service   && uvicorn main:app --reload --port 8001
cd services/agent_service  && uvicorn main:app --reload --port 8002
cd services/knowledge_service && uvicorn main:app --reload --port 8003
cd frontend && npm run dev    # 前端 :3000
```

### 启动后验证

打开浏览器访问：

| 地址 | 内容 |
|------|------|
| http://localhost | 前端界面 |
| http://localhost:8004/docs | 模型网关 API 文档 |
| http://localhost:8001/docs | 对话服务 API 文档 |
| http://localhost:8002/docs | 智能体服务 API 文档 |
| http://localhost:8003/docs | 知识库服务 API 文档 |
| http://localhost:15672 | RabbitMQ 管理界面 |
| http://localhost:9001 | MinIO 对象存储界面 |

---

## 6. 日常操作命令

> 以下命令都在 `F:\GrassSea` 目录下执行

### 查看状态

```bash
# 查看所有运行中的服务
docker-compose -f docker-compose.yml -f docker-compose.app.yml ps

# 查看某个服务的实时日志（Ctrl+C 退出）
docker-compose -f docker-compose.yml -f docker-compose.app.yml logs -f model-gateway
docker-compose -f docker-compose.yml -f docker-compose.app.yml logs -f frontend

# 查看所有日志
docker-compose -f docker-compose.yml -f docker-compose.app.yml logs -f
```

### 重启 / 停止

```bash
# 重启某个服务（改完代码后）
docker-compose -f docker-compose.yml -f docker-compose.app.yml restart model-gateway

# 停止所有服务
docker-compose -f docker-compose.yml -f docker-compose.app.yml down

# 停止并删除所有数据（危险！）
docker-compose -f docker-compose.yml -f docker-compose.app.yml down -v
```

### 更新代码后重新部署

```bash
# 改完代码后，重新构建并启动
docker-compose -f docker-compose.yml -f docker-compose.app.yml up -d --build

# 只重建某个服务
docker-compose -f docker-compose.yml -f docker-compose.app.yml up -d --build model-gateway
```

### 进入容器内部调试

```bash
# 进入某个容器的命令行
docker exec -it grasssea-model-gateway bash

# 在容器内你可以运行 Python、查看文件等
# 输入 exit 退出
```

---

## 7. 如何边部署边开发

**Docker 部署和本地开发完全不冲突！** 有两种工作模式：

### 模式 1：Docker 全托管（推荐入门）

- 所有服务都在 Docker 里跑
- 改代码 → 重启容器 → 生效
- 适合：测试、演示、不频繁改代码

```bash
# 改完代码
docker-compose -f docker-compose.yml -f docker-compose.app.yml up -d --build
```

### 模式 2：混合模式（推荐日常开发）

- 中间件跑在 Docker（数据库、缓存）
- 你正在改的服务跑在本机（热重载，秒生效）

```bash
# 终端1：启动中间件
docker-compose up -d

# 终端2：你要开发的服务跑在本机
uvicorn services.chat_service.main:app --reload --port 8001
# 改了代码→自动重启→立刻看到效果

# 终端3：前端开发
cd frontend && npm run dev
# 打开 http://localhost:3000
```

**重点**：代码在本机（`F:\GrassSea\`）随时修改，Docker 数据库在后台稳定运行。两者互不干扰。

---

## 8. 文件结构速查

```
F:/GrassSea/
│
├── docker-compose.yml          # 中间件编排（数据库、缓存等）
├── docker-compose.app.yml      # 应用服务编排（Python 微服务 + 前端）
（docker-compose.full.yml 已删除，请用 docker-compose.yml + docker-compose.app.yml 两个文件）
├── .dockerignore               # 告诉 Docker 哪些文件不要打包
├── .env                        # 环境变量（API Key 等）
│
├── docker-data/                # 📁 所有数据存这里（F盘）
│   ├── postgres/               # PostgreSQL 数据库文件
│   ├── mongodb/                # MongoDB 数据库文件
│   ├── redis/                  # Redis 持久化文件
│   ├── milvus/                 # 向量数据库
│   ├── minio/                  # 文件存储
│   ├── rabbitmq/               # 消息队列
│   └── ...
│
├── infrastructure/docker/
│   ├── Dockerfile              # Python 服务镜像构建文件
│   ├── Dockerfile.frontend     # 前端镜像构建文件
│   └── nginx/
│       └── grasssea.conf       # Nginx 反向代理配置
│
├── services/                   # Python 微服务源码
│   ├── model_gateway/
│   ├── chat_service/
│   ├── agent_service/
│   └── knowledge_service/
│
├── frontend/                   # React 前端源码
├── shared/                     # 共享 Python 模块
├── agents/                     # AI Agent 定义
└── ...
```

---

## 9. 端口速查表

| 端口 | 服务 | 访问方式 |
|------|------|---------|
| **80** | 前端界面 | http://localhost |
| **8001** | 对话服务 API | http://localhost:8001/docs |
| **8002** | 智能体服务 API | http://localhost:8002/docs |
| **8003** | 知识库服务 API | http://localhost:8003/docs |
| **8004** | 模型网关 API | http://localhost:8004/docs |
| 5432 | PostgreSQL | 数据库连接 |
| 27017 | MongoDB | 数据库连接 |
| 6379 | Redis | 缓存连接 |
| 5672 | RabbitMQ | 消息队列 |
| 15672 | RabbitMQ 管理界面 | http://localhost:15672 |
| 19530 | Milvus | 向量数据库 |
| 9000 | MinIO API | 对象存储 |
| 9001 | MinIO 控制台 | http://localhost:9001 |

---

## 10. 常见问题排查

### Q: `docker-compose` 命令报错 "not found"

**原因**：新版 Docker Desktop 用 `docker compose`（没有横杠）。

```bash
# 试试不加横杠
docker compose -f docker-compose.yml -f docker-compose.app.yml up -d
```

### Q: 端口被占用

```
Error: port 5432 is already in use
```

**原因**：你本机已经装了 PostgreSQL 占用了端口。

**解决**：关掉本机的 PostgreSQL 服务，或者修改 `.env` 中 `POSTGRES_PORT=5433`。

### Q: 某个服务一直在 restarting

```bash
# 查看该服务的日志
docker logs grasssea-model-gateway

# 常见原因：数据库还没就绪，等待一会即可
```

### Q: 磁盘空间不足

```bash
# 清理无用的 Docker 镜像和缓存
docker system prune -a
```

### Q: 我想完全从头开始

```bash
# 1. 停止并删除所有容器
docker-compose -f docker-compose.yml -f docker-compose.app.yml down -v

# 2. 清空数据目录（可选，会丢失所有数据）
rm -rf F:/GrassSea/docker-data/*

# 3. 重新启动
docker-compose -f docker-compose.yml -f docker-compose.app.yml up -d
```

### Q: 怎么查看 Docker 占了多少 F 盘空间

```bash
# Docker 系统占用（镜像+容器+缓存）
docker system df

# 数据文件占用
# 右键 F:\GrassSea\docker-data → 属性
```

---

## 附录：一段话总结 Docker 工作流

```
写代码 → 构建镜像 → 启动容器 → 访问服务
   ↑                              ↓
   └──── 改代码，再来一遍 ←──── 发现问题
```

对于日常开发，你**不需要**走完整流程。只需：

1. **第一次**：`docker-compose up -d` （启动数据库）
2. **每天**：本机 `uvicorn --reload` 跑服务（改代码自动生效）
3. **部署测试**：`docker-compose -f docker-compose.yml -f docker-compose.app.yml up -d --build`

**记住一句话**：Docker 帮你管数据库，你只管写代码。数据在 F 盘，C 盘不受影响。
