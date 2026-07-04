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

        dag = {
            "task_id": task_id,
            "title": intent.intent_type.value,
            "steps": [s.__dict__ for s in steps],
            "parallel_groups": [],
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

    def _rule_based_plan(self, message: str, intent: IntentResult) -> list[TaskStep]:
        """基于规则的任务分解"""
        steps = []

        if intent.intent_type == IntentType.TOOL_CALL:
            # 工具调用通常单步
            tool = self._infer_tool(message)
            steps.append(TaskStep(
                step_id="step_1",
                action="tool_execute",
                description=f"执行工具: {tool}",
                tool_ids=[tool] if tool else ["report_gen"],
                timeout=120,
            ))

        elif intent.intent_type == IntentType.PROFESSIONAL_TASK:
            # 专业任务多步
            if any(kw in message for kw in ["稳性", "stability"]):
                steps = [
                    TaskStep("step_1", "parse_input", "解析输入数据（型值表）", tool_ids=["xlsx_parser"], timeout=60),
                    TaskStep("step_2", "hydrostatics", "静水力计算", tool_ids=["hydrostatics"], dependencies=["step_1"], timeout=120),
                    TaskStep("step_3", "stability", "稳性分析", tool_ids=["stability"], dependencies=["step_2"], timeout=120),
                    TaskStep("step_4", "generate_report", "生成计算报告", tool_ids=["report_gen"], dependencies=["step_3"], timeout=60),
                ]
            elif any(kw in message for kw in ["型线", "型值", "线型"]):
                steps = [
                    TaskStep("step_1", "parse_offset", "解析型值表", tool_ids=["xlsx_parser"], timeout=60),
                    TaskStep("step_2", "draw_lines", "绘制型线图", tool_ids=["cad_draw"], agent_id="cad_agent", dependencies=["step_1"], timeout=180),
                ]
            elif any(kw in message for kw in ["审查", "合规", "检查"]):
                steps = [
                    TaskStep("step_1", "retrieve_regs", "检索相关规范条文", tool_ids=["web_search"], timeout=60),
                    TaskStep("step_2", "compliance_check", "逐条合规审查", tool_ids=["reg_check"], agent_id="review_agent", dependencies=["step_1"], timeout=120),
                    TaskStep("step_3", "gen_report", "生成审查报告", tool_ids=["report_gen"], dependencies=["step_2"], timeout=60),
                ]
            else:
                steps = [
                    TaskStep("step_1", "analyze", "分析需求", timeout=60),
                    TaskStep("step_2", "execute", "执行计算/分析", timeout=300),
                ]

        return steps

    def _rule_based_multi_plan(self, message: str, intent: IntentResult) -> dict:
        """基于规则的多智能体规划"""
        return {
            "title": "多智能体协同任务",
            "steps": [
                TaskStep("step_1", "pm_decompose", "PM Agent 分解任务", agent_id="pm_agent", timeout=60).__dict__,
                TaskStep("step_2a", "research", "研究员检索资料", agent_id="research_agent", dependencies=["step_1"], timeout=120).__dict__,
                TaskStep("step_2b", "naval_compute", "船舶工程师计算分析", agent_id="naval_arch_agent", dependencies=["step_1"], timeout=180).__dict__,
                TaskStep("step_3", "review", "审查 Agent 校验结果", agent_id="review_agent", dependencies=["step_2a", "step_2b"], timeout=120).__dict__,
                TaskStep("step_4", "report", "文档 Agent 生成报告", agent_id="doc_agent", dependencies=["step_3"], timeout=60).__dict__,
            ],
            "parallel_groups": [["step_2a", "step_2b"]],
            "summary": "多智能体协同执行",
        }

    def _infer_tool(self, message: str) -> str | None:
        """从消息推断需要的工具"""
        tool_keywords = {
            "reg_check": ["审查", "合规", "检查", "规范"],
            "cad_draw": ["画", "绘制", "图", "型线", "CAD"],
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
                    return json.loads(json_match.group())
        except Exception as e:
            logger.error("LLM planning failed", error=str(e))

        return {
            "title": "自动规划任务",
            "steps": [TaskStep("step_1", "execute", "执行任务", timeout=300).__dict__],
            "parallel_groups": [],
            "summary": "任务执行",
        }
