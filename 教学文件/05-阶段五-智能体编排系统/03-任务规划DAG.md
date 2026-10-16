# 03 - 任务规划 DAG

## 学习目标

1. 理解 DAG（有向无环图）在任务分解中的应用
2. 掌握 ReAct 模式和 Prompt 工程在规划中的运用
3. 能读懂 TaskStep 和 TaskDAG 数据结构
4. 了解规则规划 vs LLM 规划的区别

## 前置知识

- Python 数据类（dataclass）
- 基本图论概念（节点、边、依赖）
- 了解什么是 Prompt 工程

## 概念讲解

### 什么是 DAG（有向无环图）？

在任务规划中，DAG 描述的是"哪些步骤必须先做，哪些可以并行"。

```
                    简单任务的 DAG
                   ════════════════

                   ┌─────────────┐
                   │  接收设计参数  │  ← 入口节点（无依赖）
                   └──────┬──────┘
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
      ┌──────────┐ ┌──────────┐ ┌──────────┐
      │ 参数完整性 │ │ 规范条文   │ │ 型值表    │  ← 可并行执行
      │   检查    │ │   检索    │ │   解析    │
      └────┬─────┘ └────┬─────┘ └────┬─────┘
           │            │            │
           └────────────┼────────────┘
                        │
                        ▼
                 ┌──────────────┐
                 │   结果聚合     │  ← 依赖前面所有步骤
                 └──────┬───────┘
                        ▼
                 ┌──────────────┐
                 │ 综合报告生成   │  ← 最终节点
                 └──────────────┘

关键词：
  有向（Directed）：箭头有方向，A → B 表示 A 必须先于 B
  无环（Acyclic）：不能形成循环（A → B → C → A 是非法的）
  图（Graph）：由节点（步骤）和边（依赖）组成的结构
```

### ReAct 模式

ReAct = Reasoning（推理）+ Acting（执行）。是让 LLM 交替进行"思考下一步做什么"和"执行这一步"的模式：

```
ReAct 循环示例：

[推理] "用户要分析稳性，我需要：1)解析型值表 2)静水力计算 3)稳性分析"
[执行] 调用 xlsx_parser 解析型值表
[推理] "型值表解析完成，现在可以进行静水力计算了"
[执行] 调用 hydrostatics 工具
[推理] "静水力计算完成，排水量12500吨，现在进行稳性分析"
[执行] 调用 stability 工具
[推理] "所有计算完成，汇总结果生成报告"
[执行] 调用 report_gen 工具
```

### 规则规划 vs LLM 规划

```
规则规划：
┌────────────────────────────────────────────┐
│ 关键词匹配 → 套用预设模板                    │
│ "稳性" → [解析型值表, 静水力, 稳性, 报告]    │
│                                            │
│ 优点：快（毫秒级）、100% 可预测              │
│ 缺点：只能处理预设场景，无法应对新需求        │
└────────────────────────────────────────────┘

LLM 规划：
┌────────────────────────────────────────────┐
│ LLM 理解需求 → 动态生成步骤 DAG             │
│ "分析这艘船的燃油消耗并对比同类型船"          │
│ → LLM 自己分解为：[数据收集, 油耗计算,       │
│    同类船检索, 对比分析, 报告]               │
│                                            │
│ 优点：灵活、能处理新场景                     │
│ 缺点：慢（秒级）、可能出错（需要校验）        │
└────────────────────────────────────────────┘
```

GrassSea 使用规则规划处理常见场景（稳性计算、型线绘制），对复杂/多智能体任务使用 LLM 规划。

## 项目代码精讲

打开 `services/agent_service/planner.py`。

### 数据结构

```python
@dataclass
class TaskStep:
    step_id: str                              # "step_1"
    action: str                               # "hydrostatics"
    description: str                          # "静水力计算"
    inputs: dict = field(default_factory=dict)  # {"L": 100, "B": 15, ...}
    expected_outputs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # ["step_1"]
    timeout: int = 300                        # 超时秒数
    agent_id: str | None = None               # 分配哪个 Agent
    tool_ids: list[str] = field(default_factory=list)     # 需要哪些工具


@dataclass
class TaskDAG:
    task_id: str                              # "task_a1b2c3d4e5f6"
    title: str                                # "稳性计算与报告生成"
    steps: list[TaskStep]                     # 步骤列表
    parallel_groups: list[list[str]]          # [["step_2", "step_3"]]
```

**parallel_groups 的设计**：

```python
# 表示 step_2a 和 step_2b 可以同时执行
parallel_groups = [["step_2a", "step_2b"]]

# 而 step_1 必须在它们之前（因为 dependencies 里有 "step_1"）
# step_3 必须在它们之后（因为 step_3 的 dependencies 里有 "step_2a" 和 "step_2b"）
```

### 规则规划

```python
def _rule_based_plan(self, message: str, intent: IntentResult) -> list[TaskStep]:
    if intent.intent_type == IntentType.TOOL_CALL:
        # 工具调用通常是单步
        tool = self._infer_tool(message)
        steps.append(TaskStep(
            step_id="step_1",
            action="tool_execute",
            description=f"执行工具: {tool}",
            tool_ids=[tool],
            timeout=120,
        ))

    elif intent.intent_type == IntentType.PROFESSIONAL_TASK:
        # 根据关键词匹配预设模板
        if any(kw in message for kw in ["稳性", "stability"]):
            steps = [
                TaskStep("step_1", "parse_input", "解析输入数据（型值表）",
                         tool_ids=["xlsx_parser"], timeout=60),
                TaskStep("step_2", "hydrostatics", "静水力计算",
                         tool_ids=["hydrostatics"], dependencies=["step_1"], timeout=120),
                TaskStep("step_3", "stability", "稳性分析",
                         tool_ids=["stability"], dependencies=["step_2"], timeout=120),
                TaskStep("step_4", "generate_report", "生成计算报告",
                         tool_ids=["report_gen"], dependencies=["step_3"], timeout=60),
            ]
```

这套规则模板覆盖了 GrassSea 最常见的船舶工程场景。每个模板都指定了依赖关系、工具 ID 和超时时间。

### LLM 规划

```python
PLANNING_SYSTEM_PROMPT = """你是 GrassSea AI 的任务规划器。
将用户请求分解为可执行的步骤 DAG。

## 可用的智能体
- pm_agent: 项目经理
- naval_arch_agent: 船舶工程师
- cad_agent: CAD Agent
- review_agent: 审查 Agent
- research_agent: 研究员
- doc_agent: 文档工程师

## 可用的工具
- reg_check, hydrostatics, stability, resistance,
  cad_draw, xlsx_parser, pdf_parser, report_gen, web_search
"""
```

这个 Prompt 明确告诉 LLM"你能指挥哪些兵种"和"你有什么武器"。LLM 据此生成合理的步骤安排。

```python
async def _llm_plan(self, message: str) -> dict:
    resp = await client.post(
        f"{self.settings.DEEPSEEK_BASE_URL}/v1/chat/completions",
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
                {"role": "user", "content": f"请为以下用户请求规划任务:\n{message}"},
            ],
            "max_tokens": 2048,
            "temperature": 0.3,  # 规划需要确定性
        },
    )
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    # 从 LLM 回复中提取 JSON
    json_match = re.search(r"\{[\s\S]*\}", content)
    if json_match:
        return json.loads(json_match.group())
```

**`re.search(r"\{[\s\S]*\}", content)`** 是一个经典技巧：当 LLM 返回的 JSON 前后可能包含解释性文字时，用正则提取出纯 JSON 部分。

### 工具推断

```python
def _infer_tool(self, message: str) -> str | None:
    """从消息关键词推断需要什么工具"""
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
```

这是一个倒排索引的简单应用：每个工具关联一组触发词，匹配到就选中。

## 手把手实践

### 实验一：用笔画出 DAG

给以下任务需求画出 DAG 步骤图：

```
用户需求："根据型值表进行阻力计算，并与同类型散货船对比，
          生成对比分析报告。"
```

提示：步骤可能包括 - 解析型值表、阻力计算、检索同类型船数据、对比分析、生成报告。标注哪些可以并行。

### 实验二：手写 DAG JSON

按照 `PLANNING_SYSTEM_PROMPT` 要求的 JSON 格式，为上面的任务编写一个完整的 JSON：

```json
{
  "title": "阻力计算与同类型对比分析",
  "steps": [
    {
      "step_id": "step_1",
      "action": "...",
      "description": "...",
      "dependencies": [],
      "tool_ids": [...]
    }
    // ... 补充更多步骤
  ],
  "parallel_groups": [["step_?", "step_?"]],
  "summary": "..."
}
```

## 视频学习资源

请在 B站（bilibili.com）自行搜索以下关键词：

- "DAG 有向无环图 任务调度" -- 理解 DAG 概念
- "ReAct 模式 AI Agent 推理与行动" -- 学习 ReAct
- "Prompt工程 Chain of Thought" -- 理解思维链提示

## 常见问题与排错

**Q1：规则模板覆盖不了的场景怎么办？**

A：当前的 `_rule_based_plan` 中有一个 else 分支作为兜底：
```python
else:
    steps = [
        TaskStep("step_1", "analyze", "分析需求", timeout=60),
        TaskStep("step_2", "execute", "执行计算/分析", timeout=300),
    ]
```
这是一个通用两步骤模板，虽然不够精确，但至少能跑通。更好的方案是启用 LLM 规划。

**Q2：LLM 返回的步骤不合理怎么办？**

A：目前代码中缺少 LLM 规划结果的校验。生产环境应该增加：
- JSON Schema 验证（确保返回格式正确）
- 步骤依赖闭环检测（没有循环依赖）
- 工具/Agent 存在性检查（引用的 tool_id 确实存在）

**Q3：`parallel_groups` 如果和 `dependencies` 冲突怎么办？**

A：执行引擎（executor.py）会按 dependencies 优先：即使步骤在 parallel_groups 中，如果它的依赖还没完成，也不会开始执行。这是安全的。

## 练习任务

1. **概念题**：解释"有向"和"无环"分别是什么意思，为什么任务规划必须是无环的。
2. **代码题**：在 `_rule_based_plan` 中新增一个"船型改造"的模板（提示：步骤包括解析母型船参数、变换计算、新船型评估）。
3. **分析题**：`_infer_tool` 中使用 `any(kw in message for kw in keywords)` 来匹配。如果用户说"这个表格里有静水力数据，帮我分析"，会匹配到哪个工具？这正确吗？
4. **思考题**：如果同一个步骤需要调用多个工具（如先解析 PDF 再审查规范），当前 TaskStep 的数据结构如何支持？`tool_ids: list[str]` 表示多个工具是串行调用还是并行调用？
