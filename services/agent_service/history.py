"""会话历史（进程内）

桌面形态是单进程，服务器形态是单实例 agent_service，因此用进程内字典足够；
不引入 Redis 依赖，符合「桌面零中间件」的定位。

容量策略：每个 session 最多保留 MAX_TURNS 条消息（一问一答各算一条），
超出后从最旧的丢弃；空闲超过 TTL 秒自动清理，避免长期运行内存增长。
"""

from __future__ import annotations

import time

from shared.utils.logging import get_logger

logger = get_logger(__name__)

#: 每个会话最多保留的消息条数（约 6 轮问答）
MAX_TURNS = 12
#: 单条消息最大字符数，超出截断（防止一条超长历史挤掉后续上下文）
MAX_CHARS = 8000
#: 会话空闲过期时间（秒）
TTL_SECONDS = 3600


class ConversationHistory:
    """按 session_id 保存最近若干轮对话"""

    def __init__(self, max_turns: int = MAX_TURNS, ttl: int = TTL_SECONDS) -> None:
        self._data: dict[str, list[dict]] = {}
        self._touched: dict[str, float] = {}
        self.max_turns = max_turns
        self.ttl = ttl

    def _purge(self) -> None:
        now = time.time()
        expired = [k for k, ts in self._touched.items() if now - ts > self.ttl]
        for key in expired:
            self._data.pop(key, None)
            self._touched.pop(key, None)
        if expired:
            logger.debug("会话历史已过期清理", count=len(expired))

    def get(self, session_id: str) -> list[dict]:
        """取该会话的历史消息（副本，调用方可安全修改）"""
        if not session_id:
            return []
        self._purge()
        return [dict(m) for m in self._data.get(session_id, [])]

    def append(self, session_id: str, role: str, content: str) -> None:
        """追加一条消息，按 max_turns 截断"""
        if not session_id or not content:
            return
        text = content if len(content) <= MAX_CHARS else content[:MAX_CHARS] + "…（已截断）"
        bucket = self._data.setdefault(session_id, [])
        bucket.append({"role": role, "content": text})
        if len(bucket) > self.max_turns:
            del bucket[: len(bucket) - self.max_turns]
        self._touched[session_id] = time.time()

    def clear(self, session_id: str) -> None:
        self._data.pop(session_id, None)
        self._touched.pop(session_id, None)

    def stats(self) -> dict:
        return {"sessions": len(self._data), "messages": sum(len(v) for v in self._data.values())}


#: 全局单例
history = ConversationHistory()
