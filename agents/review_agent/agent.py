"""审查 Agent (Review Agent)

负责规范条文匹配、合规标注、审查报告生成。
"""

from __future__ import annotations

from shared.protocols.agent import AgentCallbacks, AgentCapability, AgentMetadata, BaseAgent

REVIEW_AGENT_METADATA = AgentMetadata(
    agent_id="review_agent",
    name="审查 Agent",
    role="规范条文匹配、合规标注、审查报告生成",
    capabilities=[
        AgentCapability(
            name="regulation_check",
            description="基于规范条文自动审查设计参数是否符合要求",
            input_schema={
                "type": "object",
                "properties": {
                    "design_params": {"type": "object"},
                    "regulation_codes": {"type": "array", "items": {"type": "string"}},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "pass": {"type": "boolean"},
                    "violations": {"type": "array"},
                    "suggestions": {"type": "array"},
                },
            },
            tools=["reg_check", "web_search"],
            estimated_latency_ms=2000,
        ),
        AgentCapability(
            name="compliance_report",
            description="生成规范合规审查报告（含违规标注和修改建议）",
            input_schema={"type": "object", "properties": {"review_result": {"type": "object"}}},
            output_schema={"type": "object", "properties": {"report": {"type": "string"}}},
            tools=["report_gen"],
            estimated_latency_ms=1500,
        ),
    ],
    model_preference="deepseek-chat",
    max_concurrent_tasks=3,
    version="0.1.0",
)


class ReviewAgent(BaseAgent):
    """审查智能体"""

    def __init__(self):
        super().__init__(REVIEW_AGENT_METADATA)

    async def handle_task(
        self,
        task: dict,
        context: dict,
        callbacks: AgentCallbacks,
    ) -> dict:
        """执行审查任务"""
        action = task.get("action", "regulation_check")

        if "report" in action:
            return await self._generate_report(task, context, callbacks)
        else:
            return await self._regulation_check(task, context, callbacks)

    async def _regulation_check(
        self, task: dict, context: dict, callbacks: AgentCallbacks
    ) -> dict:
        """规范合规审查"""
        design_params = task.get("inputs", {}).get("design_params", {})
        regulation_codes = task.get("inputs", {}).get("regulation_codes", ["CCS"])

        # 调用规范审查工具
        violations = []
        suggestions = []

        # 模拟审查逻辑——生产环境接入 RAG + 知识图谱
        for param, value in design_params.items():
            # 示例：检查舱壁间距
            if "舱壁" in param and isinstance(value, (int, float)) and value < 600:
                violations.append({
                    "clause": "CCS §2.5.3",
                    "parameter": param,
                    "value": value,
                    "requirement": ">= 600mm",
                    "severity": "error",
                    "description": f"{param} 为 {value}mm，不满足规范要求的 ≥600mm",
                })
                suggestions.append({
                    "parameter": param,
                    "suggestion": f"建议将 {param} 增大至 ≥600mm",
                    "priority": "high",
                })

        return {
            "status": "completed",
            "pass": len(violations) == 0,
            "violations": violations,
            "suggestions": suggestions,
            "regulation_codes_checked": regulation_codes,
        }

    async def _generate_report(
        self, task: dict, context: dict, callbacks: AgentCallbacks
    ) -> dict:
        """生成审查报告"""
        review_result = task.get("inputs", {}).get("review_result", {})
        return {
            "status": "completed",
            "report": f"## 规范合规审查报告\n\n"
                      f"审查结果: {'通过' if review_result.get('pass') else '不通过'}\n"
                      f"违规项: {len(review_result.get('violations', []))} 条\n"
                      f"修改建议: {len(review_result.get('suggestions', []))} 条\n",
        }
