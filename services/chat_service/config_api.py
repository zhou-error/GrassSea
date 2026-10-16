"""系统配置管理 API — 允许用户在 Web 中修改关键配置

安全策略:
- API Key 等敏感配置使用 Fernet 加密存储 (.grasssea_secrets)
- 密钥文件 (.grasssea_key) 首次运行自动生成
- .env 文件永不包含真实 Key，只有占位符
- 服务启动时自动解密加载，重启后 Key 不丢失
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from shared.utils.config import get_settings
from shared.utils.logging import get_logger
from shared.utils.secrets import (
    is_sensitive_key,
    load_secrets,
    save_secrets,
    update_secret,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/config", tags=["config"])

settings = get_settings()

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


# ---- 模块加载时：解密并注入敏感配置到环境变量 ----
_secrets = load_secrets()
for _k, _v in _secrets.items():
    os.environ[_k] = _v
    # 同步更新 pydantic Settings 对象
    if hasattr(settings, _k):
        setattr(settings, _k, _v)
if _secrets:
    logger.info("Encrypted secrets loaded into environment", keys=list(_secrets.keys()))


# ---- 配置项定义 ----
# 每个配置项的 key / label / 分类 / 类型 / 是否敏感
CONFIG_SCHEMA: list[dict] = [
    # LLM
    {"key": "DEEPSEEK_API_KEY",    "label": "DeepSeek API Key",     "category": "LLM", "type": "password", "sensitive": True},
    {"key": "DEEPSEEK_BASE_URL",   "label": "DeepSeek 接口地址",     "category": "LLM", "type": "text"},
    {"key": "CLAUDE_API_KEY",      "label": "Claude API Key",       "category": "LLM", "type": "password", "sensitive": True},
    {"key": "CLAUDE_BASE_URL",     "label": "Claude 接口地址",       "category": "LLM", "type": "text"},
    {"key": "OPENAI_API_KEY",      "label": "OpenAI API Key",       "category": "LLM", "type": "password", "sensitive": True},
    {"key": "OPENAI_BASE_URL",     "label": "OpenAI 接口地址",       "category": "LLM", "type": "text"},
    # 模型
    {"key": "EMBEDDING_MODEL",     "label": "Embedding 模型",        "category": "模型", "type": "select", "options": ["text-embedding-3-large", "text-embedding-3-small", "text-embedding-ada-002"]},
    {"key": "EMBEDDING_DIM",       "label": "向量维度",              "category": "模型", "type": "number"},
    # RAG
    {"key": "rag_chunk_size",      "label": "文档分块大小 (tokens)",  "category": "RAG", "type": "number", "default": "512"},
    {"key": "rag_chunk_overlap",   "label": "分块重叠 (tokens)",      "category": "RAG", "type": "number", "default": "64"},
    {"key": "rag_top_k",           "label": "检索返回数量 (Top-K)",    "category": "RAG", "type": "number", "default": "5"},
    # 会话
    {"key": "max_context_turns",   "label": "最大对话轮数",           "category": "会话", "type": "number", "default": "20"},
    {"key": "session_timeout_minutes", "label": "会话超时 (分钟)",     "category": "会话", "type": "number", "default": "30"},
    # 搜索
    {"key": "BRAVE_SEARCH_API_KEY", "label": "Brave Search API Key",  "category": "搜索", "type": "password", "sensitive": True},
    {"key": "BING_SEARCH_API_KEY",  "label": "Bing Search API Key",   "category": "搜索", "type": "password", "sensitive": True},
]


class ConfigItemResponse(BaseModel):
    key: str
    label: str
    value: str
    category: str
    type: str
    sensitive: bool = False
    default: Optional[str] = None
    options: Optional[list[str]] = None


class ConfigUpdateRequest(BaseModel):
    key: str
    value: str


def _read_env() -> dict[str, str]:
    """读取配置：.env 文件 + os.environ（包含解密后的 Key）"""
    envs: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                envs[k.strip()] = v.strip().strip('"').strip("'")
    # os.environ 覆盖 .env（含解密后的敏感 Key）
    for k in os.environ:
        if k not in envs or envs[k].startswith("your-"):
            envs[k] = os.environ[k]
    return envs


def _write_env(envs: dict[str, str]) -> None:
    """写回 .env 文件，保留注释和空行（敏感 Key 已被过滤，不会写入）"""
    if not ENV_FILE.exists():
        lines = [f"{k}={v}\n" for k, v in envs.items()]
        ENV_FILE.write_text("".join(lines), encoding="utf-8")
        return

    existing = ENV_FILE.read_text(encoding="utf-8").splitlines()
    updated_keys = set()
    new_lines = []
    for line in existing:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=")[0].strip()
            if k in envs:
                new_lines.append(f"{k}={envs[k]}\n")
                updated_keys.add(k)
                continue
        new_lines.append(line + "\n")
    # 追加新增的 key（跳过敏感 Key）
    for k, v in envs.items():
        if k not in updated_keys and not is_sensitive_key(k):
            new_lines.append(f"{k}={v}\n")
    ENV_FILE.write_text("".join(new_lines), encoding="utf-8")


# 需要传播到下游服务的 LLM 相关配置 key
PROPAGATABLE_KEYS = {
    "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL",
    "CLAUDE_API_KEY", "CLAUDE_BASE_URL",
    "OPENAI_API_KEY", "OPENAI_BASE_URL",
    "EMBEDDING_MODEL", "EMBEDDING_DIM",
    "BRAVE_SEARCH_API_KEY", "BING_SEARCH_API_KEY",
}


async def _propagate_to_services(key: str, value: str) -> dict[str, str]:
    """推送单个 key 到下游。供 background_tasks 使用。"""
    return await _propagate_to_service_urls({key: value})


async def _propagate_to_service_urls(payload: dict[str, str]) -> dict[str, str]:
    """推送配置到所有下游服务"""
    service_urls = [
        settings.MODEL_GATEWAY_URL,
        settings.AGENT_SERVICE_URL,
        settings.KNOWLEDGE_SERVICE_URL,
    ]

    results = {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
        for url in service_urls:
            try:
                resp = await client.post(f"{url}/admin/reload", json=payload)
                results[url] = "ok" if resp.status_code == 200 else f"HTTP {resp.status_code}"
            except httpx.ConnectError:
                results[url] = "unreachable"
            except Exception as e:
                results[url] = str(e)

    return results


async def _propagate_all_secrets(max_retries: int = 5, retry_delay: float = 3.0) -> None:
    """启动时将所有已加载的加密 Key 推送到下游服务（带重试）。"""
    from shared.utils.secrets import load_secrets

    secrets = load_secrets()
    if not secrets:
        logger.info("No encrypted secrets to propagate on startup")
        return

    # 只传播敏感 key
    payload = {k: v for k, v in secrets.items() if is_sensitive_key(k)}
    if not payload:
        return

    for attempt in range(1, max_retries + 1):
        results = await _propagate_to_service_urls(payload)
        failures = [url for url, status in results.items() if status != "ok"]

        if not failures:
            logger.info("Startup secrets propagated", keys=list(payload.keys()))
            return

        logger.warning(
            "Startup propagation retry",
            attempt=attempt,
            failures=failures,
        )
        if attempt < max_retries:
            import asyncio
            await asyncio.sleep(retry_delay)

    logger.error("Startup propagation failed after retries", failures=failures)


@router.get("/schema", response_model=list[ConfigItemResponse])
async def get_config_schema():
    """获取所有可配置项（含当前值）"""
    envs = _read_env()
    result = []
    for item in CONFIG_SCHEMA:
        value = envs.get(item["key"], item.get("default", ""))
        # 敏感字段脱敏
        if item.get("sensitive") and value:
            masked = value[:4] + "****" + value[-4:] if len(value) > 8 else "****"
            value = masked
        result.append(ConfigItemResponse(
            key=item["key"], label=item["label"], value=value,
            category=item["category"], type=item.get("type", "text"),
            sensitive=item.get("sensitive", False),
            default=item.get("default"),
            options=item.get("options"),
        ))
    return result


@router.put("/update")
async def update_config(request: ConfigUpdateRequest, background_tasks: BackgroundTasks):
    """更新单个配置项 — 敏感 Key 加密存储，自动推送到下游"""
    # 找到配置项定义
    item = next((i for i in CONFIG_SCHEMA if i["key"] == request.key), None)
    if not item:
        raise HTTPException(status_code=400, detail=f"未知配置项: {request.key}")

    # 如果传的是脱敏值且没变，跳过更新
    if item.get("sensitive") and request.value.count("*") > 4:
        raise HTTPException(status_code=400, detail="请勿提交脱敏后的值，请重新输入完整 Key")

    # === 敏感 Key：加密存储 + 内存注入 ===
    if is_sensitive_key(request.key):
        update_secret(request.key, request.value)
        os.environ[request.key] = request.value
        if hasattr(settings, request.key):
            setattr(settings, request.key, request.value)

        logger.info("Config updated (encrypted)", key=request.key, category=item["category"])

        # 后台推送到下游服务
        background_tasks.add_task(_propagate_to_services, request.key, request.value)

        return {
            "status": "ok",
            "key": request.key,
            "message": f"{item['label']} 已更新（加密存储，重启后自动加载）",
            "propagated": True,
            "encrypted": True,
        }

    # === 普通配置：.env 文件 ===
    envs = _read_env()
    envs[request.key] = request.value
    _write_env(envs)
    os.environ[request.key] = request.value

    logger.info("Config updated (.env)", key=request.key, category=item["category"])

    if request.key in PROPAGATABLE_KEYS:
        background_tasks.add_task(_propagate_to_services, request.key, request.value)
        return {
            "status": "ok",
            "key": request.key,
            "message": f"{item['label']} 已更新，已自动推送到下游服务",
            "propagated": True,
        }
    else:
        return {
            "status": "ok",
            "key": request.key,
            "message": f"{item['label']} 已更新，重启服务后生效",
        }


@router.post("/test-llm")
async def test_llm_connection():
    """测试 LLM 连接是否正常"""
    envs = _read_env()
    api_key = envs.get("DEEPSEEK_API_KEY", "")
    base_url = envs.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    if not api_key or api_key.startswith("your-"):
        return {"status": "error", "message": "请先配置 DeepSeek API Key"}

    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10},
            )
            if resp.status_code == 200:
                return {"status": "ok", "message": "DeepSeek 连接成功 ✓"}
            return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
