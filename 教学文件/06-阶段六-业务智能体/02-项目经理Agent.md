# 02 - 项目经理 Agent

## 学习目标

1. 理解 PM Agent 的三大核心能力：任务分解、资源分配、进度聚合
2. 掌握如何根据 action 字段分发任务到不同的处理方法
3. 能设计一个简单的任务分解 Agent
4. 理解 PM Agent 在 Multi-Agent 编排中的"指挥"角色

## 前置知识

- Python 类继承（上一节 BaseAgent 的内容）
- 字典操作和列表处理
- 了解 DAG 任务分解的概念

## 概念讲解

### PM Agent 的角色定位

在 GrassSea 的多智能体架构中，PM Agent 是"总指挥"——不自己做专业计算，而是负责：

```
用户的需求
     │
     ▼
┌─────────────────────────────────────────────┐
│              PM Agent（项目经理）             │
│                                             │
│  ① 任务分解: "稳性分析" → 4个步骤           │
│     ├─ step_1: 解析型值表                    │
│     ├─ step_2: 静水力计算                    │
│     ├─ step_3: 稳性分析                      │
│     └─ step_4: 生成报告                      │
│                                             │
│  ② 资源分配: 每个步骤分配给谁？              │
│     step_1 → Naval Arch Agent               │
│     step_2 → Naval Arch Agent               │
│     step_3 → Naval Arch Agent               │
│     step_4 → Doc Agent                      │
│                                             │
│  ③ 进度聚合: 汇总各 Agent 的结果             │
│     "静水力计算完成 ✓ 稳性分析完成 ✓          │
│      报告生成中..."                          │
└─────────────────────────────────────────────┘
```

### PM Agent 的工作流

```
         ┌─────────────┐
         │ 接收任务     │
         └──────┬──────┘
                │
                ▼
      ┌───────────────────┐
      │ 分析 action 字段   │
      │ "decompose" ?     │──→ _decompose_task()   → 返回 DAG
      │ "allocate" ?      │──→ _allocate_resources() → 返回分配方案
      │ "aggregate" ?     │──→ _aggregate_results() → 返回汇总报告
      └───────────────────┘
```

`action` 字段是标准化的任务类型标识，让 PM Agent 知道"这次轮到你做什么"。

## 项目代码精讲

打开 `agents/pm_agent/agent.py`。

### 元数据定义

```python
PM_AGENT_METADATA = AgentMetadata(
    agent_id="pm_agent",
    name="项目经理 Agent",
    role="负责任务分解、资源分配、进度跟踪、风险识别",
    capabilities=[
        AgentCapability(
            name="task_decomposition",
            description="将用户需求分解为标准化的任务步骤 DAG",
            input_schema={
                "type": "object",
                "properties": {"requirement": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"dag": {"type": "object"}},
            },
            tools=[],
            estimated_latency_ms=500,
        ),
        AgentCapability(
            name="resource_allocation",
            description="根据任务类型分配合适的智能体和工具",
            tools=[],
        ),
        AgentCapability(
            name="progress_aggregation",
            description="聚合各子任务的执行结果，生成总体进度报告",
            tools=["report_gen"],
            estimated_latency_ms=800,
        ),
    ],
    model_preference="deepseek-chat",
    max_concurrent_tasks=10,  # PM 不重计算，可以并发很多
    version="0.1.0",
)
```

三个能力分别对应 PM 的核心职责。`estimated_latency_ms` 较小（500-800ms），因为 PM 主要是逻辑判断和调度，不涉及重型计算。

### 任务分发

```python
class PMAgent(BaseAgent):
    async def handle_task(self, task, context, callbacks) -> dict:
        action = task.get("action", "")

        if "decompose" in action:
            return await self._decompose_task(task, context, callbacks)
        elif "allocate" in action:
            return await self._allocate_resources(task, context, callbacks)
        elif "aggregate" in action:
            return await self._aggregate_results(task, context, callbacks)
        else:
            # 默认：尝试分解任务
            return await self._decompose_task(task, context, callbacks)
```

使用子串匹配（`"decompose" in action`）而非精确匹配，增加了容错性。最后的 else 分支是一个合理的默认行为。

### 任务分解

```python
async def _decompose_task(self, task, context, callbacks) -> dict:
    """分解任务为 DAG"""
    requirement = task.get("inputs", {}).get("requirement",
                    task.get("description", ""))

    return {
        "status": "completed",
        "dag": {
            "steps": [
                {"step_id": "s1", "action": "parse",
                 "description": "解析输入"},
                {"step_id": "s2", "action": "analyze",
                 "description": "分析需求", "dependencies": ["s1"]},
                {"step_id": "s3", "action": "execute",
                 "description": "执行任务", "dependencies": ["s2"]},
                {"step_id": "s4", "action": "report",
                 "description": "生成结果", "dependencies": ["s3"]},
            ]
        },
        "summary": f"已将需求分解为 4 个步骤: {requirement[:100]}",
    }
```

这是简化版的任务分解（4 步通用模板）。生产环境应该结合 LLM 做更智能的分解——根据实际需求生成不同数量、不同类型的步骤。

### 资源分配

```python
async def _allocate_resources(self, task, context, callbacks) -> dict:
    task_info = task.get("inputs", {}).get("task", {})
    return {
        "status": "completed",
        "assignments": [
            {"agent_id": "naval_arch_agent",
             "reason": "涉及船舶专业计算"},
            {"tool_ids": ["hydrostatics", "stability"],
             "reason": "需要静水力和稳性分析"},
        ],
    }
```

资源分配的结果是一个分配列表，指明了"谁来做什么，用什么工具"。

### 进度聚合

```python
async def _aggregate_results(self, task, context, callbacks) -> dict:
    sub_results = task.get("inputs", {}).get("sub_results", [])
    return {
        "status": "completed",
        "summary": f"聚合了 {len(sub_results)} 个子任务的结果",
        "overall_status": (
            "success"
            if all(r.get("status") == "completed" for r in sub_results)
            else "partial"
        ),
    }
```

`overall_status` 的判断逻辑：只有当所有子任务都成功时，整体状态才是 success。有一个失败就是 partial（部分完成）。

## 手把手实践

### 实验：让 PM Agent 分解你的需求

```python
# pm_demo.py
import asyncio
from agents.pm_agent.agent import PMAgent
from shared.protocols.agent import AgentCallbacks

async def main():
    pm = PMAgent()
    task = {
        "action": "decompose",
        "inputs": {
            "requirement": "对一艘150m散货船进行完整稳性分析并生成审查报告"
        }
    }

    result = await pm.handle_task(task, {}, AgentCallbacks())
    print("分解结果:")
    for step in result["dag"]["steps"]:
        deps = step.get("dependencies", [])
        dep_str = f" (依赖: {', '.join(deps)})" if deps else ""
        print(f"  {step['step_id']}: {step['description']}{dep_str}")

asyncio.run(main())
```

### 实验：自己写一个聚合逻辑

```python
# 模拟子任务结果
sub_results = [
    {"step_id": "s1", "status": "completed", "output": "型值表解析成功"},
    {"step_id": "s2", "status": "completed", "output": "排水量12500吨"},
    {"step_id": "s3", "status": "failed", "output": "稳性计算超时"},
]

# 实现你的聚合逻辑
def aggregate(results):
    total = len(results)
    succeed = sum(1 for r in results if r["status"] == "completed")
    failed = sum(1 for r in results if r["status"] == "failed")
    return {
        "total_steps": total,
        "succeed": succeed,
        "failed": failed,
        "completion_rate": f"{succeed/total*100:.1f}%",
    }

print(aggregate(sub_results))
```

## 视频学习资源

请在 B站（bilibili.com）自行搜索以下关键词：

- "Multi-Agent 多智能体 协作架构" -- 理解多智能体系统
- "项目经理 AI Agent 自动任务分解" -- 了解任务分解
- "工作流编排 任务调度 设计模式" -- 理解编排设计

## 常见问题与排错

**Q1：PM Agent 的任务分解太简单了，只有 4 步固定模板？**

A：是的，当前是简化版本。真实场景中 PM Agent 应该调用 LLM 进行动态分解（参考 planner.py 中的 `_llm_plan` 方法）。4 步模板只是兜底方案。

**Q2：PM Agent 的 `max_concurrent_tasks=10` 是不是太高了？**

A：PM Agent 的主要工作只是"思考和分发"，计算量极低。10 个并发意味着同时管理 10 个大项目——对项目经理来说合情合理。

**Q3：如果 PM Agent 分配给某个 Agent 的任务失败了怎么办？**

A：当前简化实现没有处理这个场景。完整的实现需要 PM Agent 做"异常重新分配"：检测失败后，选择备用 Agent 重试，或调整后续步骤的依赖关系。

## 练习任务

1. **代码题**：修改 `_decompose_task`，使其根据 requirement 中的关键词生成不同数量的步骤（如包含"审查"关键词时增加到 5 步，增加一步审查验证）。
2. **设计题**：为 PM Agent 新增一个 `risk_assessment` 能力（风险评估），设计其 input_schema 和 output_schema。
3. **分析题**：`_aggregate_results` 中 `all(r.get("status") == "completed")` 的判断是否有漏洞？（提示：如果 sub_results 为空列表会怎样？）
4. **综合题**：设想 PM Agent 收到任务"设计一艘新船并生成全套图纸和报告"，它会如何分解？请写出一个 5 步骤以上的 DAG 方案。
