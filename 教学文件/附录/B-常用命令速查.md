# 附录B - 常用命令速查

> GrassSea 项目中日常使用的命令集合，按工具分类整理。

## Docker / Docker Compose

### 日常开发

```bash
# 启动所有中间件（数据库、缓存、队列）
docker-compose up -d

# 启动应用服务（与中间件配合使用）
docker-compose -f docker-compose.yml -f docker-compose.app.yml up -d

# 关闭所有服务
docker-compose down

# 查看运行中的容器状态
docker-compose ps

# 查看特定服务日志
docker-compose logs -f postgres
docker-compose logs -f redis --tail 50

# 进入容器内部
docker exec -it grasssea-postgres bash
```

### 数据库初始化

```bash
# 建表（含 timeseries schema 与 TimescaleDB 超表转换，幂等）
uv run python scripts/init_db.py

# 写入 7 项系统配置 + 默认本地用户 admin（幂等）
uv run python scripts/seed_data.py

# 初始化 MinIO 存储桶
uv run python scripts/init_minio.py

# 版本化迁移（需要时）
alembic upgrade head
```

### 镜像构建

```bash
# 重建应用镜像（推荐：按 compose 定义一次性构建全部服务）
docker-compose -f docker-compose.yml -f docker-compose.app.yml build

# 或单独构建 Python 服务镜像
docker build -f infrastructure/docker/Dockerfile -t grasssea-app:latest .

# 构建前端镜像
docker build -f infrastructure/docker/Dockerfile.frontend -t grasssea-frontend:latest .

# 查看镜像大小
docker images | grep grasssea

# 查看镜像层历史
docker history grasssea:latest

# 清理未使用的镜像和容器
docker system prune -a
```

## Git

### 日常开发

```bash
# 查看当前状态
git status

# 查看提交历史
git log --oneline -20

# 创建并切换到新分支
git checkout -b feature/xxx

# 暂存所有修改并提交
git add -A
git commit -m "描述"

# 推送到远程
git push origin feature/xxx

# 拉取最新代码
git pull origin develop

# 查看两个分支的差异
git diff develop..feature/xxx

# 回退到上一个版本（保留修改）
git reset HEAD~1

# 查看某个文件的修改历史
git log --oneline -- path/to/file.py
```

## Python / uv

> ⚠️ 本项目用 **uv** 管理依赖，`.venv` 由 uv 创建（**不含 pip**）。
> 命令请用 `uv run python ...`，不要依赖全局 `python`（本机全局为 3.14，与本项目不一致）。

### 虚拟环境

```bash
# 创建虚拟环境
uv venv

# 激活虚拟环境 (Windows Git Bash)
source .venv/Scripts/activate

# 激活虚拟环境 (Linux/macOS)
source .venv/bin/activate

# 退出虚拟环境
deactivate
```

### 包管理

```bash
# 安装 / 同步项目依赖（运行时）
uv sync

# 安装 / 同步项目依赖（含开发工具）
uv sync --extra dev

# 查看已安装的包
uv pip list

# 查看特定包的版本
uv pip show fastapi

# 在虚拟环境中执行脚本
uv run python scripts/init_db.py
```

## pytest

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定目录
pytest tests/unit/

# 运行特定文件
pytest tests/unit/test_config.py

# 运行特定测试类
pytest tests/unit/test_config.py::TestSettings

# 运行特定测试方法
pytest tests/unit/test_config.py::TestSettings::test_default_settings

# 按关键字筛选
pytest -k "test_config"

# 遇错即停
pytest -x

# 详细输出
pytest -v

# 显示 print 输出
pytest -s

# 运行最后失败的测试
pytest --lf

# 生成覆盖率报告
pytest --cov --cov-report=html
# 报告在 htmlcov/index.html
```

### 常用标记

```bash
# 只运行异步测试
pytest -m asyncio

# 跳过慢速测试
pytest -m "not slow"

# 并行运行（需安装 pytest-xdist）
pytest -n auto
```

## Uvicorn

### 启动服务

```bash
# 模型网关 (端口 8004)
uvicorn services.model_gateway.main:app --port 8004 --reload

# 对话服务 (端口 8001)
uvicorn services.chat_service.main:app --port 8001 --reload

# 智能体服务 (端口 8002)
uvicorn services.agent_service.main:app --port 8002 --reload

# 知识库服务 (端口 8003)
uvicorn services.knowledge_service.main:app --port 8003 --reload

# 指定主机和端口
uvicorn services.model_gateway.main:app --host 0.0.0.0 --port 8004

# 生产模式（多 worker）
uvicorn services.model_gateway.main:app --workers 4
```

### API 文档地址

```
http://localhost:8000/docs   # Swagger UI (交互式)
http://localhost:8000/redoc  # ReDoc (只读文档)
```

## 代码质量工具

```bash
# Ruff: 代码格式检查
ruff check .                    # 检查所有代码
ruff check --fix .              # 自动修复

# Ruff: 代码格式化
ruff format .                   # 格式化所有代码

# MyPy: 类型检查
mypy shared/ services/ agents/ tools/ --ignore-missing-imports

# Bandit: 安全检查
bandit -r shared/ services/
```

## npm (前端)

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 代码检查
npm run lint
```

## kubectl (K3s) — ⚠️ 不在本项目范围

```bash
# 查看所有 Pod
kubectl get pods -n grasssea

# 查看所有 Service
kubectl get svc -n grasssea

# 查看 Pod 日志
kubectl logs <pod-name> -n grasssea

# 实时查看日志
kubectl logs -f <pod-name> -n grasssea

# 进入 Pod 内部
kubectl exec -it <pod-name> -n grasssea -- sh

# 应用配置
# （K3s 清单已移除，本节仅作参考）

# 删除所有资源
kubectl delete namespace grasssea

# 查看部署状态
kubectl rollout status deployment -n grasssea

# 查看资源使用
kubectl top pods -n grasssea
```

## PostgreSQL

```bash
# 通过 Docker 连接数据库
docker exec -it grasssea-postgres psql -U grasssea -d grasssea

# 列出当前 schema 的表
\dt

# 列出所有 schema 的表（含 timeseries 超表）
\dt *.*

# 查看表结构
\d table_name

# 执行 SQL 查询
SELECT * FROM projects LIMIT 10;

# 退出
\q
```

## Redis

```bash
# 通过 Docker 连接 Redis CLI
docker exec -it grasssea-redis redis-cli

# 查看所有 key
KEYS *

# 获取某个 key 的值
GET key_name

# 查看 key 的过期时间
TTL key_name

# 监控实时命令
MONITOR

# 退出
EXIT
```

## RabbitMQ

管理控制台：`http://localhost:15672`（用户名/密码: grasssea/grasssea）

```bash
# 查看队列状态
docker exec grasssea-rabbitmq rabbitmqctl list_queues

# 查看连接数
docker exec grasssea-rabbitmq rabbitmqctl list_connections
```

## MinIO

管理控制台：`http://localhost:9001`（用户名/密码: grasssea-admin/grasssea-admin-secret）

## 环境变量速查

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_ENV` | development | 运行环境 (development/production) |
| `APP_DEBUG` | true | 调试模式 |
| `POSTGRES_HOST` | localhost | PostgreSQL 主机 |
| `POSTGRES_PORT` | 5432 | PostgreSQL 端口 |
| `REDIS_HOST` | localhost | Redis 主机 |
| `REDIS_PORT` | 6379 | Redis 端口 |
| `MILVUS_HOST` | localhost | Milvus 主机 |
| `MILVUS_PORT` | 19530 | Milvus 端口 |
| `MODEL_GATEWAY_PORT` | 8004 | 模型网关端口 |
| `AGENT_SERVICE_PORT` | 8002 | 智能体服务端口 |
| `KNOWLEDGE_SERVICE_PORT` | 8003 | 知识库服务端口 |
| `DEEPSEEK_API_KEY` | (空) | DeepSeek API Key |
