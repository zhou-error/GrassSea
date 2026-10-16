"""研究员 Agent (Research Agent) — 文献检索、信息提炼、每日简报生成

诚实性约定：本 Agent 尚未接入可用的检索源（web_search 工具未实现），
因此不返回任何文献标题、URL、相关度评分或引用计数。
"""

from __future__ import annotations
from shared.protocols.agent import AgentCallbacks, AgentCapability, AgentMetadata, BaseAgent

RESEARCH_AGENT_METADATA = AgentMetadata(
    agent_id="research_agent",
    name="研究员 Agent",
    role="文献检索、信息提炼、报告撰写、趋势分析",
    capabilities=[
        AgentCapability(name="literature_search", description="文献检索与信息提炼", tools=["web_search", "pdf_parser"], estimated_latency_ms=3000),
        AgentCapability(name="daily_brief", description="每日简报生成", tools=["web_search", "report_gen"], estimated_latency_ms=5000),
        AgentCapability(name="trend_analysis", description="技术趋势分析", tools=["web_search"], estimated_latency_ms=4000),
    ],
    model_preference="deepseek-chat",
    max_concurrent_tasks=5,
    version="0.1.0",
)


class ResearchAgent(BaseAgent):
    def __init__(self): super().__init__(RESEARCH_AGENT_METADATA)

    async def handle_task(self, task: dict, context: dict, callbacks: AgentCallbacks) -> dict:
        """动作路由：literature_search / research → 文献检索；daily_brief → 简报；trend_analysis → 趋势分析"""
        action = task.get("action", "")
        if "brief" in action or "简报" in action:
            return await self._daily_brief(task, context, callbacks)
        if "trend" in action or "趋势" in action:
            return await self._trend_analysis(task, context, callbacks)
        return await self._literature_search(task, context, callbacks)

    async def _literature_search(self, task: dict, context: dict, callbacks: AgentCallbacks) -> dict:
        """文献检索 — 未接入检索源，如实返回未实现"""
        return {
            "status": "not_implemented",
            "message": "文献检索尚未实现：未接入可用的文献检索源（web_search 工具未实现），无法给出真实文献条目，因此不返回任何文献标题、链接或相关度评分。",
        }

    async def _daily_brief(self, task: dict, context: dict, callbacks: AgentCallbacks) -> dict:
        """每日简报 — 未接入检索源与生成器，如实返回未实现"""
        return {
            "status": "not_implemented",
            "message": "每日简报生成尚未实现：未接入检索源与简报生成器，无法产出真实简报内容，因此不返回任何文献条目或摘要。",
        }

    async def _trend_analysis(self, task: dict, context: dict, callbacks: AgentCallbacks) -> dict:
        """趋势分析 — 未接入数据源，如实返回未实现"""
        return {
            "status": "not_implemented",
            "message": "技术趋势分析尚未实现：未接入检索源与趋势分析数据，无法给出真实趋势结论，因此不返回任何趋势判断或引用计数。",
        }
