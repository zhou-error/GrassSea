"""任务执行引擎

按 DAG 拓扑顺序调度，支持步骤级重试和回滚。
步骤真实派发到 AgentRegistry 中的智能体或 ToolRegistry 中的工具，不再模拟执行。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from services.agent_service.registry import AgentRegistry
from shared.models.postgres.task import TaskStatus
from shared.protocols.agent import AgentCallbacks
from shared.utils.config import Settings
from shared.utils.logging import get_logger
from tools.base.registry import ToolRegistry

logger = get_logger(__name__)

# 步骤返回这些状态时不计入成功
_STEP_FAILURE_STATUSES = {"error", "failed"}


# 动作 -> 中文（与 planner 的 ACTION_LABELS 对应，避免跨模块耦合）
_ACTION_LABELS = {
    "stability_calc": "稳性与初稳性计算",
    "resistance_calc": "阻力与推进计算",
    "hull_design": "型线设计",
    "general_analysis": "综合工程分析",
    "regulation_check": "规范符合性检查",
    "report_gen": "报告生成",
    "literature_search": "文献检索",
    "task_decomposition": "任务分解",
    "progress_aggregation": "结果汇总",
    "hydrostatics": "静水力计算",
    "stability": "稳性校核",
    "resistance": "阻力校核",
    "hull_transform": "船型变换校核",
}


# 步骤状态 -> 中文
_STATUS_LABELS = {
    "completed": "完成",
    "failed": "失败",
    "error": "出错",
    "skipped": "跳过",
    "not_implemented": "未实现",
    "running": "执行中",
    "pending": "等待中",
    "cancelled": "已取消",
}

# 结果键 -> (中文标签, 单位)；未登记的键原样输出
_METRIC_LABELS: dict[str, tuple[str, str]] = {
    "displacement_t": ("排水量", "t"),
    "LCB_m": ("浮心纵向位置", "m"),
    "LCB_from_midship_m": ("浮心距舯", "m"),
    "KB_m": ("浮心高度", "m"),
    "BM_m": ("稳心半径", "m"),
    "KM_m": ("横稳心高", "m"),
    "GM_m": ("初稳性高", "m"),
    "roll_period_s": ("横摇周期", "s"),
    "stability_assessment": ("稳性评估", ""),
    "block_coefficient": ("方形系数", ""),
    "wetted_surface_m2": ("湿表面积", "m²"),
    "reynolds_number": ("雷诺数", ""),
    "friction_coefficient": ("摩擦阻力系数", ""),
    "friction_resistance_kn": ("摩擦阻力", "kN"),
    "friction_resistance_kN": ("摩擦阻力", "kN"),
    "total_resistance_kn": ("总阻力", "kN"),
    "total_resistance_estimate_kN": ("总阻力估算", "kN"),
    "effective_power_kw": ("有效功率", "kW"),
    "effective_power_kW": ("有效功率", "kW"),
    "Reynolds_number": ("雷诺数", ""),
    "method": ("方法", ""),
    "parent_vessel": ("母型船", ""),
    "modified_parameters": ("变更参数", ""),
    "speed_kn": ("航速", "kn"),
    "froude_number": ("傅汝德数", ""),
    "scale_ratio": ("缩放比", ""),
    "pass": ("是否通过", ""),
    "severity": ("严重程度", ""),
    "detail": ("说明", ""),
    "message": ("说明", ""),
}


def _format_metrics(values: dict) -> str:
    """把结果字典格式化为中文的「标签 值 单位」串"""
    parts = []
    for key, value in values.items():
        label, unit = _METRIC_LABELS.get(str(key), (str(key), ""))
        if value is None:
            text = "不适用"
        elif isinstance(value, bool):
            text = "是" if value else "否"
        elif isinstance(value, (int, float)):
            text = f"{value:g}"
        elif isinstance(value, (list, tuple)):
            text = "、".join(str(v) for v in value) if value else "无"
        elif isinstance(value, dict):
            text = "；".join(f"{k}: {v}" for k, v in value.items()) if value else "无"
        else:
            text = str(value)
        suffix = f" {unit}" if unit and value is not None else ""
        parts.append(f"{label} {text}{suffix}".strip())
    return "，".join(parts)


class TaskExecutor:
    """任务执行引擎"""

    def __init__(
        self,
        settings: Settings,
        registry: AgentRegistry,
        tool_registry: ToolRegistry | None = None,
    ):
        self.settings = settings
        self.registry = registry
        self.tool_registry = tool_registry
        self._tasks: dict[str, dict] = {}
        self._results: dict[str, dict] = {}
        self._running: dict[str, asyncio.Task] = {}   # 保留后台任务引用，避免被垃圾回收
        self._cancelled: set[str] = set()             # 取消标记，DAG 循环据此真正停下

    async def execute_async(
        self, task: dict, session_id: str, user_id: str | None
    ) -> None:
        """异步执行任务"""
        task_id = task["task_id"]
        task["session_id"] = session_id
        task["user_id"] = user_id
        task["status"] = TaskStatus.PENDING.value
        task.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self._tasks[task_id] = task
        self._cancelled.discard(task_id)

        # 创建后台执行协程 — 必须保留引用，否则任务可能在运行前被垃圾回收
        background = asyncio.create_task(self._execute_dag(task), name=f"grasssea-task-{task_id}")
        self._running[task_id] = background
        background.add_done_callback(lambda _done, tid=task_id: self._running.pop(tid, None))

    async def _execute_dag(self, task: dict) -> None:
        """按 DAG 拓扑顺序执行步骤"""
        task_id = task["task_id"]
        steps = task.get("steps", [])
        parallel_groups = task.get("parallel_groups", [])

        if not steps:
            task["status"] = TaskStatus.COMPLETED.value
            task["progress"] = 100.0
            return

        task["status"] = TaskStatus.RUNNING.value
        results: dict[str, Any] = {}
        completed: set[str] = set()
        failed: set[str] = set()
        skipped: set[str] = set()
        task["step_results"] = results   # 供后续步骤作为上下文读取

        step_map = {s["step_id"]: s for s in steps}
        total_steps = len(steps)

        def finished_count() -> int:
            return len(completed) + len(failed) + len(skipped)

        try:
            while finished_count() < total_steps:
                # cancel_task() 写入的标记 — 让取消真正中断执行循环
                if task_id in self._cancelled:
                    logger.info("Task cancellation observed, stop DAG loop", task_id=task_id)
                    break

                # 找出所有依赖已满足的步骤
                ready = []
                for step in steps:
                    sid = step["step_id"]
                    if sid in completed or sid in failed or sid in skipped:
                        continue
                    deps = step.get("dependencies", [])
                    if all(d in completed for d in deps):
                        ready.append(step)

                if not ready:
                    # 依赖已失败/跳过的步骤直接跳过，而不是让整单死锁
                    # （此前 xlsx_parser 等未实现工具会让后续步骤永远不满足依赖）
                    blocked = [
                        s for s in steps
                        if s["step_id"] not in completed
                        and s["step_id"] not in failed
                        and s["step_id"] not in skipped
                        and any(d in failed or d in skipped for d in s.get("dependencies", []))
                    ]
                    if blocked:
                        for step in blocked:
                            sid = step["step_id"]
                            skipped.add(sid)
                            results[sid] = {
                                "step_id": sid,
                                "action": step.get("action"),
                                "status": "skipped",
                                "reason": "依赖步骤未成功完成",
                                "dependencies": step.get("dependencies", []),
                            }
                        logger.info(
                            "Steps skipped due to failed dependencies",
                            task_id=task_id,
                            steps=[s["step_id"] for s in blocked],
                        )
                        task["progress"] = finished_count() / total_steps * 100.0
                        continue

                    # 真正的死锁：存在循环依赖
                    logger.error("DAG deadlock detected (circular dependencies)", task_id=task_id)
                    failed.update(
                        s for s in step_map
                        if s not in completed and s not in failed and s not in skipped
                    )
                    break

                # 检查并行组
                parallel_steps = []
                sequential_steps = []
                for s in ready:
                    in_parallel = any(s["step_id"] in g for g in parallel_groups)
                    if in_parallel:
                        parallel_steps.append(s)
                    else:
                        sequential_steps.append(s)

                # 并行执行
                if parallel_steps:
                    parallel_tasks = [
                        self._execute_step(s, task) for s in parallel_steps
                    ]
                    parallel_results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
                    for step, result in zip(parallel_steps, parallel_results):
                        if isinstance(result, Exception):
                            logger.error("Step failed", step_id=step["step_id"], error=str(result))
                            failed.add(step["step_id"])
                            results[step["step_id"]] = {"status": "error", "message": str(result)}
                        else:
                            self._record_step(step["step_id"], result, results, completed, failed, skipped)

                # 串行执行
                for step in sequential_steps:
                    if task_id in self._cancelled:
                        break
                    try:
                        result = await self._execute_step(step, task)
                        self._record_step(step["step_id"], result, results, completed, failed, skipped)
                    except Exception as e:
                        logger.error("Step failed", step_id=step["step_id"], error=str(e))
                        # 重试一次
                        try:
                            await asyncio.sleep(1)
                            result = await self._execute_step(step, task)
                            self._record_step(step["step_id"], result, results, completed, failed, skipped)
                        except Exception as retry_error:
                            logger.error("Step retry failed", step_id=step["step_id"], error=str(retry_error))
                            failed.add(step["step_id"])
                            results[step["step_id"]] = {"status": "error", "message": str(retry_error)}

                # 更新进度
                task["progress"] = finished_count() / total_steps * 100.0
        except asyncio.CancelledError:
            # cancel_task() 取消了底层 asyncio.Task，这里收敛状态后正常返回
            self._cancelled.add(task_id)
            logger.info("Task execution coroutine cancelled", task_id=task_id)

        if task_id in self._cancelled:
            task["status"] = TaskStatus.CANCELLED.value
        elif failed or not completed:
            # 有步骤真正报错，或一步都没能成功执行（TaskStatus 无"部分成功"成员）
            task["status"] = TaskStatus.FAILED.value
        else:
            # 允许部分步骤因能力未实现而跳过，明细见 _results 的 skipped
            task["status"] = TaskStatus.COMPLETED.value
        task["progress"] = 100.0
        self._results[task_id] = {
            "results": results,
            "completed": sorted(completed),
            "failed": sorted(failed),
            "skipped": sorted(skipped),
            # 供前端直接展示的一行步摘要（只做格式化，不新增任何数据）
            "summary": self._summarize(results),
        }
        logger.info(
            "Task execution finished",
            task_id=task_id,
            status=task["status"],
            completed=len(completed),
            failed=len(failed),
            skipped=len(skipped),
        )

    @staticmethod
    def _summarize(results: dict[str, Any]) -> list[str]:
        """把每步的真实产出格式化为一行摘要

        仅做字符串化，不新增、不推断任何数据；数值直接取自步骤实际返回值。
        """
        lines: list[str] = []
        for step_id, payload in results.items():
            if not isinstance(payload, dict):
                lines.append(f"{step_id}｜{payload}")
                continue

            status = str(payload.get("status", "unknown"))
            status_cn = _STATUS_LABELS.get(status, status)
            who = (
                payload.get("agent_name")
                or payload.get("tool_name")
                or payload.get("agent_id")
                or payload.get("tool_id")
                or "系统"
            )
            action = payload.get("action") or ""
            action_cn = _ACTION_LABELS.get(action, action)
            # 动作名与执行者名称重复时只显示一次
            if action_cn and who and action_cn != who:
                head = f"{step_id}【{status_cn}】{action_cn} · {who}"
            else:
                head = f"{step_id}【{status_cn}】{action_cn or who}"

            detail = ""
            output = payload.get("output")
            warnings: list = []
            if isinstance(output, dict):
                values = output.get("results")
                if isinstance(values, dict) and values:
                    shown = list(values.items())[:8]
                    detail = _format_metrics(dict(shown))
                    if len(values) > len(shown):
                        detail += f"（其余 {len(values) - len(shown)} 项略）"
                elif output.get("message"):
                    detail = str(output["message"])
                warnings = output.get("warnings") or []
            if not detail and payload.get("reason"):
                detail = str(payload["reason"])
            if isinstance(warnings, list) and warnings:
                detail = (detail + "；" if detail else "") + "提示：" + "；".join(str(w) for w in warnings)

            lines.append(f"{head}｜{detail}" if detail else head)
        return lines

    @staticmethod
    def _record_step(
        step_id: str,
        result: Any,
        results: dict[str, Any],
        completed: set[str],
        failed: set[str],
        skipped: set[str],
    ) -> None:
        """按步骤返回状态归类：skipped/error/not_implemented 不计入成功"""
        results[step_id] = result
        status = result.get("status") if isinstance(result, dict) else None
        if status in ("skipped", "not_implemented"):
            # not_implemented = 能力尚未实现，属于"没能执行"而不是"执行失败"
            skipped.add(step_id)
            if status == "not_implemented" and isinstance(result, dict):
                # 把底层给出的具体原因透出，便于用户在任务详情里看到"缺什么"
                inner = result.get("output")
                reason = inner.get("message") if isinstance(inner, dict) else None
                results[step_id] = {**result, "reason": reason or "该能力尚未实现，步骤已跳过"}
        elif status in _STEP_FAILURE_STATUSES:
            failed.add(step_id)
        else:
            completed.add(step_id)

    async def _execute_step(self, step: dict, task: dict) -> Any:
        """执行单个步骤 — 真实派发给智能体或工具"""
        step_id = step["step_id"]
        action = step.get("action")
        agent_id = step.get("agent_id")
        tool_ids = list(step.get("tool_ids") or [])
        step_inputs = dict(step.get("inputs") or {})

        # 把上游步骤的产出并入本步输入，供下游步骤（如 PM 的结果聚合）消费
        step_results_all = task.get("step_results") or {}
        upstream = {
            dep: step_results_all[dep]
            for dep in (step.get("dependencies") or [])
            if dep in step_results_all
        }
        if upstream:
            step_inputs.setdefault("sub_results", upstream)
            step_inputs.setdefault("upstream", upstream)

        context = {
            "task_id": task.get("task_id"),
            "session_id": task.get("session_id"),
            "user_id": task.get("user_id"),
            "step_id": step_id,
            "action": action,
            "inputs": step_inputs,
            "step_results": task.get("step_results", {}),
        }
        logger.debug("Executing step", step_id=step_id, action=action, agent_id=agent_id, tool_ids=tool_ids)

        # 1) 优先派发给已注册智能体
        if agent_id:
            agent = await self.registry.get_agent_instance(agent_id)
            if agent is None:
                logger.warning("Agent not registered, step skipped", step_id=step_id, agent_id=agent_id)
                return {
                    "step_id": step_id,
                    "action": action,
                    "agent_id": agent_id,
                    "status": "skipped",
                    "reason": f"Agent '{agent_id}' 未在 AgentRegistry 中注册",
                }

            agent_task = {
                "task_id": f"{task.get('task_id')}:{step_id}",
                "action": action,
                "description": step.get("description", ""),
                "inputs": step_inputs,
                "expected_outputs": step.get("expected_outputs", []),
            }
            logger.info("Dispatching step to agent", step_id=step_id, agent_id=agent_id, action=action)
            output = await agent.handle_task(agent_task, context, self._build_callbacks(task))
            return {
                "step_id": step_id,
                "action": action,
                "agent_id": agent_id,
                "agent_name": agent.metadata.name,
                "status": output.get("status", "completed") if isinstance(output, dict) else "completed",
                "output": output,
            }

        # 2) 其次派发给第一个已注册的工具
        if tool_ids:
            if self.tool_registry is None:
                return {
                    "step_id": step_id,
                    "action": action,
                    "tool_ids": tool_ids,
                    "status": "skipped",
                    "reason": "TaskExecutor 未注入 ToolRegistry",
                }
            for tool_id in tool_ids:
                tool = await self.tool_registry.get_tool(tool_id)
                if tool is None:
                    logger.warning("Tool not registered, trying next", step_id=step_id, tool_id=tool_id)
                    continue
                logger.info("Dispatching step to tool", step_id=step_id, tool_id=tool_id)
                output = await self.tool_registry.execute_tool(tool_id, step_inputs, context)
                return {
                    "step_id": step_id,
                    "action": action,
                    "tool_id": tool_id,
                    "tool_name": tool.manifest.name,
                    "status": output.get("status", "completed") if isinstance(output, dict) else "completed",
                    "output": output,
                }
            return {
                "step_id": step_id,
                "action": action,
                "tool_ids": tool_ids,
                "status": "skipped",
                "reason": f"tool_ids {tool_ids} 均未在 ToolRegistry 中注册",
            }

        # 3) 无派发目标
        return {
            "step_id": step_id,
            "action": action,
            "status": "skipped",
            "reason": "步骤未指定 agent_id 或 tool_ids，无可派发目标",
        }

    def _build_callbacks(self, task: dict) -> AgentCallbacks:
        """构造智能体回调 — 进度/消息/错误统一进入结构化日志"""
        task_id = task.get("task_id")

        async def on_progress(progress_task_id: str, progress: float) -> None:
            logger.debug("Agent progress", task_id=progress_task_id or task_id, progress=progress)

        async def on_message(message_task_id: str, message: str) -> None:
            logger.info("Agent message", task_id=message_task_id or task_id, message=message)

        async def on_error(error_task_id: str, error: str) -> None:
            logger.error("Agent error", task_id=error_task_id or task_id, error=error)

        return AgentCallbacks(on_progress=on_progress, on_message=on_message, on_error=on_error)

    async def list_tasks(self) -> list[dict]:
        """列出内存中的任务（最新在前）"""
        items = []
        for task_id, task in reversed(list(self._tasks.items())):
            items.append(
                {
                    "task_id": task_id,
                    "title": task.get("title", ""),
                    "intent": task.get("intent", ""),
                    "status": task.get("status", TaskStatus.PENDING.value),
                    "progress": task.get("progress", 0.0),
                    "steps_total": len(task.get("steps", [])),
                    "created_at": task.get("created_at", ""),
                    "session_id": task.get("session_id", ""),
                }
            )
        return items

    async def get_status(self, task_id: str) -> dict | None:
        """获取任务状态"""
        task = self._tasks.get(task_id)
        if not task:
            return None
        return {
            "task_id": task_id,
            "status": task.get("status", "unknown"),
            "progress": task.get("progress", 0.0),
            "result": self._results.get(task_id),
            "error": task.get("error"),
            "steps": task.get("steps", []),
        }

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务 — 置取消标记并中断后台执行协程"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        self._cancelled.add(task_id)
        task["status"] = TaskStatus.CANCELLED.value
        background = self._running.get(task_id)
        if background is not None and not background.done():
            background.cancel()
        logger.info("Task cancelled", task_id=task_id)
        return True
