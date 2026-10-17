"""文档工程师 Agent (Doc Agent) — 报告排版、PDF 生成、格式规范校验

诚实性约定：本 Agent 尚未接入排版渲染器，因此不产出任何报告文件、
不返回任何文件路径，只如实返回 not_implemented。
"""

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
        """动作路由保持不变：report_gen / report → 报告生成；format_check → 格式校验"""
        action = task.get("action", "")
        if "format" in action or "格式" in action:
            return await self._format_check(task, context, callbacks)
        return await self._report_gen(task, context, callbacks)

    async def _report_gen(self, task: dict, context: dict, callbacks: AgentCallbacks) -> dict:
        """报告排版与 PDF 生成 — 委托给已实现的 report_gen / docx_* 工具

        工具实现位于 tools/report/report_gen.py 与 tools/doc/。
        这里不重复实现渲染逻辑，避免两处行为不一致。
        """
        inputs = task.get("inputs") or {}
        markdown = inputs.get("markdown") or inputs.get("content")
        if not markdown:
            return {
                "status": "error",
                "message": "缺少 markdown/content：报告生成需要提供正文内容。",
            }

        from tools.report.report_gen import ReportGenTool

        tool = ReportGenTool()
        result = await tool.execute(
            {
                "markdown": markdown,
                "title": inputs.get("title") or "报告",
                "path": inputs.get("path") or "",
                "toc": bool(inputs.get("toc", False)),
                "to_pdf": bool(inputs.get("to_pdf", True)),
                "overwrite": bool(inputs.get("overwrite", False)),
            },
            context,
        )
        return result

    async def _format_check(self, task: dict, context: dict, callbacks: AgentCallbacks) -> dict:
        """格式规范校验 — 未接入文档解析与格式规则库，如实返回未实现"""
        return {
            "status": "not_implemented",
            "message": "格式规范校验尚未实现：未接入文档解析器与格式规则库，无法读取待校验文档并核对版式，因此不返回任何校验结论。",
        }
