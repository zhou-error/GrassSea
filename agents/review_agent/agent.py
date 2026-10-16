"""审查 Agent (Review Agent)

负责参数合规检查（内置启发式阈值）、合规标注、审查报告生成。

诚实性约定：本项目尚未接入规范条文库/RAG，无法核对任何规范条文，
因此本 Agent 不引用、不编造任何规范条款编号；检查结论只说明参数是否
低于内置校验阈值，不构成规范合规判定。
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
    """审查智能体

    内置校验阈值仅用于参数级提示，来源为项目早期示例，尚未与任何规范
    条文库核对，因此不得被表述为"规范要求"。
    """

    # 舱壁间距内置校验阈值 (mm) — 非规范条文，仅作启发式提示
    BULKHEAD_CLEARANCE_MIN_MM = 600.0

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
        """参数合规检查（内置启发式阈值）

        只对调用方实际传入的设计参数做阈值比对：这一部分是真实执行的；
        未接入规范条文库，因此**不输出任何规范条款编号**，也不声称已核对
        规范条文。生产环境接入 RAG + 知识图谱后，才可补充条款依据。
        """
        design_params = task.get("inputs", {}).get("design_params", {})
        regulation_codes = task.get("inputs", {}).get("regulation_codes", ["CCS"])
        threshold = self.BULKHEAD_CLEARANCE_MIN_MM

        if not isinstance(design_params, dict) or not design_params:
            # 无参数可查时不再返回 pass=true（那会是一条没有依据的"通过"结论）
            return {
                "status": "not_implemented",
                "message": "参数合规检查未执行：调用方未提供任何设计参数（inputs.design_params 为空），没有可比对的参数，因此不返回通过/不通过结论。",
            }

        violations = []
        suggestions = []

        for param, value in design_params.items():
            if "舱壁" not in str(param):
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            # 真实阈值比对（阈值为内置值，非规范条文）
            if value < threshold:
                violations.append({
                    "parameter": str(param),
                    "value": float(value),
                    "requirement": f">= {threshold:g}mm（内置校验阈值，未与规范条文核对）",
                    "severity": "warning",
                    "description": f"{param} 为 {value}mm，低于内置校验阈值 {threshold:g}mm；该阈值非规范条文，需人工依据现行规范复核。",
                })
                suggestions.append({
                    "parameter": str(param),
                    "suggestion": f"建议将 {param} 增大至 ≥{threshold:g}mm，并由人工依据现行规范条文复核。",
                    "priority": "high",
                })

        return {
            "status": "completed",
            "pass": len(violations) == 0,
            "violations": violations,
            "suggestions": suggestions,
            "regulation_basis": "内置启发式阈值，未接入规范条文库；结论不构成规范合规判定",
            "regulation_codes_requested": regulation_codes,
        }

    async def _generate_report(
        self, task: dict, context: dict, callbacks: AgentCallbacks
    ) -> dict:
        """生成审查报告

        只汇总调用方实际提供的 review_result，不添加任何未提供的条款或结论。
        """
        review_result = task.get("inputs", {}).get("review_result", {})
        if not isinstance(review_result, dict) or not review_result:
            return {
                "status": "not_implemented",
                "message": "审查报告未生成：调用方未提供任何检查结果（inputs.review_result 为空），没有可汇总的内容。",
            }
        violations = review_result.get("violations") or []
        suggestions = review_result.get("suggestions") or []
        return {
            "status": "completed",
            "report": f"## 参数合规检查报告（依据调用方提供的检查结果汇总）\n\n"
                      f"审查结果: {'通过' if review_result.get('pass') else '不通过'}\n"
                      f"问题项: {len(violations)} 条\n"
                      f"修改建议: {len(suggestions)} 条\n"
                      f"说明: 本报告仅汇总调用方提供的检查结果；未接入规范条文库，不引用任何规范条款编号，不构成规范合规判定。\n",
        }
