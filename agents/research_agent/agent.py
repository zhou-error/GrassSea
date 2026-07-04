"""研究员 Agent (Research Agent) — 文献检索、信息提炼、每日简报生成"""

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
        query = task.get("inputs", {}).get("query", task.get("description", ""))
        return {
            "status": "completed",
            "query": query,
            "sources": [{"title": "示例文献", "url": "https://example.com", "relevance": 0.95}],
            "summary": f"关于 '{query[:50]}' 的研究综述（模拟结果）",
            "citation_count": 15,
        }
