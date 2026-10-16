"""统一的文本向量化模块

后端由 EMBEDDING_PROVIDER 选择：
  - auto   : 依次尝试 local → openai → hash（推荐）
  - local  : fastembed 本地 ONNX 模型，离线可用、无需 API Key（个人使用推荐）
  - openai : 任何 OpenAI 兼容的 /embeddings 接口（需要 API Key）
  - hash   : 字面量哈希向量，**不具备语义理解**，仅作最后兜底并在日志中显著告警

⚠️ 文档入库与查询检索必须共用本模块。此前两处各自实现，
   导致同一份文本在入库与检索时得到不同向量，稠密检索完全失效。
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import os
import re
from pathlib import Path

from shared.utils.config import Settings, is_usable_key
from shared.utils.logging import get_logger

logger = get_logger(__name__)

# 常见本地模型维度，避免 EMBEDDING_DIM 与实际模型不匹配
LOCAL_MODEL_DIMS: dict[str, int] = {
    "BAAI/bge-small-zh-v1.5": 512,
    "BAAI/bge-base-zh-v1.5": 768,
    "BAAI/bge-large-zh-v1.5": 1024,
    "BAAI/bge-small-en-v1.5": 384,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-large-en-v1.5": 1024,
}


class BaseEmbedder:
    """向量化后端基类"""

    name: str = "base"
    semantic: bool = True

    def __init__(self, dim: int) -> None:
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    async def embed_one(self, text: str) -> list[float]:
        vectors = await self.embed([text])
        return vectors[0]


class LocalEmbedder(BaseEmbedder):
    """本地 ONNX 模型（fastembed），CPU 推理，无需联网与 API Key"""

    name = "local"
    semantic = True

    def __init__(self, settings: Settings) -> None:
        # 模型缓存必须落在可写目录：沙箱/只读临时目录会导致下载失败
        cache_dir = settings.LOCAL_EMBEDDING_CACHE or str(
            Path(settings.PROJECT_ROOT) / "docker-data" / "fastembed"
        )
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        if settings.HF_ENDPOINT:
            os.environ.setdefault("HF_ENDPOINT", settings.HF_ENDPOINT)
        os.environ.setdefault("HF_HOME", str(Path(cache_dir).parent / "hf"))
        # hf-mirror 不代理 Xet 存储协议，启用会 401；官方站也可安全禁用
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

        from fastembed import TextEmbedding

        self.model_name = settings.LOCAL_EMBEDDING_MODEL
        self.cache_dir = cache_dir
        self._model = TextEmbedding(model_name=self.model_name, cache_dir=cache_dir)
        # 以实际输出维度为准，避免与配置不一致
        self.dim = len(next(iter(self._model.embed(["dimension probe"]))))
        logger.info(
            "Local embedding model loaded",
            model=self.model_name,
            dim=self.dim,
            cache_dir=cache_dir,
            declared_dim=LOCAL_MODEL_DIMS.get(self.model_name),
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        def _run() -> list[list[float]]:
            return [[float(x) for x in vec] for vec in self._model.embed(texts)]

        return await asyncio.to_thread(_run)


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI 兼容的 /embeddings 接口"""

    name = "openai"
    semantic = True

    def __init__(self, settings: Settings) -> None:
        import httpx  # noqa: F401

        self._settings = settings
        self.model = settings.EMBEDDING_MODEL
        self.dim = settings.EMBEDDING_DIM
        self._base_url = settings.OPENAI_BASE_URL.rstrip("/")
        self._api_key = settings.OPENAI_API_KEY

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self.model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]


class HashEmbedder(BaseEmbedder):
    """字面量哈希向量（词 + 字二元组 hashing trick，L2 归一化）

    ⚠️ 只具备**字面重叠**匹配能力，不具备语义理解。
    仅用于没有其它后端时的兜底，保证检索链路不崩。
    """

    name = "hash-lexical"
    semantic = False

    _TOKEN_RE = re.compile(r"[a-zA-Z]+|\d+|[\u4e00-\u9fff]")

    def __init__(self, dim: int) -> None:
        self.dim = dim

    @classmethod
    def _features(cls, text: str) -> list[str]:
        tokens = cls._TOKEN_RE.findall(text.lower())
        features = list(tokens)
        # 中文二元组，提升中文召回
        cjk = [t for t in tokens if len(t) == 1 and "\u4e00" <= t <= "\u9fff"]
        features += [cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1)]
        return features

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for feature in self._features(text):
                h = int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")
                vec[h % self.dim] += 1.0
            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0:
                vec = [v / norm for v in vec]
            vectors.append(vec)
        return vectors


_embedder: BaseEmbedder | None = None


def _build(settings: Settings) -> BaseEmbedder:
    provider = (getattr(settings, "EMBEDDING_PROVIDER", "auto") or "auto").strip().lower()
    failures: list[str] = []

    if provider in ("auto", "local"):
        try:
            return LocalEmbedder(settings)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"local({settings.LOCAL_EMBEDDING_MODEL}): {exc}")
            if provider == "local":
                raise

    if provider in ("auto", "openai"):
        # 注意：.env.example 的 "your-openai-api-key" 是非空字符串，
        # 直接判真会误选 openai 后端并让所有检索静默失败。
        if is_usable_key(settings.OPENAI_API_KEY):
            return OpenAIEmbedder(settings)
        failures.append("openai: OPENAI_API_KEY 未配置或为占位符")
        if provider == "openai":
            raise RuntimeError("EMBEDDING_PROVIDER=openai 但未配置 OPENAI_API_KEY")

    if provider == "hash":
        return HashEmbedder(settings.EMBEDDING_DIM)

    logger.warning(
        "所有语义向量后端均不可用，回退到 hash 字面量向量（检索质量会很差）",
        attempts=failures,
    )
    return HashEmbedder(settings.EMBEDDING_DIM)


def get_embedder(settings: Settings) -> BaseEmbedder:
    """获取全局向量化后端（进程内单例）"""
    global _embedder
    if _embedder is None:
        _embedder = _build(settings)
        logger.info(
            "Embedding backend ready",
            backend=_embedder.name,
            dim=_embedder.dim,
            semantic=_embedder.semantic,
        )
        if not _embedder.semantic:
            logger.warning("当前向量后端不具备语义能力，RAG 检索结果仅供参考")
    return _embedder


def reset_embedder() -> None:
    """清空缓存（配置热更新后调用）"""
    global _embedder
    _embedder = None
