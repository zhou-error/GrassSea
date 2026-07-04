"""系统配置管理 API — 允许用户在 Web 中修改关键配置"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/config", tags=["config"])

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


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
    """读取 .env 文件"""
    envs: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                envs[k.strip()] = v.strip().strip('"').strip("'")
    # 兜底：从 os.environ 读取
    for k in os.environ:
        if k not in envs:
            envs[k] = os.environ[k]
    return envs


def _write_env(envs: dict[str, str]) -> None:
    """写回 .env 文件，保留注释和空行"""
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
    # 追加新增的 key
    for k, v in envs.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}\n")
    ENV_FILE.write_text("".join(new_lines), encoding="utf-8")


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
async def update_config(request: ConfigUpdateRequest):
    """更新单个配置项"""
    # 找到配置项定义
    item = next((i for i in CONFIG_SCHEMA if i["key"] == request.key), None)
    if not item:
        raise HTTPException(status_code=400, detail=f"未知配置项: {request.key}")

    envs = _read_env()
    old_value = envs.get(request.key, "")

    # 如果传的是脱敏值且没变，跳过更新
    if item.get("sensitive") and request.value.count("*") > 4:
        raise HTTPException(status_code=400, detail="请勿提交脱敏后的值，请重新输入完整 Key")

    envs[request.key] = request.value
    _write_env(envs)
    os.environ[request.key] = request.value

    logger.info("Config updated", key=request.key, category=item["category"])

    return {"status": "ok", "key": request.key, "message": f"{item['label']} 已更新，重启服务后生效"}


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
