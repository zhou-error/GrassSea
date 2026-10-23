"""会话存储端口

对应实现：services/agent_service/history.py（内存 + <DATA_DIR>/sessions/*.json）。
未来换 Redis/Postgres 时实现同一端口。

背景：曾经的历史实现是**纯内存**，进程重启后"继续"丢掉上下文，
模型于是凭空发挥（实测突然讲起 LangChain 教程）。该行为已固化为契约测试。
"""

from __future__ import annotations

from typing import Protocol, TypedDict, runtime_checkable


class HistoryMessage(TypedDict):
    role: str      # "user" | "assistant"
    content: str


@runtime_checkable
class ConversationStorePort(Protocol):
    """会话历史契约

    实现方必须保证：
    1. 同一 session_id 的消息**跨进程重启**仍可读回（落盘或外部存储）；
    2. 不同 session_id 互不串；
    3. 超出容量时丢最旧的消息，而不是整段清空；
    4. 单条内容有长度上限（截断并标记），避免一条超长历史挤掉后续上下文；
    5. 空闲超过 TTL 的会话可被清理。
    """

    def get(self, session_id: str) -> list[HistoryMessage]:
        ...

    def append(self, session_id: str, role: str, content: str) -> None:
        ...

    def clear(self, session_id: str) -> None:
        ...
