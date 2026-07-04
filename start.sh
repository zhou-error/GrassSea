#!/bin/bash
# ============================================================
# GrassSea AI — 一键启动脚本 (Git Bash / Linux / macOS)
# ============================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}  ✓${NC} $1"; }
fail()  { echo -e "${RED}  ✗${NC} $1"; }
title() { echo -e "\n${CYAN}$1${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     🌊 白草沧智 GrassSea AI — 启动中...      ║"
echo "╚══════════════════════════════════════════════╝"

# ---- 1. 检查前置条件 ----
title "[1/5] 检查环境..."

command -v docker  &>/dev/null || { fail "Docker 未安装"; exit 1; }
command -v python  &>/dev/null || { fail "Python 未安装"; exit 1; }
command -v node    &>/dev/null || { fail "Node.js 未安装"; exit 1; }
ok "Docker  已就绪"
ok "Python  已就绪 ($(python --version 2>&1))"
ok "Node.js 已就绪 ($(node --version))"

# ---- 2. 启动 Docker 中间件 ----
title "[2/5] 启动 Docker 中间件..."
docker compose up -d postgres mongodb redis rabbitmq minio

info "等待服务健康检查..."
while true; do
    HEALTHY=$(docker compose ps 2>/dev/null | grep -c "healthy" || true)
    [ "$HEALTHY" -ge 5 ] && break
    sleep 2
done

ok "PostgreSQL  (localhost:5432)"
ok "MongoDB     (localhost:27017)"
ok "Redis       (localhost:6379)"
ok "MinIO       (localhost:9000 / :9001)"
ok "RabbitMQ    (localhost:5672 / :15672)"

# ---- 3. 启动后端服务 ----
title "[3/5] 启动后端服务..."

python -m uvicorn services.model_gateway.main:app --host 0.0.0.0 --port 8004 --reload &
ok "模型网关    (http://localhost:8004)  PID=$!"
sleep 2

python -m uvicorn services.knowledge_service.main:app --host 0.0.0.0 --port 8003 --reload &
ok "知识库/RAG  (http://localhost:8003)  PID=$!"
sleep 2

python -m uvicorn services.agent_service.main:app --host 0.0.0.0 --port 8002 --reload &
ok "智能体编排  (http://localhost:8002)  PID=$!"
sleep 2

python -m uvicorn services.chat_service.main:app --host 0.0.0.0 --port 8001 --reload &
ok "对话服务    (http://localhost:8001)  PID=$!"
sleep 3

# ---- 4. 前端依赖 ----
title "[4/5] 检查前端依赖..."
if [ ! -d "frontend/node_modules" ]; then
    info "安装前端依赖..."
    cd frontend && npm install && cd ..
fi
ok "前端依赖已就绪"

# ---- 5. 启动前端 ----
title "[5/5] 启动前端..."
cd frontend && npm run dev &
FRONTEND_PID=$!
ok "前端 Vite   (http://localhost:3000)  PID=$FRONTEND_PID"

sleep 3

# ---- 检查服务 ----
title "验证服务..."

check_url() {
    if curl -s -o /dev/null -w "%{http_code}" "$1" 2>/dev/null | grep -q "200"; then
        ok "$2"
    else
        fail "$2 (可能仍在启动中)"
    fi
}

check_url "http://localhost:8004/health" "模型网关 /health"
check_url "http://localhost:8003/health" "知识库   /health"
check_url "http://localhost:8002/health" "智能体   /health"
check_url "http://localhost:8001/health" "对话服务 /health"

# ---- 打开浏览器 ----
if command -v start &>/dev/null; then
    start http://localhost:3000   # Windows
elif command -v open &>/dev/null; then
    open http://localhost:3000     # macOS
elif command -v xdg-open &>/dev/null; then
    xdg-open http://localhost:3000 # Linux
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║         🎉 GrassSea AI 启动完成！            ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  前端页面   http://localhost:3000            ║"
echo "║  模型网关   http://localhost:8004/health     ║"
echo "║  知识库     http://localhost:8003/health     ║"
echo "║  智能体     http://localhost:8002/health     ║"
echo "║  对话服务   http://localhost:8001/health     ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  按 Ctrl+C 停止所有 Python 服务               ║"
echo "║  停止 Docker:  docker compose down           ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 等待前台进程
wait
