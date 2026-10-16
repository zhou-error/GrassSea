"""项目经理 Agent (PM Agent)

负责任务分解、资源分配、进度跟踪、风险识别。

诚实性约定：
- 任务分解 / 资源分配尚未实现（未接入大模型规划器与调度评估），返回 not_implemented，
  不再返回任何与需求无关的预设步骤或预设分配结果；
- 进度聚合是真实执行的：只统计调用方实际传入的 sub_results。
"""

from __future__ import annotations

from shared.protocols.agent import AgentCallbacks, AgentCapability, AgentMetadata, BaseAgent

PM_AGENT_METADATA = AgentMetadata(
    agent_id="pm_agent",
    name="项目经理 Agent",
    role="负责任务分解、资源分配、进度跟踪、风险识别",
    capabilities=[
        AgentCapability(
            name="task_decomposition",
            description="将用户需求分解为标准化的任务步骤 DAG",
            input_schema={"type": "object", "properties": {"requirement": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"dag": {"type": "object"}}},
            tools=[],
            estimated_latency_ms=500,
        ),
        AgentCapability(
            name="resource_allocation",
            description="根据任务类型分配合适的智能体和工具",
            input_schema={"type": "object", "properties": {"task": {"type": "object"}}},
            output_schema={"type": "object", "properties": {"assignments": {"type": "array"}}},
            tools=[],
            estimated_latency_ms=300,
        ),
        AgentCapability(
            name="progress_aggregation",
            description="聚合各子任务的执行结果，生成总体进度报告",
            input_schema={"type": "object", "properties": {"sub_results": {"type": "array"}}},
            output_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
            tools=["report_gen"],
            estimated_latency_ms=800,
        ),
    ],
    model_preference="deepseek-chat",
    max_concurrent_tasks=10,
    version="0.1.0",
)


class PMAgent(BaseAgent):
    """项目经理智能体"""

    def __init__(self):
        super().__init__(PM_AGENT_METADATA)

    async def handle_task(
        self,
        task: dict,
        context: dict,
        callbacks: AgentCallbacks,
    ) -> dict:
        """执行 PM 任务 — 动作关键词路由保持不变，并补上原先漏配的分配/聚合分支"""
        action = task.get("action", "")

        # 注意：能力名是 allocation / aggregation，不含 "allocate" / "aggregate" 子串，
        # 因此这里匹配更短的同源词干（allocat / aggregat），否则会被误路由到任务分解。
        if "allocat" in action or "分配" in action:
            return await self._allocate_resources(task, context, callbacks)
        elif "aggregat" in action or "聚合" in action:
            return await self._aggregate_results(task, context, callbacks)
        else:
            # task_decomposition / pm_decompose / decompose / 分解（默认）
            return await self._decompose_task(task, context, callbacks)

    async def _decompose_task(
        self, task: dict, context: dict, callbacks: AgentCallbacks
    ) -> dict:
        """任务分解 — 未接入规划器，如实返回未实现（不产出预设 DAG）"""
        return {
            "status": "not_implemented",
            "message": "任务分解尚未实现：未接入大模型/任务规划器，无法依据需求生成真实的步骤 DAG，因此不返回任何预设步骤。",
        }

    async def _allocate_resources(
        self, task: dict, context: dict, callbacks: AgentCallbacks
    ) -> dict:
        """资源分配 — 未接入能力匹配与调度评估，如实返回未实现（不产出预设分配）"""
        return {
            "status": "not_implemented",
            "message": "资源分配尚未实现：未建立任务能力匹配与可执行性评估逻辑，无法给出真实的智能体/工具分配，因此不返回任何预设分配结果。",
        }

    async def _aggregate_results(
        self, task: dict, context: dict, callbacks: AgentCallbacks
    ) -> dict:
        """聚合子任务结果 — 只统计调用方实际传入的 sub_results，不臆造结果"""
        sub_results = task.get("inputs", {}).get("sub_results", [])
        if not isinstance(sub_results, list) or not sub_results:
            return {
                "status": "not_implemented",
                "message": "进度聚合未执行：调用方未提供任何子任务结果（inputs.sub_results 为空），没有可聚合的数据。",
            }
        completed = sum(
            1 for r in sub_results if isinstance(r, dict) and r.get("status") == "completed"
        )
        return {
            "status": "completed",
            "summary": f"聚合了 {len(sub_results)} 个子任务的结果，其中 {completed} 个 status 为 completed",
            "overall_status": "success" if completed == len(sub_results) else "partial",
        }
