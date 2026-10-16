# 05 - Docker 开发环境

## 学习目标

学完本文件后，你将能够：
1. 理解 Docker 的核心概念（镜像、容器、数据卷）
2. 区分容器和虚拟机的本质差异
3. 读懂 `docker-compose.yml` 的完整结构
4. 理解健康检查、网络、数据卷、环境变量的配置方式
5. 能够独立编写一个多服务的 docker-compose.yml

## 前置知识

- 了解什么是数据库（PostgreSQL、MongoDB、Redis 这些名字至少听说过）
- 了解端口的概念（如 `localhost:5432` 中的 `5432` 是端口）
- 安装过 Docker Desktop（没有的话请先安装）

## 概念讲解

### 一、Docker 是什么 —— 容器 vs 虚拟机

**传统方式的问题**：假设你要在本机安装 PostgreSQL、MongoDB、Redis、RabbitMQ、MinIO、Milvus、Neo4j 共 7 个数据库。每个数据库有不同的系统依赖、配置文件、启动脚本。在 Windows 上装一遍可能需要一整天。

**虚拟机的方案**：在物理机上运行一个完整的操作系统（Guest OS），在里面安装应用。每个虚拟机需要独立的 CPU、内存、磁盘。

**容器的方案**：共享宿主机的操作系统内核，每个容器只包含应用及其依赖。

```
虚拟机架构:                          容器架构:

┌─────────────┐                    ┌─────────────────────────┐
│   App A     │                    │  App A  │ App B │ App C │
├─────────────┤                    ├─────────┼───────┼───────┤
│  Guest OS   │ ← 完整操作系统        │  Bin/   │ Bin/  │ Bin/  │
├─────────────┤                    │  Libs   │ Libs  │ Libs  │
│ Hypervisor  │                    ├─────────┴───────┴───────┤
├─────────────┤                    │     Docker Engine       │
│   Host OS   │                    ├─────────────────────────┤
├─────────────┤                    │       Host OS            │
│   Hardware  │                    ├─────────────────────────┤
└─────────────┘                    │       Hardware           │
                                    └─────────────────────────┘

启动时间: 分钟级                     启动时间: 秒级
大小: GB 级                         大小: MB 级
隔离性: 强（独立内核）                隔离性: 中等（共享内核）
```

**一句话总结**：虚拟机是"虚拟硬件"，容器是"虚拟环境"。对于运行数据库和服务，容器足够了，而且更快、更轻。

### 二、Docker 的三个核心概念

```
镜像 (Image)     →     容器 (Container)    →     数据卷 (Volume)
    │                        │                        │
    │  docker run            │  docker stop           │ 持久化存储
    ├──────────────────────> ├────────────────────>   ├──────────
    │                        │                        │
  相当于"类"               相当于"实例"              相当于"外挂硬盘"
  只读模板                 可运行的进程               容器删除后数据还在
```

**类比理解**：

```
镜像 = 操作系统安装盘 ISO 文件（只读模板）
容器 = 安装好后正在运行的 Windows（运行实例）
数据卷 = D 盘（容器删了，D 盘数据还在）

docker pull nginx     → 下载镜像（下载 ISO）
docker run nginx      → 启动容器（安装并启动 Windows）
docker stop container → 停止容器（关机）
docker rm container   → 删除容器（格式化 C 盘，但 D 盘没事）
```

### 三、docker-compose.yml —— 编排多个容器

Docker Compose 让你用 YAML 文件定义多个容器的配置，然后一条命令启动所有服务。

```bash
docker compose up -d    # 启动所有服务（-d 表示后台运行）
docker compose down     # 停止并删除所有服务
docker compose ps       # 查看服务状态
docker compose logs -f  # 查看日志（-f 表示实时跟踪）
```

## 项目代码精讲

GrassSea 的 `docker-compose.yml` 定义了 9 个服务。我们逐一解析关键配置模式。

### 通用模板 —— 一个完整服务的结构

```
services:
  服务名:
    image: 镜像名:版本号          ← 从哪个镜像启动
    container_name: 容器名        ← 给容器起个名字
    restart: unless-stopped       ← 崩溃自动重启
    environment:                  ← 环境变量
      KEY: value
    ports:                        ← 端口映射
      - "宿主机端口:容器端口"
    volumes:                      ← 数据卷
      - 宿主机路径:容器路径
    healthcheck:                  ← 健康检查
      test: 检查命令
      interval: 检查间隔
    networks:                     ← 网络
      - 网络名
```

### 服务 1：PostgreSQL（关系数据库）

```yaml
  postgres:
    image: timescale/timescaledb:2.14.2-pg15
    container_name: grasssea-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-grasssea}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-grasssea}
      POSTGRES_DB: ${POSTGRES_DB:-grasssea}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - type: bind
        source: F:/GrassSea/docker-data/postgres
        target: /var/lib/postgresql/data
      - ./infrastructure/docker/postgres/init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-grasssea} -d ${POSTGRES_DB:-grasssea}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - grasssea-net
```

**逐行解析：**

**镜像选择** — `timescale/timescaledb:2.14.2-pg15`
这不是普通的 PostgreSQL，而是集成了 TimescaleDB 扩展的 PostgreSQL 15。TimescaleDB 用于存储时序数据（如 Token 用量统计）。

**环境变量语法** — `${POSTGRES_USER:-grasssea}`
这是 Docker Compose 的变量替换语法。含义：
- 优先使用 `.env` 文件中的 `POSTGRES_USER`
- 如果没设置，使用默认值 `grasssea`
- `:-` 表示"如果变量未设置或为空"

**端口映射** — `"${POSTGRES_PORT:-5432}:5432"`
```
"宿主机端口:容器端口"

宿主机端口 5432 → 容器的 5432 端口
（外部访问用）     （容器内部监听）
```

这意味着你可以在本机用 `localhost:5432` 连接到容器内的 PostgreSQL。

**数据卷（volumes）**：
```yaml
    volumes:
      - type: bind
        source: F:/GrassSea/docker-data/postgres  # 宿主机路径
        target: /var/lib/postgresql/data          # 容器内路径
```

`bind` 类型：将宿主机目录直接映射到容器内。效果是 PostgreSQL 写数据到 `/var/lib/postgresql/data` 时，实际写到了 `F:/GrassSea/docker-data/postgres`。即使容器被删除，数据还在。

**初始化脚本**：
```yaml
      - ./infrastructure/docker/postgres/init:/docker-entrypoint-initdb.d
```

PostgreSQL 镜像的约定：容器首次启动时，会自动执行 `/docker-entrypoint-initdb.d/` 目录下的所有 `.sql` 文件。GrassSea 用这个机制自动创建 TimescaleDB 扩展。

**健康检查（healthcheck）**：
```yaml
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U grasssea -d grasssea"]
      interval: 10s    # 每 10 秒检查一次
      timeout: 5s      # 单次检查超时时间
      retries: 5       # 失败 5 次后标记为 unhealthy
```

健康检查是 Docker 的一个重要机制。标记为 unhealthy 的容器会被 `depends_on: condition: service_healthy` 阻塞——后续依赖该服务的容器不会启动。

### 服务 2：MongoDB（文档数据库）

```yaml
  mongodb:
    image: mongo:7.0
    container_name: grasssea-mongodb
    restart: unless-stopped
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGODB_USER:-grasssea}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGODB_PASSWORD:-grasssea}
      MONGO_INITDB_DATABASE: ${MONGODB_DB:-grasssea}
    ports:
      - "${MONGODB_PORT:-27017}:27017"
    volumes:
      - type: bind
        source: F:/GrassSea/docker-data/mongodb
        target: /data/db
      - ./infrastructure/docker/mongodb/init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "mongosh --eval 'db.adminCommand(\"ping\")' --quiet"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - grasssea-net
```

结构与 PostgreSQL 类似，但注意几个差异：

1. MongoDB 的默认端口是 27017（不是 5432）
2. 健康检查命令不同：`mongosh --eval 'db.adminCommand("ping")'` —— 发送一个 ping 命令验证 MongoDB 是否响应
3. 数据目录是 `/data/db`

### 服务 3：Milvus（向量数据库）—— 多服务依赖

Milvus 比较特殊，它需要 etcd（配置存储）和 MinIO（对象存储）作为依赖：

```yaml
  milvus-etcd:              # 子服务 1：配置存储
    image: quay.io/coreos/etcd:v3.5.12
    # ...

  milvus-minio:             # 子服务 2：对象存储
    image: minio/minio:RELEASE.2024-01-16T16-07-38Z
    # ...

  milvus:                   # 主服务
    image: milvusdb/milvus:v2.4.0
    depends_on:             # 依赖声明
      milvus-etcd:
        condition: service_healthy  # 必须 healthy 才启动
      milvus-minio:
        condition: service_started  # 启动即可（没有健康检查）
    environment:
      ETCD_ENDPOINTS: milvus-etcd:2379     # 通过容器名访问
      MINIO_ADDRESS: milvus-minio:9000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9091/healthz"]
      interval: 30s
      timeout: 20s
      retries: 3
```

**关键知识点**：

1. **depends_on 的条件控制**：
   - `condition: service_healthy` —— 只当依赖服务通过健康检查后才启动（Docker Compose v3.8+）
   - `condition: service_started` —— 依赖服务启动即可（不管是否 healthy）

2. **容器间通信**：Milvus 通过 `milvus-etcd:2379` 访问 etcd，而不是 `localhost:2379`。这是因为它们在同一网络 `grasssea-net` 中，Docker 提供了内置的 DNS 解析，**容器名就是主机名**。

### 生成架构：Structured Profiles

```yaml
  neo4j:
    # ...
    profiles:
      - full
      - kg

  jaeger:
    # ...
    profiles:
      - full
      - observability

  prometheus:
    # ...
    profiles:
      - full
      - observability

  grafana:
    # ...
    profiles:
      - full
      - observability
```

profiles 让你可以有选择地启动服务：

```bash
# 默认启动：核心服务（没有 profiles 限制的）
docker compose up -d

# 启动所有服务（包括有 profiles 的）
docker compose --profile full up -d

# 只启动可观测性相关服务
docker compose --profile observability up -d

# 启动多个 profile
docker compose --profile full --profile kg up -d
```

### 网络（networks）

```yaml
networks:
  grasssea-net:
    driver: bridge
    name: grasssea-net
```

一个自定义的桥接网络。所有加入这个网络的服务可以通过容器名互相访问。

```
┌────────────────── grasssea-net ──────────────────┐
│                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │postgres  │  │ mongodb  │  │  redis   │        │
│  │ :5432    │  │ :27017   │  │ :6379    │        │
│  └──────────┘  └──────────┘  └──────────┘        │
│                                                    │
│    容器间通过名称访问: postgres:5432                 │
│    外部通过宿主机端口: localhost:5432               │
│                                                    │
└────────────────────────────────────────────────────┘
```

### 数据卷：bind vs named volume

GrassSea 主要使用了两种卷类型：

```yaml
# 1. bind mount — 宿主机绝对路径
volumes:
  - type: bind
    source: F:/GrassSea/docker-data/postgres
    target: /var/lib/postgresql/data

# 2. named volume — Docker 管理，不在宿主机暴露
volumes:
  milvus_data:

# 在 services 中引用 named volume:
volumes:
  - milvus_data:/var/lib/milvus
```

| 类型 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| bind mount | 开发环境 | 能看到文件，方便调试和备份 | 路径依赖宿主机 |
| named volume | 生产环境 | Docker 管理，性能好，跨平台 | 不透明 |

## 手把手实践

### 任务：编写一个简化的 docker-compose.yml

假设你只需要 PostgreSQL 和 Redis 两个服务。

**步骤 1**：创建 `docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:15-alpine
    container_name: my-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: devuser
      POSTGRES_PASSWORD: devpass
      POSTGRES_DB: devdb
    ports:
      - "5432:5432"
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U devuser -d devdb"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: my-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - ./data/redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
```

**步骤 2**：启动

```bash
docker compose up -d
```

**步骤 3**：验证

```bash
docker compose ps              # 看状态
docker compose logs postgres   # 看日志
```

**步骤 4**：连接测试

```bash
# 用 psql 连接 PostgreSQL（如果安装了）
psql -h localhost -U devuser -d devdb

# 或者用 Python 测试
python -c "import psycopg2; conn = psycopg2.connect('postgresql://devuser:devpass@localhost:5432/devdb'); print('连接成功')"
```

## 视频学习资源

在 B 站搜索以下关键词：
1. "Docker 入门教程" — Docker 基本概念和常用命令
2. "docker-compose 实战" — docker-compose.yml 的编写和调试
3. "Docker 健康检查 healthcheck" — 深入理解容器健康检查机制

## 常见问题与排错

### Q1: 端口被占用 `port is already allocated`
**原因**：宿主机端口（如 5432）已被其他程序占用（可能是本地安装的 PostgreSQL）。
**解决**：
```bash
# 查看端口占用
netstat -ano | findstr 5432

# 方案 A：停止占用端口的程序
# 方案 B：修改 docker-compose.yml 的宿主机端口
ports:
  - "15432:5432"  # 映射到 15432 而非 5432
```

### Q2: 容器启动后立即退出
**原因**：容器内的主进程执行完毕或出错退出。
**排查**：
```bash
docker compose logs 服务名    # 查看日志
docker compose ps -a          # 查看退出状态
```

### Q3: healthcheck 一直 failing
**原因**：健康检查命令不正确，或服务启动时间超过 interval * retries。
**排查**：
```bash
# 手动进入容器测试健康检查命令
docker exec -it grasssea-postgres bash
pg_isready -U grasssea -d grasssea
```

### Q4: 数据卷中的数据丢失了
**原因**：使用了 `docker compose down -v`（-v 会删除 volumes）。
**牢记**：`docker compose down` 不会删除 bind mount 的数据（在宿主机目录中），但 `docker compose down -v` 会删除 named volume。

### Q5: Windows 上路径问题
GrassSea 的 `docker-compose.yml` 中使用了 `F:/GrassSea/docker-data/...` 这样的绝对路径。如果你克隆到其他盘符，需要修改这些路径。更好的做法是使用相对路径：
```yaml
volumes:
  - ./docker-data/postgres:/var/lib/postgresql/data
```

## 练习任务

1. **画出服务依赖图**：根据 `depends_on` 和 `profiles`，画出 GrassSea 所有 Docker 服务的依赖关系图（箭头表示"依赖"）。

2. **添加新服务**：在 docker-compose.yml 中添加一个 Adminer（数据库管理 Web UI）服务，映射到 8080 端口，并与 postgres 在同一网络。

3. **健康检查设计**：为每个 GrassSea 服务的健康检查命令写注释，解释为什么选择这个命令。思考有没有更好的检查方式。

4. **资源限制**：研究 Docker Compose 的 `deploy.resources` 配置，为 GrassSea 的 postgres 服务添加内存限制（如 512M），防止它消耗过多系统资源。
