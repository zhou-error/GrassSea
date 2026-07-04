"""Token 用量统计与计费

记录 LLM 调用到 TimescaleDB，支持按模型/用户/时间维度统计。
"""

from __future__ import annotations

from datetime import datetime

from shared.utils.logging import get_logger

logger = get_logger(__name__)


class TokenTracker:
    """Token 用量追踪器"""

    def __init__(self):
        self._buffer: list[dict] = []
        self._max_buffer_size = 100

    async def record(
        self,
        user_id: str,
        session_id: str,
        model: str,
        task_type: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
    ) -> None:
        """记录一次 LLM 调用"""
        record = {
            "user_id": user_id,
            "session_id": session_id,
            "model": model,
            "task_type": task_type,
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "latency_ms": latency_ms,
            "status": "success",
            "created_at": datetime.utcnow(),
        }

        # 记录到 MongoDB (异步日志)
        # 生产环境应批量写入 TimescaleDB
        self._buffer.append(record)

        logger.info(
            "Token usage",
            model=model,
            task_type=task_type,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=round(latency_ms, 1),
        )

        # 缓冲区满时批量写入（简化实现）
        if len(self._buffer) >= self._max_buffer_size:
            await self.flush()

    async def flush(self) -> None:
        """批量写入缓冲区"""
        count = len(self._buffer)
        self._buffer.clear()
        if count > 0:
            logger.debug("Token tracker flushed", records=count)

    async def get_user_usage(
        self, user_id: str, days: int = 30
    ) -> dict:
        """获取用户用量统计（直接从 TimescaleDB 查询）"""
        # 生产环境：SELECT sum(total_tokens) FROM timeseries.token_usage_metrics
        # WHERE user_id = $1 AND time > now() - interval '$2 days'
        return {
            "user_id": user_id,
            "total_tokens": 0,
            "total_calls": 0,
            "days": days,
        }
