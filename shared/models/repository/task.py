"""Task Repository"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.postgres.task import TaskRecord, TaskStatus, TaskType
from shared.models.repository.base import BaseRepository


class TaskRepository(BaseRepository[TaskRecord]):
    """任务数据访问层"""
    model = TaskRecord

    async def get_by_session(self, session_id: str) -> list[TaskRecord]:
        """获取会话的所有任务"""
        result = await self.session.execute(
            select(TaskRecord)
            .where(TaskRecord.session_id == session_id)
            .order_by(TaskRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_user(
        self, user_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[TaskRecord]:
        """获取用户的任务列表"""
        result = await self.session.execute(
            select(TaskRecord)
            .where(TaskRecord.user_id == user_id)
            .order_by(TaskRecord.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_status(
        self, status: TaskStatus, skip: int = 0, limit: int = 50
    ) -> list[TaskRecord]:
        """根据状态获取任务"""
        result = await self.session.execute(
            select(TaskRecord)
            .where(TaskRecord.status == status)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self, task_id: UUID, status: TaskStatus, error_message: str | None = None
    ) -> None:
        """更新任务状态"""
        values = {"status": status}
        if error_message:
            values["error_message"] = error_message
        await self.session.execute(
            update(TaskRecord).where(TaskRecord.id == task_id).values(**values)
        )
        await self.session.flush()

    async def update_progress(self, task_id: UUID, progress: float) -> None:
        """更新任务进度"""
        await self.session.execute(
            update(TaskRecord)
            .where(TaskRecord.id == task_id)
            .values(progress=progress)
        )
        await self.session.flush()
