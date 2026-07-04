# ============================================================
# GrassSea AI — Makefile
# 常用命令快捷方式
# ============================================================
SHELL := /bin/bash

.PHONY: help up down up-full ps logs build test lint lint-fix clean migrate setup init-buckets

help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---- Docker Compose ----
up: ## 启动核心中间件 (postgres mongodb redis milvus minio rabbitmq)
	docker-compose up -d postgres mongodb redis milvus-etcd milvus-minio milvus minio rabbitmq
	@echo "等待服务就绪..."
	@sleep 5
	docker-compose ps

up-full: ## 启动全部服务 (含 neo4j, jaeger, prometheus, grafana)
	docker-compose --profile full up -d
	@echo "等待全部服务就绪..."
	@sleep 10
	docker-compose ps

down: ## 停止并移除所有容器
	docker-compose --profile full --profile kg --profile observability down

down-volumes: ## 停止并移除所有容器 + 数据卷 (危险)
	docker-compose --profile full --profile kg --profile observability down -v

ps: ## 查看所有服务状态
	docker-compose ps

logs: ## 查看所有服务日志 (Ctrl+C 退出)
	docker-compose logs -f

logs-%: ## 查看指定服务日志 (例如: make logs-postgres)
	docker-compose logs -f $*

# ---- 开发环境 ----
setup: ## 初始化开发环境 (安装依赖 + 初始化数据库)
	pip install -e ".[dev]"
	cp -n .env.example .env || true
	@echo "开发环境初始化完成"

init-buckets: ## 初始化 MinIO bucket
	@echo "初始化 MinIO buckets..."
	@python scripts/init_minio.py

db-migrate: ## 运行 Alembic 数据库迁移
	cd shared/models && alembic upgrade head

db-migrate-new: ## 创建新的 Alembic 迁移 (usage: make db-migrate-new msg="add users table")
	cd shared/models && alembic revision --autogenerate -m "$(msg)"

db-seed: ## 运行数据库种子脚本
	python scripts/seed_data.py

# ---- 测试 ----
test: ## 运行所有测试
	pytest tests/ -v

test-cov: ## 运行测试并生成覆盖率报告
	pytest tests/ -v --cov=shared --cov=services --cov=agents --cov=tools --cov-report=term-missing --cov-report=html

test-unit: ## 仅运行单元测试
	pytest tests/unit/ -v

test-integration: ## 仅运行集成测试
	pytest tests/integration/ -v

test-%: ## 运行匹配模式的测试 (例如: make test-rag)
	pytest tests/ -v -k $*

# ---- 代码质量 ----
lint: ## 代码检查 (ruff + mypy)
	ruff check .
	mypy shared/ services/ agents/ tools/

lint-fix: ## 自动修复 lint 问题
	ruff check . --fix

format: ## 格式化代码 (ruff)
	ruff format .

security-scan: ## 安全扫描 (bandit)
	bandit -r shared/ services/ agents/ tools/ -ll

# ---- 服务启动 (开发模式) ----
run-model-gateway: ## 启动模型网关服务
	uvicorn services.model_gateway.main:app --host 0.0.0.0 --port $(MODEL_GATEWAY_PORT) --reload

run-chat: ## 启动对话服务
	uvicorn services.chat_service.main:app --host 0.0.0.0 --port $(CHAT_SERVICE_PORT) --reload

run-knowledge: ## 启动知识库服务
	uvicorn services.knowledge_service.main:app --host 0.0.0.0 --port $(KNOWLEDGE_SERVICE_PORT) --reload

run-agent: ## 启动智能体服务
	uvicorn services.agent_service.main:app --host 0.0.0.0 --port $(AGENT_SERVICE_PORT) --reload

# ---- 清理 ----
clean: ## 清理临时文件和缓存
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage