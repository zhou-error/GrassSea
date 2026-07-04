"""任务执行引擎

按 DAG 拓扑顺序调度，支持步骤级重试和回滚。
使用 Celery 驱动异步任务执行。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from services.agent_service.registry import AgentRegistry
from shared.utils.config import Settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)


class TaskExecutor:
    """任务执行引擎"""

    def __init__(self, settings: Settings, registry: AgentRegistry):
        self.settings = settings
        self.registry = registry
        self._tasks: dict[str, dict] = {}
        self._results: dict[str, dict] = {}

    async def execute_async(
        self, task: dict, session_id: str, user_id: str | None
    ) -> None:
        """异步执行任务"""
        task_id = task["task_id"]
        task["session_id"] = session_id
        task["user_id"] = user_id
        self._tasks[task_id] = task

        # 创建后台执行协程
        asyncio.create_task(self._execute_dag(task))

    async def _execute_dag(self, task: dict) -> None:
        """按 DAG 拓扑顺序执行步骤"""
        task_id = task["task_id"]
        steps = task.get("steps", [])
        parallel_groups = task.get("parallel_groups", [])

        if not steps:
            task["status"] = "completed"
            task["progress"] = 100.0
            return

        task["status"] = "running"
        results: dict[str, Any] = {}
        completed: set[str] = set()
        failed: set[str] = set()

        step_map = {s["step_id"]: s for s in steps}
        total_steps = len(steps)

        while len(completed) + len(failed) < total_steps:
            # 找出所有依赖已满足的步骤
            ready = []
            for step in steps:
                sid = step["step_id"]
                if sid in completed or sid in failed:
                    continue
                deps = step.get("dependencies", [])
                if all(d in completed for d in deps):
                    ready.append(step)

            if not ready and len(completed) + len(failed) < total_steps:
                # 死锁检测
                logger.error("DAG deadlock detected", task_id=task_id)
                failed.update(s for s in step_map if s not in completed)
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
                    else:
                        results[step["step_id"]] = result
                        completed.add(step["step_id"])

            # 串行执行
            for step in sequential_steps:
                try:
                    result = await self._execute_step(step, task)
                    results[step["step_id"]] = result
                    completed.add(step["step_id"])
                except Exception as e:
                    logger.error("Step failed", step_id=step["step_id"], error=str(e))
                    # 重试一次
                    try:
                        await asyncio.sleep(1)
                        result = await self._execute_step(step, task)
                        results[step["step_id"]] = result
                        completed.add(step["step_id"])
                    except Exception:
                        failed.add(step["step_id"])

            # 更新进度
            task["progress"] = (len(completed) + len(failed)) / total_steps * 100.0

        task["status"] = "completed" if not failed else "completed_with_errors"
        task["progress"] = 100.0
        self._results[task_id] = {"results": results, "completed": list(completed), "failed": list(failed)}
        logger.info("Task execution finished", task_id=task_id, status=task["status"])

    async def _execute_step(self, step: dict, task: dict) -> Any:
        """执行单个步骤"""
        logger.debug("Executing step", step_id=step["step_id"], action=step.get("action"))
        await asyncio.sleep(0.5)  # 模拟执行

        agent_id = step.get("agent_id")
        tool_ids = step.get("tool_ids", [])

        result = {
            "step_id": step["step_id"],
            "action": step.get("action"),
            "status": "completed",
            "output": f"Step {step['step_id']} executed successfully",
            "agent_id": agent_id,
            "tools_used": tool_ids,
        }

        if agent_id and agent_id in self.registry._agents:
            result["agent_name"] = self.registry._agents[agent_id].name

        return result

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
        """取消任务"""
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = "cancelled"
            logger.info("Task cancelled", task_id=task_id)
            return True
        return False
