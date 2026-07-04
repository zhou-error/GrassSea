"""重排序模块

使用 Cross-encoder 模型对检索结果精排。
默认使用 bge-reranker-v2-m3。

从 Top-20 候选重排序，返回 Top-5。
"""

from __future__ import annotations

from shared.utils.logging import get_logger

logger = get_logger(__name__)


class Reranker:
    """Cross-encoder 重排序器"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model_name = model_name
        self._model = None
        self._tokenizer = None

    async def _ensure_model(self) -> None:
        """延迟加载模型"""
        if self._model is not None:
            return
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self._model.eval()
            logger.info("Reranker model loaded", model=self.model_name)
        except ImportError:
            logger.warning(
                "transformers not installed, using score-based fallback for reranking"
            )
        except Exception as e:
            logger.warning("Failed to load reranker model, using fallback", error=str(e))

    async def rerank(
        self,
        query: str,
        candidates: list,
        top_k: int = 5,
    ) -> list:
        """对候选结果重排序

        Args:
            query: 用户查询
            candidates: 候选 SearchResult 列表
            top_k: 返回 Top-K 结果

        Returns:
            重排序后的结果列表
        """
        if not candidates:
            return []

        if len(candidates) <= top_k:
            return candidates

        # 尝试使用 cross-encoder
        try:
            return await self._cross_encoder_rerank(query, candidates, top_k)
        except Exception as e:
            logger.warning("Cross-encoder rerank failed, using score-based fallback", error=str(e))
            return self._score_based_rerank(candidates, top_k)

    async def _cross_encoder_rerank(
        self,
        query: str,
        candidates: list,
        top_k: int,
    ) -> list:
        """使用 Cross-encoder 重排序"""
        await self._ensure_model()

        if self._model is None or self._tokenizer is None:
            return self._score_based_rerank(candidates, top_k)

        import torch

        pairs = [[query, c.text] for c in candidates]

        scores = []
        with torch.no_grad():
            for pair in pairs:
                inputs = self._tokenizer(
                    pair[0], pair[1],
                    max_length=512,
                    truncation=True,
                    padding=True,
                    return_tensors="pt",
                )
                outputs = self._model(**inputs)
                score = outputs.logits.squeeze().item()
                scores.append(score)

        # 按重排序分数更新
        for candidate, score in zip(candidates, scores):
            candidate.score = score

        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates[:top_k]

    def _score_based_rerank(
        self,
        candidates: list,
        top_k: int,
    ) -> list:
        """基于原始分数的简单重排序"""
        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates[:top_k]
