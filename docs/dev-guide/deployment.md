# GrassSea AI — 部署指南

## 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Docker | 24.x+ | 容器运行时 |
| K3s | 1.28+ | 轻量 Kubernetes (生产) |
| Python | 3.11+ | 服务运行环境 |
| Node.js | 20 LTS | 前端构建 |

## 环境变量

参见 `.env.example`，所有必需变量:

| 变量 | 说明 | 示例 |
|------|------|------|
| `APP_SECRET_KEY` | 应用密钥 | 随机 32 位字符串 |
| `JWT_SECRET_KEY` | JWT 签名密钥 | 随机 32 位字符串 |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | `sk-xxx` |
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | 强密码 |
| `MONGODB_PASSWORD` | MongoDB 密码 | 强密码 |
| `MINIO_SECRET_KEY` | MinIO Secret Key | 随机 |
| `RABBITMQ_PASSWORD` | RabbitMQ 密码 | 强密码 |

## 本地开发

```bash
# 1. 启动中间件
make up

# 2. 初始化
make setup
make db-migrate
make db-seed
make init-buckets

# 3. 启动服务
make run-model-gateway &
make run-knowledge &
make run-agent &
make run-chat &

# 4. 启动前端
cd frontend && npm install && npm run dev
```

## K3s 生产部署

```bash
# 1. 创建 namespace
kubectl apply -f infrastructure/k3s/namespace.yaml

# 2. 创建 ConfigMap 和 Secret
kubectl apply -f infrastructure/k3s/configmap.yaml
kubectl apply -f infrastructure/k3s/secret.yaml  # 先编辑填入真实值

# 3. 创建 PVC
kubectl apply -f infrastructure/k3s/persistent-volumes.yaml

# 4. 部署服务
kubectl apply -f infrastructure/k3s/deployments/
kubectl apply -f infrastructure/k3s/ingress.yaml

# 5. 检查状态
kubectl get pods -n grasssea
kubectl get svc -n grasssea
```

## 健康检查

- 模型网关: `GET http://<host>:8004/health`
- 知识库: `GET http://<host>:8003/health`
- 智能体: `GET http://<host>:8002/health`
- 对话: `GET http://<host>:8001/health`

## 数据库备份

```bash
# 手动备份
python scripts/backup_db.py

# 定时任务 (crontab)
0 2 * * * cd /app && python scripts/backup_db.py >> logs/backup.log 2>&1
```

## 监控

- Grafana: http://<host>:3000 (admin/grasssea-grafana)
- Jaeger: http://<host>:16686
- Prometheus: http://<host>:9090
- RabbitMQ Mgmt: http://<host>:15672
- MinIO Console: http://<host>:9001
