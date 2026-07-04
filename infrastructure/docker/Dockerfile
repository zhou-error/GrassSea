# ============================================================
# GrassSea AI — 基础 Python 服务镜像
# 所有微服务基于此 Dockerfile
# ============================================================
FROM python:3.11-slim-bookworm

LABEL maintainer="GrassSea AI Team"
LABEL project="grasssea"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY pyproject.toml .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e ".[dev]" && \
    pip install psycopg2-binary

# 复制应用代码
COPY . .

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:${SERVICE_PORT:-8000}/health || exit 1

EXPOSE ${SERVICE_PORT:-8000}

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${SERVICE_PORT:-8000}"]
