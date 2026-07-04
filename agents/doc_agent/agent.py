"""文档工程师 Agent (Doc Agent) — 报告排版、PDF 生成、格式规范校验"""

from __future__ import annotations
from shared.protocols.agent import AgentCallbacks, AgentCapability, AgentMetadata, BaseAgent

DOC_AGENT_METADATA = AgentMetadata(
    agent_id="doc_agent",
    name="文档工程师 Agent",
    role="报告排版、PDF 生成、格式规范校验",
    capabilities=[
        AgentCapability(name="report_gen", description="报告排版与PDF生成", tools=["report_gen"], estimated_latency_ms=2000),
        AgentCapability(name="format_check", description="格式规范校验", tools=[], estimated_latency_ms=500),
    ],
    model_preference="claude-opus-4-8",
    max_concurrent_tasks=3,
    version="0.1.0",
)


class DocAgent(BaseAgent):
    def __init__(self): super().__init__(DOC_AGENT_METADATA)

    async def handle_task(self, task: dict, context: dict, callbacks: AgentCallbacks) -> dict:
        template = task.get("inputs", {}).get("template", "default")
        return {
            "status": "completed",
            "output": "报告已生成",
            "format": "PDF (A4, 12pt, 宋体/Time New Roman)",
            "sections": ["封面", "摘要", "正文", "结论", "附录"],
            "template_used": template,
            "file": "report_output.pdf",
        }
