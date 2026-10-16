# 04 - 审查与 CAD Agent

## 学习目标

1. 理解 Review Agent 的规范条文匹配和合规标注机制
2. 了解 CAD Agent 的图纸绘制和解析能力
3. 掌握审查结果的数据结构设计（violations、suggestions）
4. 理解两个 Agent 在任务流程中的协作关系

## 前置知识

- Python 类继承和字典操作
- 了解 Agent 基类的使用
- 不需要 CAD 专业知识——本节会解释相关概念

## 概念讲解

### Review Agent：规范条文的"守门员"

Review Agent 的职责是拿着规范条文去"挑刺"——检查设计参数是否符合相关标准。

```
设计参数                   规范条文                 审查结果
────────                  ────────                ────────
舱壁间距=500mm    vs    CCS §2.5.3: ≥600mm  →  ✗ 不通过
                                              违规: 500mm < 600mm
                                              建议: 增大至 ≥600mm

GM=2.34m          vs    IMO: ≥0.15m         →  ✓ 通过

结构板厚=8mm      vs    DNV: ≥10mm          →  ✗ 不通过
                                              违规: 8mm < 10mm
                                              建议: 板厚 ≥10mm
```

### CAD Agent：图纸的"画师与翻译官"

CAD Agent 有两个相反方向的能力：

```
  图纸绘制 (Draw)                图纸解析 (Parse)
  ════════════                 ══════════════
  
  参数 → 图纸                    图纸 → 数据
  
  "船长100m, 船宽15m"           DWG 文件
      │                              │
      ▼                              ▼
  ┌──────────┐               ┌──────────┐
  │调用 CAD   │               │提取图层   │
  │API 画图   │               │提取尺寸   │
  └──────────┘               │提取标注   │
      │                      └──────────┘
      ▼                              │
  型线图.dwg                          ▼
                              {
                                "dimensions": [...],
                                "layers": ["hull", ...],
                                "annotations": [...]
                              }
```

### Review Agent 和 CAD Agent 的协作

```
典型的联合任务流程：

用户："审查这张图纸是否符合CCS规范"
  │
  ├── CAD Agent: 解析 DWG 图纸 → 提取尺寸参数
  │      └── 输出: {"舱壁间距": 500, "板厚": 8, ...}
  │
  ├── Review Agent: 对提取的参数逐条审查
  │      ├── 舱壁间距 500mm vs CCS §2.5.3 (≥600mm) → 违规
  │      ├── 板厚 8mm vs CCS §3.1.2 (≥10mm) → 违规
  │      └── 输出: {pass: false, violations: [...], suggestions: [...]}
  │
  └── Doc Agent: 基于审查结果生成报告
```

## 项目代码精讲

### Review Agent

打开 `agents/review_agent/agent.py`。

#### 元数据

```python
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
                    "regulation_codes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
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
        # ...
    ],
)
```

注意 `input_schema` 明确定义了输入格式：`design_params`（设计参数对象）和 `regulation_codes`（规范代号数组）。这让编排器能自动判断某个任务是否可以交给这个 Agent。

#### 审查逻辑

```python
async def _regulation_check(self, task, context, callbacks) -> dict:
    design_params = task.get("inputs", {}).get("design_params", {})
    regulation_codes = task.get("inputs", {}).get(
        "regulation_codes", ["CCS"]
    )

    violations = []
    suggestions = []

    # 遍历每个设计参数，检查是否合规
    for param, value in design_params.items():
        # 示例审查规则 —— 生产环境接入 RAG + 知识图谱
        if "舱壁" in param and isinstance(value, (int, float)) and value < 600:
            violations.append({
                "clause": "CCS §2.5.3",
                "parameter": param,
                "value": value,
                "requirement": ">= 600mm",
                "severity": "error",
                "description": f"{param} 为 {value}mm，"
                               f"不满足规范要求的 ≥600mm",
            })
            suggestions.append({
                "parameter": param,
                "suggestion": f"建议将 {param} 增大至 ≥600mm",
                "priority": "high",
            })

    return {
        "status": "completed",
        "pass": len(violations) == 0,
        "violations": violations,
        "suggestions": suggestions,
        "regulation_codes_checked": regulation_codes,
    }
```

**数据结构解读**：

每条 violation 包含：
- `clause`：违反的规范条文编号（CCS §2.5.3）
- `parameter`：哪个参数不符合
- `value`：当前值 vs `requirement`：规范要求值
- `severity`：严重程度（error/warning）
- `description`：人类可读的解释

每条 suggestion 包含：
- `parameter`：需要修改的参数
- `suggestion`：具体的修改建议
- `priority`：优先级（high/medium/low）

**当前实现的局限**：审查规则是硬编码的（只检查了"舱壁"相关参数）。生产环境应该接入 RAG 引擎，动态检索相关规范条文并自动化比对。这就是 `tools=["reg_check", "web_search"]` 的作用——但实际调用尚未实现。

### CAD Agent

打开 `agents/cad_agent/agent.py`。

```python
CAD_AGENT_METADATA = AgentMetadata(
    agent_id="cad_agent",
    name="CAD Agent",
    role="图纸解析、型线绘制、曲线光顺、DWG 操作",
    capabilities=[
        AgentCapability(name="cad_draw",
            description="型线图绘制与曲线光顺",
            tools=["cad_draw", "dwg_converter"],
            estimated_latency_ms=5000),       # 5秒，CAD操作较慢
        AgentCapability(name="cad_parse",
            description="从 DWG/DXF 提取尺寸和标注",
            tools=["cad_parse", "ocr_engine"],
            estimated_latency_ms=3000),
    ],
    max_concurrent_tasks=2,  # CAD操作吃资源
)
```

`estimated_latency_ms=5000` 是最高的——CAD 操作可能涉及外部软件调用，确实较慢。

#### 图纸绘制

```python
async def _draw_lines(self, task, context) -> dict:
    return {
        "status": "completed",
        "output": "型线图绘制完成",
        "files": {
            "dwg": "lines_plan.dwg",
            "preview": "lines_plan.png",
        },
        "quality": {
            "fairness": 0.985,      # 光顺度 98.5%
            "stations": 21,          # 21站
            "waterlines": 8,         # 8条水线
        },
    }
```

返回结果中的 `quality` 字段提供了图纸质量的量化指标：光顺度 (fairness) 越接近 1.0 表示曲线越平滑。

#### 图纸解析

```python
async def _parse_drawing(self, task, context) -> dict:
    return {
        "status": "completed",
        "output": "图纸解析完成",
        "extracted": {
            "dimensions": [],        # 提取的尺寸
            "annotations": [],       # 提取的标注
            "layers": ["hull", "deck", "bulkhead"],
        },
    }
```

CAD 图纸按"图层"（layer）组织：船体外板（hull）、甲板（deck）、舱壁（bulkhead）分别在独立的图层上。解析器需要识别这些图层并分别提取信息。

## 手把手实践

### 实验：模拟审查流程

```python
# review_demo.py -- 简易审查逻辑
def review_design(design_params, rules):
    """审查设计参数"""
    violations = []
    suggestions = []

    for param, value in design_params.items():
        if param in rules:
            rule_min = rules[param]
            if value < rule_min:
                violations.append({
                    "parameter": param,
                    "current": value,
                    "required": f">= {rule_min}",
                })
                suggestions.append({
                    "parameter": param,
                    "suggestion": f"将 {param} 增大至 >= {rule_min}",
                })

    return {
        "pass": len(violations) == 0,
        "violations": violations,
        "suggestions": suggestions,
    }

# 规范要求
CCS_RULES = {
    "舱壁间距": 600,
    "结构板厚": 10,
    "肋骨间距": 750,
}

# 设计参数
design = {"舱壁间距": 500, "结构板厚": 12, "肋骨间距": 800}

result = review_design(design, CCS_RULES)
print(f"审查结果: {'通过' if result['pass'] else '不通过'}")
for v in result['violations']:
    print(f"  违规: {v['parameter']} = {v['current']} (要求 {v['required']})")
for s in result['suggestions']:
    print(f"  建议: {s['suggestion']}")
```

### 实验：理解图层概念

如果熟悉 Docker，可以把 CAD 图层类比为 Docker 镜像层——每个图层叠加在一起形成完整的图纸。看看你能否用 Python 字典模拟一个简单的图层系统。

## 视频学习资源

请在 B站（bilibili.com）自行搜索以下关键词：

- "船舶规范 CCS 入级规范 简介" -- 了解船舶规范体系
- "CAD 图纸 DWG 格式 图层概念" -- 理解 CAD 基础
- "正则表达式 合规检查 自动化审查" -- 了解自动化审查原理

## 常见问题与排错

**Q1：Review Agent 的审查规则太少了，只有"舱壁"一条？**

A：是的。当前是演示级别的简化实现。完整版需要：
1. 将规范条文向量化存入 Milvus
2. 用 RAG 检索相关条文
3. 用 LLM 比对设计参数和规范要求

思路是：`RAG检索("舱壁间距要求") → 提取"≥600mm" → 比对 500mm → 发现违规`。

**Q2：CAD Agent 真的能画图吗？**

A：当前代码是"接口已定义，逻辑待实现"的状态。真正的画图需要集成外部的 CAD 引擎（如 AutoCAD MCP API 或 SolidWorks MCP）。框架已经准备好了（通过 `tools=["cad_draw"]` 声明了对 CAD 工具的依赖），只需接入实际的工具实现。

**Q3：fairness=0.985 是什么意思？**

A：光顺度（fairness）衡量曲线的平滑程度。1.0 表示完美平滑。0.985 在工程上是非常好的结果。计算方法涉及曲线曲率变化的评估。

## 练习任务

1. **代码题**：扩展 `review_demo.py`，增加新的审查规则：检查 GM 值是否 >= 0.15m，增加"稳性不足"的违规记录。
2. **设计题**：CAD Agent 当前有两个能力（draw 和 parse）。设计第三个能力 `cad_optimize`（图纸优化），填写其 AgentCapability。
3. **分析题**：`_regulation_check` 中每个违规都同时记录了 violation 和 suggestion。这两者的数据结构有什么不同？为什么需要分开存储？
4. **综合题**：设计 Review Agent 和 CAD Agent 协作完成"审核型线图光顺度"的完整流程。写出从用户上传 DWG 到最终审查报告的步骤序列。
