"""API Key 加密存储模块

使用 Fernet (AES-128-CBC + HMAC) 对称加密保护敏感配置。
- 密钥文件 (.grasssea_key): 首次运行自动生成，权限 0o600
- 加密数据 (.grasssea_secrets): API Key 密文存储
- .env 文件永不包含真实 Key，只有占位符

安全特性:
- 明文 Key 永不落盘
- 密钥和数据分离存储
- 密文离开本机无法解密（需同时持有 key.bin）
- .gitignore 保护，不会误提交
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet

from shared.utils.logging import get_logger

logger = get_logger(__name__)

# 加密文件存储目录
# Docker 中挂载到 ./docker-data/secrets → /app/.secrets
# 本地开发直接放在项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_secrets_dir() -> Path:
    """确定密钥/密文存放目录。

    1. 显式设置 SECRETS_DIR（Docker / 自定义部署）时优先；
    2. 本地开发沿用 docker-compose 挂载的 docker-data/secrets；
    3. 都不存在时退回到项目根目录。
    """
    env_dir = os.getenv("SECRETS_DIR")
    if env_dir:
        return Path(env_dir)
    mounted = _PROJECT_ROOT / "docker-data" / "secrets"
    if mounted.is_dir():
        return mounted
    return _PROJECT_ROOT


_SECRETS_DIR = _resolve_secrets_dir()
KEY_FILE = _SECRETS_DIR / ".grasssea_key"
SECRETS_FILE = _SECRETS_DIR / ".grasssea_secrets"

# 确保目录存在
_SECRETS_DIR.mkdir(parents=True, exist_ok=True)

# 需要加密存储的敏感 key（这些 key 永不写入 .env）
SENSITIVE_KEYS = {
    "DEEPSEEK_API_KEY",
    "CLAUDE_API_KEY",
    "OPENAI_API_KEY",
    "BRAVE_SEARCH_API_KEY",
    "BING_SEARCH_API_KEY",
}


def _get_or_create_key() -> bytes:
    """获取或创建 Fernet 加密密钥。

    首次运行时生成随机密钥并保存到 .grasssea_key。
    文件权限设为仅当前用户可读写（Unix: 0o600, Windows: 受限访问）。
    """
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()

    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)

    # 设置文件权限（仅 owner 可读写）
    try:
        os.chmod(KEY_FILE, 0o600)
    except Exception:
        pass  # Windows 上 chmod 无意义，跳过

    logger.info("Encryption key generated", path=str(KEY_FILE))
    return key


def _get_fernet() -> Fernet:
    """获取 Fernet 加密实例"""
    return Fernet(_get_or_create_key())


def load_secrets() -> dict[str, str]:
    """解密并加载所有敏感配置。

    Returns:
        dict: {key: plaintext_value, ...}，如 {"DEEPSEEK_API_KEY": "sk-xxx"}
        文件不存在或解密失败时返回空 dict
    """
    if not SECRETS_FILE.exists():
        return {}

    try:
        fernet = _get_fernet()
        ciphertext = SECRETS_FILE.read_bytes()
        plaintext = fernet.decrypt(ciphertext)
        secrets = json.loads(plaintext)
        logger.info("Secrets loaded", count=len(secrets))
        return secrets
    except Exception as e:
        logger.error("Failed to decrypt secrets", error=str(e))
        return {}


def save_secrets(secrets: dict[str, str]) -> None:
    """加密并保存敏感配置。

    Args:
        secrets: {key: plaintext_value, ...}，只保存 SENSITIVE_KEYS 中的 key
    """
    # 只保存敏感 key
    to_save = {k: v for k, v in secrets.items() if k in SENSITIVE_KEYS}
    if not to_save:
        return

    fernet = _get_fernet()
    plaintext = json.dumps(to_save, ensure_ascii=False)
    ciphertext = fernet.encrypt(plaintext.encode("utf-8"))
    SECRETS_FILE.write_bytes(ciphertext)

    # 设置文件权限
    try:
        os.chmod(SECRETS_FILE, 0o600)
    except Exception:
        pass

    logger.info("Secrets saved", keys=list(to_save.keys()))


def update_secret(key: str, value: str) -> None:
    """更新单个敏感配置（合并保存）。

    Args:
        key: 配置项名称
        value: 明文值
    """
    current = load_secrets()
    current[key] = value
    save_secrets(current)


def is_sensitive_key(key: str) -> bool:
    """判断是否为需要加密存储的敏感 key"""
    return key in SENSITIVE_KEYS
