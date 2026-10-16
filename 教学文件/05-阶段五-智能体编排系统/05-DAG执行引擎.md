# 05 - DAG 执行引擎

## 学习目标

1. 理解拓扑排序在 DAG 执行中的应用
2. 掌握并行调度和串行执行的切换逻辑
3. 了解重试机制和超时控制的实现
4. 能读懂并修改 DAG 执行引擎代码

## 前置知识

- Python 的 `asyncio`（异步编程）
- DAG 的基本概念（上一节内容）
- 字典、列表、集合的操作

## 概念讲解

### DAG 执行的三个核心问题

```
问题一：执行顺序
  step_2 依赖 step_1 → step_1 必须先执行
  step_3 依赖 step_1 和 step_2 → 两者都完成才能开始

问题二：并行识别
  step_2a 和 step_2b 都不互相依赖 → 可以同时执行

问题三：异常处理
  step_2 失败了 → 重试？跳过？终止整个 DAG？
```

### 拓扑排序式的执行

```
DAG 步骤：
  step_1: 无依赖
  step_2a: 依赖 step_1
  step_2b: 依赖 step_1
  step_3: 依赖 step_2a, step_2b

执行时间线：
────────────────────────────────────────────►
t=0     t=1     t=2     t=3     t=4     t=5
│       │       │       │       │       │
[step_1]        │       │       │       │
        ┌───────┴───────┐       │       │
        │               │       │       │
   [step_2a]      [step_2b]     │       │
        │               │       │       │
        └───────┬───────┘       │       │
                │               │       │
                │          [step_3]    │
                │               │       │
                │               └───────┘
                
本轮执行: step_1 → {step_2a, step_2b} → step_3
```

每一轮找出"所有依赖已满足且尚未执行"的步骤，能并行的并行，不能的串行。

### 重试机制

```
正常执行:  step ──► 成功
                   
带重试:    step ──► 失败 ──► 等待1秒 ──► 重试 ──► 成功
                   
重试也失败: step ──► 失败 ──► 重试 ──► 失败 ──► 标记为 failed
                                                    │
                                          ┌─────────┘
                                          ▼
                                    下游步骤无法执行
                                    （依赖未满足）
```

## 项目代码精讲

打开 `services/agent_service/executor.py`。

### TaskExecutor 架构

```python
class TaskExecutor:
    def __init__(self, settings: Settings, registry: AgentRegistry):
        self.settings = settings
        self.registry = registry
        self._tasks: dict[str, dict] = {}        # 任务存储
        self._results: dict[str, dict] = {}      # 结果存储
```

`_tasks` 和 `_results` 是内存字典，开发阶段够用。生产环境应接入持久化存储（MongoDB 或 PostgreSQL）。

### 核心执行循环：_execute_dag

```python
async def _execute_dag(self, task: dict) -> None:
    task_id = task["task_id"]
    steps = task.get("steps", [])
    parallel_groups = task.get("parallel_groups", [])

    task["status"] = "running"
    results: dict[str, Any] = {}
    completed: set[str] = set()
    failed: set[str] = set()

    step_map = {s["step_id"]: s for s in steps}
    total_steps = len(steps)

    while len(completed) + len(failed) < total_steps:
        # 1. 找所有依赖已满足的步骤
        ready = []
        for step in steps:
            sid = step["step_id"]
            if sid in completed or sid in failed:
                continue
            deps = step.get("dependencies", [])
            if all(d in completed for d in deps):   # ← 关键行
                ready.append(step)
```

**`all(d in completed for d in deps)`** 是核心判断：只有当步骤的所有依赖都已完成，该步骤才进入 ready 列表。

### 死锁检测

```python
        # 2. 死锁检测
        if not ready and len(completed) + len(failed) < total_steps:
            # 有未完成的步骤，但没有可执行的步骤 → 死锁
            logger.error("DAG deadlock detected", task_id=task_id)
            failed.update(s for s in step_map if s not in completed)
            break
```

死锁场景：step_2 依赖 step_1，但 step_1 失败了。step_1 既不在 completed 也不在 failed（如果遗漏了标记），导致 step_2 永远不能开始。死锁检测确保程序不会无限等待。

### 并行与串行分离

```python
        # 3. 检查并行组：分离并行步骤和串行步骤
        parallel_steps = []
        sequential_steps = []
        for s in ready:
            in_parallel = any(s["step_id"] in g for g in parallel_groups)
            if in_parallel:
                parallel_steps.append(s)
            else:
                sequential_steps.append(s)

        # 4. 并行执行（asyncio.gather）
        if parallel_steps:
            parallel_tasks = [
                self._execute_step(s, task) for s in parallel_steps
            ]
            parallel_results = await asyncio.gather(
                *parallel_tasks, return_exceptions=True
            )
            for step, result in zip(parallel_steps, parallel_results):
                if isinstance(result, Exception):
                    failed.add(step["step_id"])
                else:
                    results[step["step_id"]] = result
                    completed.add(step["step_id"])

        # 5. 串行执行（带重试）
        for step in sequential_steps:
            try:
                result = await self._execute_step(step, task)
                results[step["step_id"]] = result
                completed.add(step["step_id"])
            except Exception as e:
                # 重试一次
                try:
                    await asyncio.sleep(1)
                    result = await self._execute_step(step, task)
                    results[step["step_id"]] = result
                    completed.add(step["step_id"])
                except Exception:
                    failed.add(step["step_id"])
```

**`asyncio.gather(*parallel_tasks, return_exceptions=True)`** 是关键：
- `*parallel_tasks` 将列表展开为多个参数
- `return_exceptions=True` 确保某个步骤失败时不影响其他并行步骤
- 返回值与输入顺序一致，可以用 `zip()` 映射回去

### 进度更新

```python
        # 6. 更新进度
        task["progress"] = (len(completed) + len(failed)) / total_steps * 100.0

    # 所有步骤执行完毕
    task["status"] = "completed" if not failed else "completed_with_errors"
    task["progress"] = 100.0
```

进度百分比随完成和失败步骤的总数线性增长。`completed_with_errors` 状态允许部分失败，下游可以根据此状态决定是展示完整结果还是附带警告。

### 单步执行（模拟）

```python
async def _execute_step(self, step: dict, task: dict) -> Any:
    """执行单个步骤（当前为模拟实现）"""
    logger.debug("Executing step", step_id=step["step_id"])
    await asyncio.sleep(0.5)  # 模拟执行耗时

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

    # 如果指定了 Agent，附加 Agent 名称
    if agent_id and agent_id in self.registry._agents:
        result["agent_name"] = self.registry._agents[agent_id].name

    return result
```

当前是模拟实现。生产环境中，这里应该：
1. 根据 `agent_id` 从 registry 获取 Agent 实例
2. 调用 `agent.handle_task(step, context, callbacks)`
3. 将返回结果存入 results

### 任务管理

```python
async def get_status(self, task_id: str) -> dict | None:
    """查询任务状态"""
    task = self._tasks.get(task_id)
    if not task:
        return None
    return {
        "task_id": task_id,
        "status": task.get("status"),
        "progress": task.get("progress", 0.0),
        "result": self._results.get(task_id),
    }

async def cancel_task(self, task_id: str) -> bool:
    """取消任务"""
    if task_id in self._tasks:
        self._tasks[task_id]["status"] = "cancelled"
        return True
    return False
```

取消是"软取消"——只标记状态，不中断正在执行的协程。真正的硬取消需要用到 `asyncio.Task.cancel()`。

## 手把手实践

### 实验：拓扑排序执行模拟

```python
# dag_simulator.py -- 理解 DAG 执行
import asyncio

async def simulate_step(name, deps, completed):
    """模拟一个执行步骤"""
    # 等待依赖完成
    for dep in deps:
        while dep not in completed:
            await asyncio.sleep(0.1)
    print(f"[开始] {name}")
    await asyncio.sleep(1)  # 模拟工作
    print(f"[完成] {name}")
    completed.add(name)

async def main():
    completed = set()

    # 定义步骤：(名称, 依赖列表)
    steps = [
        ("A解析数据", []),
        ("B检索规范", []),
        ("C稳性计算", ["A解析数据"]),
        ("D合规审查", ["B检索规范", "C稳性计算"]),
    ]

    tasks = [
        asyncio.create_task(simulate_step(name, deps, completed))
        for name, deps in steps
    ]
    await asyncio.gather(*tasks)

asyncio.run(main())
```

观察输出：B检索规范 和 A解析数据 会同时开始（无依赖），C稳性计算 等 A完成，D合规审查 等 B和C都完成。

## 视频学习资源

请在 B站（bilibili.com）自行搜索以下关键词：

- "Python asyncio 异步编程 实战" -- 深入理解异步
- "DAG 任务调度 拓扑排序 算法" -- 理解拓扑排序
- "任务编排 工作流引擎 原理" -- 了解工作流引擎

## 常见问题与排错

**Q1：`_execute_step` 是模拟的，怎么接入真实 Agent？**

A：在 `_execute_step` 中增加 Agent 调用逻辑：
```python
if agent_id:
    agent_instance = get_agent_instance(agent_id)  # 从注册中心获取
    result = await agent_instance.handle_task(step, task, callbacks)
    return result
```

**Q2：如果步骤需要 10 分钟才能完成怎么办？**

A：当前设计有两个问题：
1. `asyncio.sleep(0.5)` 是假的，真实长任务会阻塞事件循环
2. 没有超时控制（TaskStep 里的 timeout 字段未使用）

改进方案：使用 `asyncio.wait_for(coro, timeout=step.get("timeout", 300))` 包装每个步骤，超时后抛出 `asyncio.TimeoutError`。

**Q3：为什么串行步骤有重试而并行步骤没有？**

A：设计选择。可以为并行步骤也添加重试，但并行重试更难管理。当前保守策略是：并行优先保证整体进度，串行允许更多容错。

## 练习任务

1. **代码题**：为 `_execute_step` 增加超时控制，使用 `asyncio.wait_for` 包装，超时时间从 `step["timeout"]` 读取。
2. **分析题**：`cancel_task` 只是标记状态，不会真正停止执行。设计一个方案来真正取消正在运行的步骤（提示：使用 `asyncio.Task` 的 `cancel()` 方法）。
3. **实践题**：在 `_execute_dag` 中添加日志输出，每次完成或失败一个步骤时打印当前进度。
4. **综合题**：当前执行引擎把所有结果存在内存字典中。如果服务重启，所有任务状态丢失。设计一个持久化方案（提示：考虑 MongoDB 文档存储或 PostgreSQL）。
