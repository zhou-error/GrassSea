"""会话状态机 (Session FSM)

使用 transitions 库实现文档定义的状态转换。
状态: IDLE → PARSING → CHITCHAT/KNOWLEDGE/TOOL_TASK → ... → COMPLETED
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum

from transitions.extensions.asyncio import AsyncMachine

from shared.utils.logging import get_logger

logger = get_logger(__name__)


class SessionState(str, Enum):
    """会话状态"""
    IDLE = "idle"
    PARSING = "parsing"
    CHITCHAT = "chitchat"
    KNOWLEDGE = "knowledge"
    TOOL_TASK = "tool_task"
    RESPONDING = "responding"
    SEARCHING = "searching"
    PLANNING = "planning"
    RANKING = "ranking"
    GENERATING = "generating"
    EXECUTING = "executing"
    AGGREGATING = "aggregating"
    STREAMING = "streaming"
    COMPLETED = "completed"
    WAITING_USER = "waiting_user"
    ERROR = "error"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


# 状态迁移定义
TRANSITIONS = [
    # IDLE → PARSING
    {"trigger": "receive_message", "source": SessionState.IDLE, "dest": SessionState.PARSING},

    # PARSING → 各子状态
    {"trigger": "classify_chitchat", "source": SessionState.PARSING, "dest": SessionState.CHITCHAT},
    {"trigger": "classify_knowledge", "source": SessionState.PARSING, "dest": SessionState.KNOWLEDGE},
    {"trigger": "classify_tool_task", "source": SessionState.PARSING, "dest": SessionState.TOOL_TASK},

    # 各子状态 → 处理状态
    {"trigger": "start_responding", "source": SessionState.CHITCHAT, "dest": SessionState.RESPONDING},
    {"trigger": "start_searching", "source": SessionState.KNOWLEDGE, "dest": SessionState.SEARCHING},
    {"trigger": "start_planning", "source": SessionState.TOOL_TASK, "dest": SessionState.PLANNING},

    # SEARCHING → RANKING → GENERATING
    {"trigger": "rank_results", "source": SessionState.SEARCHING, "dest": SessionState.RANKING},
    {"trigger": "start_generating", "source": SessionState.RANKING, "dest": SessionState.GENERATING},

    # PLANNING → EXECUTING
    {"trigger": "start_executing", "source": SessionState.PLANNING, "dest": SessionState.EXECUTING},

    # EXECUTING → WAITING_USER (数据不足)
    {"trigger": "need_user_input", "source": SessionState.EXECUTING, "dest": SessionState.WAITING_USER},
    {"trigger": "user_provided", "source": SessionState.WAITING_USER, "dest": SessionState.EXECUTING},

    # EXECUTING → AGGREGATING
    {"trigger": "aggregate_results", "source": SessionState.EXECUTING, "dest": SessionState.AGGREGATING},

    # RESPONDING / GENERATING / AGGREGATING → STREAMING
    {"trigger": "start_streaming", "source": [SessionState.RESPONDING, SessionState.GENERATING, SessionState.AGGREGATING], "dest": SessionState.STREAMING},

    # STREAMING → COMPLETED
    {"trigger": "finish_streaming", "source": SessionState.STREAMING, "dest": SessionState.COMPLETED},

    # COMPLETED → IDLE (自动回到空闲)
    {"trigger": "reset", "source": SessionState.COMPLETED, "dest": SessionState.IDLE},

    # 异常状态
    {"trigger": "handle_error", "source": "*", "dest": SessionState.ERROR},
    {"trigger": "recover_error", "source": SessionState.ERROR, "dest": SessionState.IDLE},

    # 用户取消
    {"trigger": "user_cancel", "source": "*", "dest": SessionState.CANCELLED},
    {"trigger": "recover_cancel", "source": SessionState.CANCELLED, "dest": SessionState.IDLE},

    # 超时
    {"trigger": "handle_timeout", "source": "*", "dest": SessionState.TIMEOUT},
    {"trigger": "recover_timeout", "source": SessionState.TIMEOUT, "dest": SessionState.IDLE},
]


class SessionFSM:
    """会话有限状态机"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.error_count = 0
        self.max_errors = 3
        self.timeout_seconds = 1800  # 30 分钟

        self.machine = AsyncMachine(
            model=self,
            states=list(SessionState),
            transitions=TRANSITIONS,
            initial=SessionState.IDLE,
        )

    async def on_enter_ERROR(self):
        """进入错误状态时的处理"""
        self.error_count += 1
        logger.warning("Session entered ERROR state", session=self.session_id, errors=self.error_count)
        if self.error_count >= self.max_errors:
            logger.error("Max errors reached, forcing recovery", session=self.session_id)
            await self.recover_error()

    async def on_enter_TIMEOUT(self):
        """进入超时状态时的处理"""
        logger.info("Session timeout", session=self.session_id)
        # 30分钟后自动归档
        await asyncio.sleep(5)  # 开发环境缩短
        if self.state == SessionState.TIMEOUT:
            await self.recover_timeout()

    async def on_enter_WAITING_USER(self):
        """等待用户补充信息"""
        logger.info("Waiting for user input", session=self.session_id)

    def touch(self):
        """更新最后活动时间"""
        self.last_activity = datetime.utcnow()

    @property
    def idle_duration_seconds(self) -> float:
        return (datetime.utcnow() - self.last_activity).total_seconds()

    @property
    def is_timed_out(self) -> bool:
        return self.idle_duration_seconds > self.timeout_seconds
