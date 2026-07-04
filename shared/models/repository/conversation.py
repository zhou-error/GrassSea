"""Conversation Repository (MongoDB)"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.models.mongodb.collections import MongoCollections


class ConversationRepository:
    """对话历史 Repository (MongoDB)"""

    collection_name = MongoCollections.CONVERSATION_HISTORY

    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db[self.collection_name]

    async def create_session(
        self, session_id: str, user_id: str, initial_state: str = "IDLE"
    ) -> str:
        """创建新会话"""
        doc = {
            "session_id": session_id,
            "user_id": user_id,
            "messages": [],
            "intent": None,
            "state": initial_state,
            "token_usage": {"prompt": 0, "completion": 0, "total": 0},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        await self.collection.insert_one(doc)
        return session_id

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: list[dict] | None = None,
    ) -> None:
        """添加消息到会话"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow(),
            "sources": sources or [],
        }
        await self.collection.update_one(
            {"session_id": session_id},
            {
                "$push": {"messages": message},
                "$set": {"updated_at": datetime.utcnow()},
            },
        )

    async def get_session(self, session_id: str) -> Optional[dict]:
        """获取会话详情"""
        return await self.collection.find_one({"session_id": session_id})

    async def update_state(self, session_id: str, state: str) -> None:
        """更新会话状态"""
        await self.collection.update_one(
            {"session_id": session_id},
            {"$set": {"state": state, "updated_at": datetime.utcnow()}},
        )

    async def update_intent(self, session_id: str, intent: str) -> None:
        """更新意图识别结果"""
        await self.collection.update_one(
            {"session_id": session_id},
            {"$set": {"intent": intent, "updated_at": datetime.utcnow()}},
        )

    async def update_token_usage(
        self, session_id: str, prompt: int, completion: int
    ) -> None:
        """更新 Token 统计"""
        await self.collection.update_one(
            {"session_id": session_id},
            {
                "$inc": {
                    "token_usage.prompt": prompt,
                    "token_usage.completion": completion,
                    "token_usage.total": prompt + completion,
                },
                "$set": {"updated_at": datetime.utcnow()},
            },
        )

    async def get_recent_sessions(
        self, user_id: str, limit: int = 20
    ) -> list[dict]:
        """获取用户最近的会话列表"""
        cursor = (
            self.collection.find({"user_id": user_id})
            .sort("updated_at", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        result = await self.collection.delete_one({"session_id": session_id})
        return result.deleted_count > 0
