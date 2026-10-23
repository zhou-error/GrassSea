"""会话存储端口契约测试

背景：历史曾经只存内存，进程重启后用户说「继续」时模型丢失上下文，
凭空讲起了无关话题。以下断言把该行为钉死。
"""

from __future__ import annotations

import tempfile
from pathlib import Path


def _new_history(data_dir: str):
    from shared.utils.config import get_settings

    get_settings.cache_clear()
    from services.agent_service.history import ConversationHistory

    return ConversationHistory()


def test_survives_process_restart(apply_settings):
    """重启（新实例）后必须能读回历史 —— 这是「继续」能工作的前提"""
    data_dir = tempfile.mkdtemp(prefix="hist_")
    apply_settings(DATA_DIR=data_dir)

    first = _new_history(data_dir)
    first.append("s1", "user", "建一个船体外壳")
    first.append("s1", "assistant", "已放样 11 个断面")

    # 模拟进程重启：全新实例，内存为空
    second = _new_history(data_dir)
    restored = second.get("s1")
    assert [m["content"] for m in restored] == ["建一个船体外壳", "已放样 11 个断面"]


def test_sessions_isolated(apply_settings):
    data_dir = tempfile.mkdtemp(prefix="hist_")
    apply_settings(DATA_DIR=data_dir)
    store = _new_history(data_dir)
    store.append("a", "user", "A 的内容")
    store.append("b", "user", "B 的内容")
    assert [m["content"] for m in store.get("a")] == ["A 的内容"]
    assert [m["content"] for m in store.get("b")] == ["B 的内容"]
    assert store.get("c") == []


def test_capacity_drops_oldest_not_all(apply_settings):
    data_dir = tempfile.mkdtemp(prefix="hist_")
    apply_settings(DATA_DIR=data_dir)
    from services.agent_service.history import ConversationHistory

    store = ConversationHistory(max_turns=4)
    for i in range(10):
        store.append("x", "user", f"第{i}条")
    kept = store.get("x")
    assert len(kept) == 4
    assert kept[-1]["content"] == "第9条"


def test_long_message_truncated(apply_settings):
    data_dir = tempfile.mkdtemp(prefix="hist_")
    apply_settings(DATA_DIR=data_dir)
    store = _new_history(data_dir)
    store.append("y", "user", "长" * 20000)
    message = store.get("y")[0]
    assert len(message["content"]) < 20000
    assert "截断" in message["content"]


def test_clear_removes_file(apply_settings):
    data_dir = tempfile.mkdtemp(prefix="hist_")
    apply_settings(DATA_DIR=data_dir)
    store = _new_history(data_dir)
    store.append("z", "user", "内容")
    store.clear("z")
    assert store.get("z") == []
    # 不能残留可被再次读回的文件
    assert _new_history(data_dir).get("z") == []
