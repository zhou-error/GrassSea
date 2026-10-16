# 03 - Docker 镜像构建

> ⚠️ **范围说明（项目定位：个人使用）**
>
> 本章讲解的集群部署 / CI/CD / 可观测性属于通用工程知识，**当前项目不包含这部分能力**：
> 相关流水线与部署清单已从仓库移除，对应容器配置也已从 `docker-compose.yml` 移除。
> 本章可作为学习资料阅读，但无需在本项目中落地。

## 学习目标

1. 理解 Docker 镜像的分层结构和构建缓存机制
2. 掌握多阶段构建（Multi-stage Build）的原理和价值
3. 能够读懂和理解 GrassSea 的 Python 后端和前端 Dockerfile
4. 理解 Dockerfile 中的关键指令（FROM、COPY、RUN、CMD、EXPOSE）

## 前置知识

- 了解 Docker 的基本概念（镜像、容器）
- 了解 Linux 终端的基本操作（cd、ls、cp）
- 了解 pip（Python 包管理器）和 npm（Node.js 包管理器）的基本用法

## 概念讲解

### Docker 镜像的分层结构

Docker 镜像像"千层饼"——每一层叠加在上一层之上：

```
镜像的分层结构:

  ┌────────────────────────────┐
  │  第6层: COPY . .           │  ← 应用代码（经常变）
  ├────────────────────────────┤
  │  第5层: RUN pip install    │  ← Python 依赖（偶尔变）
  ├────────────────────────────┤
  │  第4层: COPY pyproject.toml│  ← 依赖声明文件
  ├────────────────────────────┤
  │  第3层: RUN apt-get install│  ← 系统包（几乎不变）
  ├────────────────────────────┤
  │  第2层: WORKDIR /app       │  ← 工作目录
  ├────────────────────────────┤
  │  第1层: FROM python:3.11   │  ← 基础镜像
  └────────────────────────────┘

  关键规则: 层是只读的，修改任何一层 = 该层及之上的所有层重新构建
```

### 为什么层的顺序很重要？

Docker 的构建缓存是按层来的。如果一个层的输入没变，Docker 直接复用缓存。所以把"经常变的"放在下面，"很少变的"放在上面。

```
❌ 错误的顺序:
  COPY . .                    ← 代码变了 → 缓存失效
  RUN pip install -r ...      ← 也重新运行（慢！）

✅ 正确的顺序:
  COPY pyproject.toml .       ← 依赖声明没变 → 缓存命中
  RUN pip install -e .        ← 复用缓存，跳过（快！）
  COPY . .                    ← 只有代码变了才重新复制
```

### 多阶段构建 — 构建和运行分离

编译型语言的典型流程是先"编译"再"运行"。多阶段构建将这个模式带到了容器中：

```
多阶段构建原理:

  阶段一: 构建 (Builder Stage)
  ┌──────────────────────────────────────┐
  │ FROM node:20-alpine AS builder       │  ← 完整 Node.js 环境
  │                                      │
  │ COPY package.json .                  │
  │ RUN npm install          ← 下载依赖  │
  │                                      │
  │ COPY src/ .                          │
  │ RUN npm run build        ← 编译打包  │
  │                                      │
  │ 产物: /app/dist/  (一堆 HTML/JS/CSS) │
  └──────────────────────────────────────┘
       │
       │  copy --from=builder  只复制最终产物（几十 KB）
       ▼
  阶段二: 运行 (Runtime Stage)
  ┌──────────────────────────────────────┐
  │ FROM nginx:alpine                    │  ← 轻量的 Nginx
  │                                      │
  │ COPY --from=builder /app/dist /html  │  ← 只复制静态文件
  │                                      │
  │ 最终镜像大小: ~20MB (vs 500MB+)     │
  │ 不包含: Node.js / npm / node_modules │
  └──────────────────────────────────────┘
```

**核心价值**：最终运行镜像只包含运行所需的文件，不包含构建工具（如编译器、开发依赖）。镜像更小、攻击面更窄。

## 项目代码精讲

### Python 服务 Dockerfile

```dockerfile
# infrastructure/docker/Dockerfile 第5行
FROM python:3.11-slim-bookworm
```

**逐段解析**：
- `python:3.11` — Python 3.11 版本
- `slim` — 精简版（只包含运行 Python 所需的最小系统库）
- `bookworm` — Debian 12 的代号（确定底层操作系统版本）

选择 `slim` 而非 `alpine` 是因为 Alpine Linux 使用 musl libc，而很多 Python 的 C 扩展（如 psycopg2）需要 glibc。`slim` 版基于 Debian，兼容性最好。

```dockerfile
# 第10-14行: 环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
```

这些环境变量都是"Docker 最佳实践"：
- `PYTHONUNBUFFERED=1` — stdout/stderr 不缓冲，日志实时输出（不会积攒一批才显示）
- `PYTHONDONTWRITEBYTECODE=1` — 不生成 `.pyc` 字节码文件（减少镜像体积）
- `PIP_NO_CACHE_DIR=1` — pip 不缓存下载的包（减少镜像体积）
- `PIP_DISABLE_PIP_VERSION_CHECK=1` — 不检查 pip 新版本（减少网络请求 + 提速）

```dockerfile
# 第20-24行: 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
```

**关键模式**：
- `&& apt-get update && apt-get install` — 在同一个 RUN 中完成（减少层数）
- `--no-install-recommends` — 只安装必需包，不装推荐的（减少体积）
- `&& rm -rf /var/lib/apt/lists/*` — 安装后立即清理包缓存（减少体积）
- 注意所有都在一个 `RUN` 命令中——如果分开，缓存文件会留在中间层

```dockerfile
# 第28-33行: Python 依赖（利用缓存）
COPY pyproject.toml .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e . && \
    pip install psycopg2-binary
```

**关键设计**：先只复制 `pyproject.toml`，再 `pip install`。这样只要项目依赖不变，Docker 就能复用这一层的缓存，跳过耗时的 pip install。

```dockerfile
# 第36行: 应用代码
COPY . .
```

这一行放在最后，因为代码变得最频繁。前面的层（系统依赖、Python 依赖）都可以复用缓存。

```dockerfile
# 第39-40行: 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:${SERVICE_PORT:-8000}/health || exit 1
```

Docker 会每 30 秒执行这个命令。如果失败（`exit 1`），Docker 标记容器为 `unhealthy`，编排工具（如 K3s）可以自动重启它。`${SERVICE_PORT:-8000}` 是 Bash 语法：使用 `SERVICE_PORT` 环境变量，如果没有设置则默认 8000。

### 前端多阶段构建 Dockerfile

```dockerfile
# infrastructure/docker/Dockerfile.frontend
# 阶段1: Node.js 编译
FROM node:20-alpine AS builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# 阶段2: Nginx 部署
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY infrastructure/docker/nginx/grasssea.conf \
     /etc/nginx/conf.d/default.conf
```

**逐段解析**：

1. `FROM node:20-alpine AS builder` — 阶段一别名 `builder`。Alpine 版 Node.js 非常小（~50MB），适合构建阶段。

2. `COPY package.json package-lock.json ./` — 先复制依赖文件，利用 npm install 的层缓存。和前一个 Dockerfile 的思路完全一致。

3. `RUN npm run build` — 编译 TypeScript 代码，打包为静态文件。

4. `FROM nginx:alpine` — 阶段二，全新的干净镜像。不包含 Node.js。

5. `COPY --from=builder /app/dist /usr/share/nginx/html` — **多阶段构建的关键语法**。`--from=builder` 从阶段一复制文件。只复制构建产物（HTML/JS/CSS），不复制源代码和 node_modules。

6. 最终镜像只包含 Nginx + 静态文件，体积约 20MB。

## 手把手实践

### 实验一：构建并观察层缓存

```bash
# 第一次构建（全量）
docker build -f infrastructure/docker/Dockerfile -t grasssea:test .

# 第二次构建（应该全缓存）
docker build -f infrastructure/docker/Dockerfile -t grasssea:test .

# 修改任意 .py 文件后第三次构建
# 观察哪些层重新构建，哪些层使用缓存
```

观察输出中的 `---> Using cache` 和 `---> Running in ...`，理解哪些步骤跳过了，哪些重新执行了。

### 实验二：检查镜像大小

```bash
# 查看镜像大小
docker images | grep grasssea

# 查看镜像的层历史
docker history grasssea:test
```

## 视频学习资源

请在 B站（bilibili.com）搜索以下关键词：

- "Docker 镜像分层 构建缓存" -- 理解层的缓存机制
- "Docker 多阶段构建 实战" -- 学习多阶段构建
- "Dockerfile 最佳实践" -- 学习 Dockerfile 编写规范
- "Docker Compose 编排 Python 微服务" -- 学习完整部署方案

## 常见问题与排错

**Q1：pip install 每次都重新下载怎么办？**

A：检查是否在 `COPY pyproject.toml` 之前有代码变化导致的层失效。确保 `COPY pyproject.toml .` 和 `RUN pip install` 在 `COPY . .` 之前。

**Q2：镜像太大了（>1GB）怎么办？**

A：1) 使用 `slim` 基础镜像而非 `latest`；2) 使用多阶段构建；3) 在同一个 RUN 中运行 `apt-get update && install && clean`；4) 创建 `.dockerignore` 文件排除 `node_modules`、`.git`、`__pycache__` 等。

**Q3：`--no-install-recommends` 没有效果？**

A：这个选项只影响 `apt-get`，不影响 `pip`。对于 pip，使用 `--no-cache-dir` 来减少缓存。

**Q4：前端 Dockerfile 中为什么有两个 `FROM`？**

A：这就是多阶段构建。第一个 `FROM` 是构建阶段（有 Node.js 用于编译），第二个 `FROM` 是运行阶段（只有 Nginx 用于提供静态文件）。构建工具不会出现在最终镜像中。

## 练习任务

1. **概念题**：解释 Docker 镜像的"层"是什么，为什么层的顺序会影响构建速度？
2. **实践题**：为 GrassSea 项目创建一个 `.dockerignore` 文件，列出应该被排除的目录和文件（如 `.git`、`__pycache__`、`node_modules`、`*.pyc` 等）。
3. **分析题**：读取 `infrastructure/docker/Dockerfile` 和 `Dockerfile.frontend`，对比两者的共性模式（缓存策略、多阶段思想）。
4. **设计题**：如果要给 knowledge_service 创建一个专用的 Dockerfile（不是共用的通用镜像），你会做哪些优化？提示：knowledge_service 需要 Milvus 客户端、PDF 处理库等特殊依赖。
