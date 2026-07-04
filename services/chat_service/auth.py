"""认证服务 — JWT 登录/注册"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from jose import jwt

from shared.utils.config import get_settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str | None = None
    display_name: str | None = None


class AuthResponse(BaseModel):
    token: str
    user: dict


def hash_password(password: str) -> str:
    """SHA256 密码哈希 (开发环境)"""
    salt = settings.APP_SECRET_KEY
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    return hmac.compare_digest(hash_password(password), hashed)


# 开发环境默认用户
_dev_users: dict[str, dict] = {
    "admin": {
        "id": "admin-001",
        "username": "admin",
        "hashed_password": hash_password("admin123"),
        "display_name": "系统管理员",
        "email": "admin@grasssea.local",
        "role": "admin",
    },
    "engineer": {
        "id": "eng-001",
        "username": "engineer",
        "hashed_password": hash_password("engineer123"),
        "display_name": "船舶工程师",
        "email": "engineer@grasssea.local",
        "role": "engineer",
    },
    "guest": {
        "id": "guest-001",
        "username": "guest",
        "hashed_password": hash_password("guest123"),
        "display_name": "访客",
        "email": "guest@grasssea.local",
        "role": "guest",
    },
}


def create_token(user_id: str, username: str, role: str) -> str:
    """生成 JWT Token"""
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """用户登录"""
    user = _dev_users.get(request.username)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(user["id"], user["username"], user["role"])
    logger.info("User logged in", username=request.username, role=user["role"])

    return AuthResponse(
        token=token,
        user={
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "email": user["email"],
            "roles": [user["role"]],
        },
    )


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """用户注册（开发环境）"""
    if request.username in _dev_users:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = {
        "id": f"user-{len(_dev_users) + 1}",
        "username": request.username,
        "hashed_password": hash_password(request.password),
        "display_name": request.display_name or request.username,
        "email": request.email or f"{request.username}@grasssea.local",
        "role": "engineer",
    }
    _dev_users[request.username] = user

    token = create_token(user["id"], user["username"], user["role"])
    logger.info("User registered", username=request.username)

    return AuthResponse(
        token=token,
        user={
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "email": user["email"],
            "roles": [user["role"]],
        },
    )
