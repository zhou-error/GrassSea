"""项目经理 Agent (PM Agent)

负责任务分解、资源分配、进度跟踪、风险识别。
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
        """执行 PM 任务"""
        action = task.get("action", "")

        if "decompose" in action:
            return await self._decompose_task(task, context, callbacks)
        elif "allocate" in action:
            return await self._allocate_resources(task, context, callbacks)
        elif "aggregate" in action:
            return await self._aggregate_results(task, context, callbacks)
        else:
            return await self._decompose_task(task, context, callbacks)

    async def _decompose_task(
        self, task: dict, context: dict, callbacks: AgentCallbacks
    ) -> dict:
        """分解任务为 DAG"""
        requirement = task.get("inputs", {}).get("requirement", task.get("description", ""))
        return {
            "status": "completed",
            "dag": {
                "steps": [
                    {"step_id": "s1", "action": "parse", "description": "解析输入"},
                    {"step_id": "s2", "action": "analyze", "description": "分析需求", "dependencies": ["s1"]},
                    {"step_id": "s3", "action": "execute", "description": "执行任务", "dependencies": ["s2"]},
                    {"step_id": "s4", "action": "report", "description": "生成结果", "dependencies": ["s3"]},
                ]
            },
            "summary": f"已将需求分解为 4 个步骤: {requirement[:100]}",
        }

    async def _allocate_resources(
        self, task: dict, context: dict, callbacks: AgentCallbacks
    ) -> dict:
        """分配资源（选择智能体和工具）"""
        task_info = task.get("inputs", {}).get("task", {})
        return {
            "status": "completed",
            "assignments": [
                {"agent_id": "naval_arch_agent", "reason": "涉及船舶专业计算"},
                {"tool_ids": ["hydrostatics", "stability"], "reason": "需要静水力和稳性分析"},
            ],
        }

    async def _aggregate_results(
        self, task: dict, context: dict, callbacks: AgentCallbacks
    ) -> dict:
        """聚合子任务结果"""
        sub_results = task.get("inputs", {}).get("sub_results", [])
        return {
            "status": "completed",
            "summary": f"聚合了 {len(sub_results)} 个子任务的结果",
            "overall_status": "success" if all(r.get("status") == "completed" for r in sub_results) else "partial",
        }
