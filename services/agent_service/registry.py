"""智能体注册中心

管理智能体的注册、发现、心跳和健康检查。
开发阶段使用内存注册表，生产环境迁移到 Nacos。
"""

from __future__ import annotations

import time
from typing import Optional

from shared.protocols.agent import AgentMetadata, AgentStatus, BaseAgent
from shared.utils.logging import get_logger

logger = get_logger(__name__)


class AgentRegistry:
    """智能体注册中心（内存实现）"""

    def __init__(self):
        self._agents: dict[str, AgentMetadata] = {}
        self._instances: dict[str, BaseAgent] = {}   # 可执行实例，供 TaskExecutor 派发
        self._status: dict[str, AgentStatus] = {}
        self._heartbeats: dict[str, float] = {}
        self._heartbeat_timeout = 30  # 30秒无心跳标记 UNHEALTHY

    async def initialize(self) -> None:
        """初始化，注册内置智能体（元信息 + 可执行实例）"""
        from agents.cad_agent.agent import CAD_AGENT_METADATA, CADAgent
        from agents.doc_agent.agent import DOC_AGENT_METADATA, DocAgent
        from agents.naval_arch_agent.agent import NAVAL_ARCH_METADATA, NavalArchAgent
        from agents.pm_agent.agent import PM_AGENT_METADATA, PMAgent
        from agents.research_agent.agent import RESEARCH_AGENT_METADATA, ResearchAgent
        from agents.review_agent.agent import REVIEW_AGENT_METADATA, ReviewAgent

        for metadata, agent_cls in (
            (PM_AGENT_METADATA, PMAgent),
            (REVIEW_AGENT_METADATA, ReviewAgent),
            (NAVAL_ARCH_METADATA, NavalArchAgent),
            (CAD_AGENT_METADATA, CADAgent),
            (RESEARCH_AGENT_METADATA, ResearchAgent),
            (DOC_AGENT_METADATA, DocAgent),
        ):
            await self.register(metadata)
            # 同时注册实例，TaskExecutor 据此真实派发 handle_task
            await self.register_instance(agent_cls())
        logger.info("Agent registry initialized", agents=list(self._agents.keys()))

    async def register(self, metadata: AgentMetadata) -> bool:
        """注册智能体"""
        self._agents[metadata.agent_id] = metadata
        self._status[metadata.agent_id] = AgentStatus.IDLE
        self._heartbeats[metadata.agent_id] = time.time()
        logger.info("Agent registered", agent_id=metadata.agent_id, name=metadata.name)
        return True

    async def register_instance(self, agent: BaseAgent) -> bool:
        """注册智能体实例（供 TaskExecutor 真实派发任务）"""
        self._instances[agent.metadata.agent_id] = agent
        agent.set_status(AgentStatus.IDLE)
        return True

    async def get_agent_instance(self, agent_id: str) -> BaseAgent | None:
        """获取智能体实例 — 公开访问器，替代直接读取私有 _agents"""
        return self._instances.get(agent_id)

    async def deregister(self, agent_id: str) -> bool:
        """注销智能体"""
        self._agents.pop(agent_id, None)
        self._instances.pop(agent_id, None)
        self._status.pop(agent_id, None)
        self._heartbeats.pop(agent_id, None)
        logger.info("Agent deregistered", agent_id=agent_id)
        return True

    async def discover(self, capability: str) -> list[AgentMetadata]:
        """按能力发现智能体"""
        results = []
        for agent_id, metadata in self._agents.items():
            for cap in metadata.capabilities:
                if capability in cap.name:
                    results.append(metadata)
                    break
        return results

    async def heartbeat(self, agent_id: str) -> bool:
        """心跳上报"""
        if agent_id in self._agents:
            self._heartbeats[agent_id] = time.time()
            if self._status.get(agent_id) == AgentStatus.UNHEALTHY:
                self._status[agent_id] = AgentStatus.IDLE
            return True
        return False

    async def get_agent(self, agent_id: str) -> AgentMetadata | None:
        """获取智能体信息"""
        return self._agents.get(agent_id)

    async def get_status(self, agent_id: str) -> AgentStatus | None:
        """获取智能体状态"""
        return self._status.get(agent_id)

    async def set_status(self, agent_id: str, status: AgentStatus) -> None:
        """设置智能体状态"""
        self._status[agent_id] = status

    async def list_agents(self) -> list[dict]:
        """列出所有智能体"""
        return [
            {
                "agent_id": agent_id,
                "name": meta.name,
                "role": meta.role,
                "status": self._status.get(agent_id, AgentStatus.UNREGISTERED).value,
                "version": meta.version,
                "capabilities": [c.name for c in meta.capabilities],
                "last_heartbeat": self._heartbeats.get(agent_id, 0),
            }
            for agent_id, meta in self._agents.items()
        ]

    async def check_health(self) -> None:
        """检查所有智能体健康状态"""
        now = time.time()
        for agent_id, last_hb in list(self._heartbeats.items()):
            if now - last_hb > self._heartbeat_timeout:
                if self._status.get(agent_id) != AgentStatus.UNHEALTHY:
                    self._status[agent_id] = AgentStatus.UNHEALTHY
                    logger.warning("Agent unhealthy", agent_id=agent_id)
