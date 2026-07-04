"""User Repository"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.models.postgres.user import User, Role
from shared.models.repository.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """用户数据访问层"""
    model = User

    async def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名查找用户"""
        result = await self.session.execute(
            select(User)
            .where(User.username == username)
            .options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱查找用户"""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_active_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """获取活跃用户列表"""
        result = await self.session.execute(
            select(User)
            .where(User.is_active == True)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())


class RoleRepository(BaseRepository[Role]):
    """角色数据访问层"""
    model = Role

    async def get_by_name(self, name: str) -> Optional[Role]:
        """根据角色名查找"""
        result = await self.session.execute(
            select(Role).where(Role.name == name)
        )
        return result.scalar_one_or_none()

    async def get_system_roles(self) -> list[Role]:
        """获取系统内置角色"""
        result = await self.session.execute(
            select(Role).where(Role.is_system == True)
        )
        return list(result.scalars().all())
