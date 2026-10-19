"""任务规划模块

DAG 任务解析器 + ReAct/CoT 提示模板。
将用户输入分解为标准化步骤描述。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from services.agent_service.intent import IntentResult, IntentType
from shared.utils.config import Settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TaskStep:
    step_id: str
    action: str
    description: str
    inputs: dict = field(default_factory=dict)
    expected_outputs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    timeout: int = 300
    agent_id: str | None = None
    tool_ids: list[str] = field(default_factory=list)


@dataclass
class TaskDAG:
    task_id: str
    title: str
    steps: list[TaskStep]
    parallel_groups: list[list[str]] = field(default_factory=list)


# ReAct + CoT Prompt 模板
PLANNING_SYSTEM_PROMPT = """你是 GrassSea AI 的任务规划器。将用户请求分解为可执行的步骤 DAG。

## 输出格式
返回 JSON:
{
  "title": "任务标题",
  "steps": [
    {
      "step_id": "step_1",
      "action": "动作名称",
      "description": "步骤描述",
      "inputs": {},
      "expected_outputs": ["预期输出"],
      "dependencies": [],
      "agent_id": "可选的智能体ID",
      "tool_ids": ["需要的工具ID"],
      "timeout": 300
    }
  ],
  "parallel_groups": [["step_2", "step_3"]],
  "summary": "任务摘要"
}

## 可用的智能体
- pm_agent: 项目经理 (任务分解、资源分配)
- naval_arch_agent: 船舶工程师 (型线设计、稳性计算、规范审查)
- cad_agent: CAD Agent (图纸绘制、型线绘制)
- review_agent: 审查 Agent (规范合规检查)
- research_agent: 研究员 (文献检索、报告)
- doc_agent: 文档工程师 (报告排版、PDF生成)

## 可用的工具
- reg_check: 规范合规审查
- hydrostatics: 静水力计算
- stability: 稳性分析
- resistance: 阻力计算
- cad_draw: CAD图纸生成
- xlsx_parser: 表格解析
- pdf_parser: PDF解析
- report_gen: 报告生成
- web_search: 联网搜索
"""


class TaskPlanner:
    """任务规划器"""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def plan(self, message: str, intent: IntentResult) -> dict:
        """规划单智能体任务"""
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        steps = self._rule_based_plan(message, intent)
        # 无依赖的根步骤可以并行执行
        roots = [s.step_id for s in steps if not s.dependencies]
        parallel_groups = [roots] if len(roots) > 1 else []

        dag = {
            "task_id": task_id,
            "title": intent.intent_type.value,
            "steps": [s.__dict__ for s in steps],
            "parallel_groups": parallel_groups,
            "summary": f"任务类型: {intent.intent_type.value}",
            "intent": intent.intent_type.value,
            "status": "pending",
            "progress": 0.0,
        }
        return dag

    async def plan_multi_agent(self, message: str, intent: IntentResult) -> dict:
        """规划多智能体协同任务"""
        task_id = f"task_{uuid.uuid4().hex[:12]}"

        # 使用 LLM 分解复杂任务
        if self.settings.DEEPSEEK_API_KEY:
            dag = await self._llm_plan(message)
        else:
            dag = self._rule_based_multi_plan(message, intent)

        dag["task_id"] = task_id
        dag["status"] = "pending"
        dag["progress"] = 0.0
        return dag

    # 已真实实现的工具；其余工具调用会返回 not_implemented
    IMPLEMENTED_TOOLS = {
        "hydrostatics", "stability", "resistance", "hull_transform",
        "rhino_bridge",
    }

    # 关键词 -> (智能体, 动作) 能力路由
    AGENT_ROUTES = (
        (("稳性", "横摇", "复原", "stability", "静水力", "排水量", "浮心", "稳心"), "naval_arch_agent", "stability_calc"),
        (("阻力", "快速性", "推进", "resistance"), "naval_arch_agent", "resistance_calc"),
        (("型线", "型值", "线型", "hull"), "naval_arch_agent", "hull_design"),
        (("审查", "合规", "规范", "检查", "review"), "review_agent", "regulation_check"),
        (("报告", "排版", "文档", "report"), "doc_agent", "report_gen"),
        (("文献", "检索", "调研", "趋势", "research"), "research_agent", "literature_search"),
        (("计划", "分解", "排期", "项目", "pm"), "pm_agent", "task_decomposition"),
        (("建模", "rhino", "Rhino", "实体", "挤出", "布尔", "球体", "曲面"), "rhino_agent", "rhino_modeling"),
    )

    # 动作 -> 可并行执行的已实现校核工具
    TOOL_FOR_ACTION = {
        "stability_calc": "hydrostatics",
        "resistance_calc": "resistance",
        "hull_design": "hull_transform",
        "rhino_modeling": "rhino_bridge",
    }

    # 智能体 / 动作 / 工具的中文名称，用于生成面向用户的步骤描述
    AGENT_LABELS = {
        "naval_arch_agent": "船舶工程师",
        "review_agent": "审查专家",
        "pm_agent": "项目经理",
        "cad_agent": "CAD 工程师",
        "rhino_agent": "Rhino 建模工程师",
        "doc_agent": "文档工程师",
        "research_agent": "研究员",
    }
    ACTION_LABELS = {
        "stability_calc": "完整稳性与初稳性计算",
        "resistance_calc": "阻力与推进性能计算",
        "hull_design": "型线设计与优化",
        "rhino_modeling": "Rhino 三维建模",
        "general_analysis": "综合工程分析",
        "regulation_check": "规范符合性检查",
        "report_gen": "报告生成",
        "literature_search": "文献检索与信息提炼",
        "task_decomposition": "任务分解",
        "progress_aggregation": "各步结果汇总",
    }
    TOOL_LABELS = {
        "hydrostatics": "静水力校核",
        "stability": "稳性校核",
        "resistance": "阻力校核",
        "hull_transform": "船型变换校核",
    }

    def _step_title(self, agent_id: str, action: str) -> str:
        agent = self.AGENT_LABELS.get(agent_id, agent_id)
        act = self.ACTION_LABELS.get(action, action)
        return f"{agent}：{act}"

    def _route_agent(self, message: str) -> tuple[str, str]:
        """按关键词把请求路由到已实现的智能体能力"""
        for keywords, agent_id, action in self.AGENT_ROUTES:
            if any(kw in message for kw in keywords):
                return agent_id, action
        return "naval_arch_agent", "general_analysis"

    def _rule_based_plan(self, message: str, intent: IntentResult) -> list[TaskStep]:
        """基于规则的任务分解

        原则：优先派发给**已实现**的智能体能力；工具只在确实实现时才作为步骤。
        不再构造"前置解析 → 计算 → 报告"的硬依赖链：此前 xlsx_parser/report_gen
        尚未实现，第一步返回 not_implemented 就让后续步骤永远不满足依赖，
        整单被判死锁、一步都没跑（已确认的线上问题）。
        """
        if intent.intent_type == IntentType.TOOL_CALL:
            tool = self._infer_tool(message)
            if tool in self.IMPLEMENTED_TOOLS:
                return [
                    TaskStep(
                        "step_1",
                        tool,
                        f"执行工具：{self.TOOL_LABELS.get(tool, tool)}",
                        tool_ids=[tool],
                        timeout=120,
                    )
                ]
            agent_id, action = self._route_agent(message)
            return [
                TaskStep(
                    "step_1",
                    action,
                    f"{self._step_title(agent_id, action)}（{tool or '未匹配到'} 工具尚未实现，改由智能体处理）",
                    agent_id=agent_id,
                    timeout=180,
                )
            ]

        if intent.intent_type == IntentType.PROFESSIONAL_TASK:
            agent_id, action = self._route_agent(message)
            steps = [
                TaskStep(
                    "step_1",
                    action,
                    self._step_title(agent_id, action),
                    agent_id=agent_id,
                    timeout=240,
                )
            ]
            tool = self.TOOL_FOR_ACTION.get(action)
            if tool in self.IMPLEMENTED_TOOLS:
                steps.append(
                    TaskStep(
                        "step_2",
                        tool,
                        f"工具校核：{self.TOOL_LABELS.get(tool, tool)}",
                        tool_ids=[tool],
                        timeout=120,
                    )
                )
            return steps

        # 其他意图（闲聊 / 知识查询已由 intent 分流），兜底做一次分析
        return [TaskStep("step_1", "analyze", "分析并处理请求", timeout=120)]

    def _rule_based_multi_plan(self, message: str, intent: IntentResult) -> dict:
        """基于规则的多智能体规划

        只编排**已实现**的能力：naval_arch_agent 负责真实计算，pm_agent 负责结果聚合。
        不再以 pm_decompose 起步 —— 任务分解尚未实现，首步被跳过会让整单失败；
        research / cad / doc 目前同样为 not_implemented，因此不纳入编排。
        """
        return {
            "title": "多智能体协同任务",
            "steps": [
                TaskStep(
                    "step_1a", "stability_calc", self._step_title("naval_arch_agent", "stability_calc"),
                    agent_id="naval_arch_agent", timeout=180,
                ).__dict__,
                TaskStep(
                    "step_1b", "resistance_calc", self._step_title("naval_arch_agent", "resistance_calc"),
                    agent_id="naval_arch_agent", timeout=180,
                ).__dict__,
                TaskStep(
                    "step_2", "progress_aggregation", self._step_title("pm_agent", "progress_aggregation"),
                    agent_id="pm_agent", dependencies=["step_1a", "step_1b"], timeout=60,
                ).__dict__,
            ],
            "parallel_groups": [["step_1a", "step_1b"]],
            "summary": "多智能体协同执行（计算 + 汇总）",
        }

    def _infer_tool(self, message: str) -> str | None:
        """从消息推断需要的工具"""
        tool_keywords = {
            "reg_check": ["审查", "合规", "检查", "规范"],
            "cad_draw": ["画", "绘制", "图", "型线", "CAD"],
            "rhino_bridge": ["建模", "Rhino", "实体", "挤出", "布尔", "球体"],
            "hydrostatics": ["静水力", "排水量", "浮心", "稳心"],
            "stability": ["稳性", "横摇", "复原"],
            "resistance": ["阻力", "快速性", "推进"],
            "report_gen": ["报告", "PDF", "导出", "生成"],
            "xlsx_parser": ["表格", "Excel", "型值表", "xlsx"],
            "pdf_parser": ["PDF", "解析"],
            "web_search": ["搜索", "查找", "检索", "最新"],
        }
        for tool, keywords in tool_keywords.items():
            if any(kw in message for kw in keywords):
                return tool
        return None

    # 已实现的智能体能力（agent_id, action）；未列入的会被跳过
    IMPLEMENTED_ACTIONS = {
        ("naval_arch_agent", "stability_calc"),
        ("naval_arch_agent", "resistance_calc"),
        ("naval_arch_agent", "hull_design"),
        ("naval_arch_agent", "general_analysis"),
        ("review_agent", "regulation_check"),
        ("pm_agent", "progress_aggregation"),
    }

    def _is_runnable(self, step: dict) -> bool:
        """该步骤能否真正执行（工具已实现，或智能体能力已实现）"""
        tool_ids = step.get("tool_ids") or []
        if tool_ids:
            return any(t in self.IMPLEMENTED_TOOLS for t in tool_ids)
        return (step.get("agent_id"), step.get("action")) in self.IMPLEMENTED_ACTIONS

    def _normalize_llm_plan(self, plan: dict) -> dict:
        """补齐 LLM 计划中缺失的派发目标

        LLM 往往只给出 action/description，不填 agent_id/tool_ids，
        导致执行器判定每一步都"无可派发目标"，整单直接失败。
        这里按同样的关键词路由把可执行的步骤接上真实能力。
        """
        steps = plan.get("steps") or []
        normalized = []
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            step.setdefault("step_id", f"step_{idx + 1}")
            step.setdefault("dependencies", [])
            if not step.get("agent_id") and not step.get("tool_ids"):
                text = f"{step.get('action', '')} {step.get('description', '')}"
                agent_id, action = self._route_agent(text)
                step["agent_id"] = agent_id
                current = step.get("action")
                if not current or current not in self.ACTION_LABELS:
                    step["action"] = action
            normalized.append(step)

        # 依赖旁路：把"不可执行"的步骤从依赖链上摘掉。
        # 否则一步未实现（如项目经理的任务分解）会把后续所有步骤拖成跳过，整单失败。
        by_id = {s["step_id"]: s for s in normalized}
        original = {s["step_id"]: list(s.get("dependencies") or []) for s in normalized}
        unrunnable = {s["step_id"] for s in normalized if not self._is_runnable(s)}

        def expand(step_id: str, guard: set[str]) -> list[str]:
            if step_id in guard or step_id not in by_id:
                return []
            guard.add(step_id)
            if step_id not in unrunnable:
                return [step_id]
            out: list[str] = []
            for dep in original.get(step_id, []):
                out.extend(expand(dep, guard))
            return out

        for step in normalized:
            deps: list[str] = []
            for dep in original.get(step["step_id"], []):
                deps.extend(expand(dep, set()))
            step["dependencies"] = sorted(d for d in set(deps) if d != step["step_id"])

        plan["steps"] = normalized
        if not plan.get("parallel_groups"):
            roots = [s["step_id"] for s in normalized if not s.get("dependencies")]
            plan["parallel_groups"] = [roots] if len(roots) > 1 else []
        plan.setdefault("summary", "多智能体协同执行")
        return plan

    async def _llm_plan(self, message: str) -> dict:
        """LLM 驱动的任务规划"""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.settings.DEEPSEEK_BASE_URL}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.DEEPSEEK_API_KEY}"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
                            {"role": "user", "content": f"请为以下用户请求规划任务:\n{message}"},
                        ],
                        "max_tokens": 2048,
                        "temperature": 0.3,
                    },
                )
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                import json, re
                json_match = re.search(r"\{[\s\S]*\}", content)
                if json_match:
                    return self._normalize_llm_plan(json.loads(json_match.group()))
        except Exception as e:
            logger.error("LLM planning failed", error=str(e))

        fallback_agent, fallback_action = self._route_agent(message)
        return {
            "title": "自动规划任务",
            "steps": [
                TaskStep(
                    "step_1",
                    fallback_action,
                    self._step_title(fallback_agent, fallback_action),
                    agent_id=fallback_agent,
                    timeout=240,
                ).__dict__
            ],
            "parallel_groups": [],
            "summary": "任务执行",
        }
