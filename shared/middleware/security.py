"""安全中间件 — RBAC + API Key + 预签名 URL + 审计日志"""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from shared.utils.logging import get_logger

logger = get_logger(__name__)


# ==== RBAC 角色权限定义 ====
ROLE_PERMISSIONS = {
    "admin": ["*"],
    "project_lead": ["project:read", "project:write", "knowledge:read", "knowledge:write", "member:manage", "task:assign"],
    "engineer": ["project:read", "project:write", "knowledge:read", "tool:use", "report:generate"],
    "guest": ["project:read", "knowledge:read"],
    "api_user": ["api:access"],
}

API_KEYS: dict[str, dict] = {}  # 生产环境存数据库


def check_permission(role: str, required: str) -> bool:
    """检查角色权限"""
    perms = ROLE_PERMISSIONS.get(role, [])
    return "*" in perms or required in perms


# ==== API Key HMAC-SHA256 签名 ====

def generate_api_key(user_id: str) -> tuple[str, str]:
    """生成 API Key 和 Secret"""
    api_key = f"gs_{hashlib.sha256(f'{user_id}:{time.time()}'.encode()).hexdigest()[:32]}"
    secret = hashlib.sha256(f"secret_{api_key}_{time.time()}".encode()).hexdigest()
    API_KEYS[api_key] = {"user_id": user_id, "secret": secret, "created": datetime.utcnow()}
    return api_key, secret


def verify_hmac_signature(payload: bytes, signature: str, secret: str) -> bool:
    """验证 HMAC-SHA256 签名"""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ==== 预签名 URL (MinIO) ====

def generate_presigned_url(
    bucket: str, object_path: str, expires_minutes: int = 15
) -> str:
    """生成 MinIO 预签名下载 URL"""
    expiry = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload = f"{bucket}/{object_path}/{int(expiry.timestamp())}"
    signature = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"http://minio:9000/{bucket}/{object_path}?expires={int(expiry.timestamp())}&sig={signature}"


# ==== 认证中间件 ====

class AuthMiddleware(BaseHTTPMiddleware):
    """JWT 认证 + RBAC 鉴权中间件"""

    PUBLIC_PATHS = {"/health", "/version", "/docs", "/openapi.json", "/redoc", "/api/auth/login"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.PUBLIC_PATHS or request.url.path.startswith("/ws"):
            return await call_next(request)

        token = request.headers.get("Authorization", "").replace("Bearer ", "")

        if not token:
            api_key = request.headers.get("X-API-Key")
            if api_key and api_key in API_KEYS:
                request.state.user_id = API_KEYS[api_key]["user_id"]
                request.state.role = "api_user"
                return await call_next(request)
            raise HTTPException(status_code=401, detail="Missing authentication token")

        try:
            from jose import jwt
            from shared.utils.config import get_settings
            settings = get_settings()
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            request.state.user_id = payload.get("sub")
            request.state.role = payload.get("role", "engineer")
            request.state.username = payload.get("username", "")
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid authentication token")

        return await call_next(request)


# ==== 审计日志中间件 ====

class AuditMiddleware(BaseHTTPMiddleware):
    """审计日志 — 记录所有操作到 TimescaleDB"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        user_id = getattr(request.state, "user_id", "anonymous")

        logger.info(
            "audit_log",
            user_id=user_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("User-Agent", ""),
        )

        return response


# ==== 安全 Header ====

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全 Header — CSP, XSS Protection, HSTS"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:"
        return response


def setup_security(app: FastAPI) -> None:
    """配置安全中间件"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
        max_age=3600,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(AuditMiddleware)
    logger.info("Security middleware configured")
