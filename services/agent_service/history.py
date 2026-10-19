"""会话历史（进程内 + 磁盘持久化）

桌面形态是单进程，服务器形态是单实例 agent_service，进程内字典足够；
但**进程重启会清空内存**——用户说「继续」时若历史没了，模型只能凭空发挥。
因此落盘到 <DATA_DIR>/sessions/<hash>.json，重启后自动恢复。

容量策略：每个 session 最多保留 MAX_TURNS 条消息；
单条上限 MAX_CHARS 字符；空闲超过 TTL 秒的文件在读取时惰性清理。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from shared.utils.logging import get_logger

logger = get_logger(__name__)

#: 每个会话最多保留的消息条数（约 6 轮问答）
MAX_TURNS = 12
#: 单条消息最大字符数
MAX_CHARS = 8000
#: 会话空闲过期时间（秒）
TTL_SECONDS = 3600


def _sessions_dir() -> Path:
    """会话文件目录：<DATA_DIR>/sessions（默认 <项目根>/data/sessions）"""
    try:
        from shared.utils.config import get_settings

        s = get_settings()
        data_dir = (getattr(s, "DATA_DIR", "") or "").strip()
        base = Path(data_dir) if data_dir else (s.PROJECT_ROOT / "data")
    except Exception:  # noqa: BLE001
        base = Path(__file__).resolve().parent.parent.parent / "data"
    return base / "sessions"


class ConversationHistory:
    """按 session_id 保存最近若干轮对话（内存 + 磁盘）"""

    def __init__(self, max_turns: int = MAX_TURNS, ttl: int = TTL_SECONDS) -> None:
        self._data: dict[str, list[dict]] = {}
        self._touched: dict[str, float] = {}
        self.max_turns = max_turns
        self.ttl = ttl

    # ---------- 磁盘 ----------

    @staticmethod
    def _path_for(session_id: str) -> Path:
        # 用哈希做文件名，避免 session_id 里的特殊字符影响路径
        digest = hashlib.sha1(session_id.encode("utf-8")).hexdigest()[:24]
        return _sessions_dir() / f"{digest}.json"

    def _load_from_disk(self, session_id: str) -> list[dict]:
        path = self._path_for(session_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("会话历史读取失败，按空处理", error=str(exc))
            return []
        if payload.get("session_id") != session_id:
            return []
        age = time.time() - float(payload.get("updated_at") or 0)
        if age > self.ttl:
            return []
        messages = payload.get("messages")
        return messages if isinstance(messages, list) else []

    def _save_to_disk(self, session_id: str, messages: list[dict]) -> None:
        try:
            path = self._path_for(session_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "session_id": session_id,
                        "updated_at": time.time(),
                        "messages": messages,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            # 落盘失败不影响对话本身
            logger.warning("会话历史落盘失败", error=str(exc))

    # ---------- 公开 ----------

    def _purge(self) -> None:
        now = time.time()
        expired = [k for k, ts in self._touched.items() if now - ts > self.ttl]
        for key in expired:
            self._data.pop(key, None)
            self._touched.pop(key, None)
        if expired:
            logger.debug("会话历史已过期清理", count=len(expired))

    def get(self, session_id: str) -> list[dict]:
        """取该会话的历史消息（副本）"""
        if not session_id:
            return []
        self._purge()
        if session_id not in self._data:
            restored = self._load_from_disk(session_id)
            if restored:
                logger.info("会话历史已从磁盘恢复", messages=len(restored))
            self._data[session_id] = restored
            self._touched[session_id] = time.time()
        return [dict(m) for m in self._data.get(session_id, [])]

    def append(self, session_id: str, role: str, content: str) -> None:
        """追加一条消息，按 max_turns 截断，并落盘"""
        if not session_id or not content:
            return
        text = content if len(content) <= MAX_CHARS else content[:MAX_CHARS] + "…（已截断）"
        bucket = self._data.setdefault(session_id, [])
        bucket.append({"role": role, "content": text})
        if len(bucket) > self.max_turns:
            del bucket[: len(bucket) - self.max_turns]
        self._touched[session_id] = time.time()
        self._save_to_disk(session_id, bucket)

    def clear(self, session_id: str) -> None:
        self._data.pop(session_id, None)
        self._touched.pop(session_id, None)
        try:
            self._path_for(session_id).unlink(missing_ok=True)
        except OSError:
            pass

    def stats(self) -> dict:
        return {"sessions": len(self._data), "messages": sum(len(v) for v in self._data.values())}


#: 全局单例
history = ConversationHistory()
