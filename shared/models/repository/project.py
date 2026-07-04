"""Project Repository"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.postgres.project import Project, ProjectStatus
from shared.models.repository.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """项目数据访问层"""
    model = Project

    async def get_by_code(self, code: str) -> Optional[Project]:
        """根据项目代码查找"""
        result = await self.session.execute(
            select(Project).where(Project.code == code)
        )
        return result.scalar_one_or_none()

    async def get_by_owner(
        self, owner_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[Project]:
        """获取用户拥有的项目"""
        result = await self.session.execute(
            select(Project)
            .where(Project.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_active_projects(
        self, skip: int = 0, limit: int = 50
    ) -> list[Project]:
        """获取活跃项目"""
        result = await self.session.execute(
            select(Project)
            .where(Project.status == ProjectStatus.ACTIVE)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def archive_project(self, project_id: UUID) -> Optional[Project]:
        """归档项目"""
        project = await self.get_by_id(project_id)
        if project:
            project.status = ProjectStatus.ARCHIVED
            await self.session.flush()
        return project
