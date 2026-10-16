# ============================================================
# GrassSea AI — Python 微服务通用镜像
# 所有 Python 服务共用此镜像，通过 CMD 区分启动哪个服务
# ============================================================
FROM python:3.11-slim-bookworm

LABEL maintainer="GrassSea AI Team"
LABEL project="grasssea"

# 环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app

WORKDIR /app

# --- 镜像源加速（默认国内源；如需官方源可 --build-arg 覆盖）---
ARG APT_MIRROR=mirrors.tuna.tsinghua.edu.cn
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple

# --- 第一层: 系统依赖 ---
RUN set -eux; \
    for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources; do \
        if [ -f "$f" ]; then sed -i "s|deb.debian.org|${APT_MIRROR}|g" "$f"; fi; \
    done; \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# --- 第二层: Python 依赖 (利用 Docker 缓存) ---
# 先复制依赖文件，这样改代码不会触发重新 pip install
COPY pyproject.toml .

# 只安装运行时依赖，不装 dev (pytest/ruff/mypy 等)
RUN pip install --upgrade pip setuptools wheel -i ${PIP_INDEX} && \
    pip install -e . -i ${PIP_INDEX} && \
    pip install psycopg2-binary -i ${PIP_INDEX}

# --- 第三层: 应用代码 ---
COPY . .

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:${SERVICE_PORT:-8000}/health || exit 1

# 默认端口 (各服务可通过环境变量覆盖)
EXPOSE 8000

# 默认启动命令 (docker-compose 中各自覆盖)
CMD ["uvicorn", "services.model_gateway.main:app", "--host", "0.0.0.0", "--port", "8004"]
