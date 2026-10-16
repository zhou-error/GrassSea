# 工具开发指南（Tool Development Guide）

> 面向为 GrassSea AI 新增工具（Tool）的开发者。读完本文应能独立完成：
> 写一个工具 → 注册 → 测试 → 让大模型自主调用它。
>
> 代码基线：`develop` 分支；工具协议版本 0.1.0。配套文档：[架构说明](./ARCHITECTURE.md)。

---

## 目录

1. [工具是什么：架构位置](#1-工具是什么架构位置)
2. [5 分钟做第一个工具](#2-5-分钟做第一个工具)
3. [ToolManifest 字段详解](#3-toolmanifest-字段详解)
4. [input_schema：参数怎么写](#4-input_schema参数怎么写)
5. [execute：返回值契约](#5-execute返回值契约)
6. [注册：让工具进入注册中心](#6-注册让工具进入注册中心)
7. [让模型能自主调用你的工具](#7-让模型能自主调用你的工具)
8. [测试：三层验证](#8-测试三层验证)
9. [常见坑与约定](#9-常见坑与约定)
10. [提交前检查清单](#10-提交前检查清单)

---

## 1. 工具是什么：架构位置

工具是平台**最小的原子能力单元**。与「智能体（Agent）」的区别：

| | Tool | Agent |
|---|---|---|
| 粒度 | 单一计算 / 单一操作 | 一个专业角色的完整流程 |
| 调用方 | 注册中心 ToolRegistry，或被大模型直接选中 | 任务编排器 TaskExecutor |
| 位置 | `tools/<category>/<name>.py` | `agents/<name>/agent.py` |
| 契约 | `BaseTool.execute()` | `BaseAgent.handle_task()` |

**两条调用路径**（同一个工具实例，两条路都会用到）：

```text
路径 A（规则）  planner 生成 DAG → TaskExecutor._execute_step
                → ToolRegistry.execute_tool → tool.execute

路径 B（自主）  用户提问 → ToolCallLoop 把工具的 JSON Schema 交给大模型
                → 模型返回 tool_calls → ToolRegistry.execute_tool
                → 结果回灌模型 → 模型给出最终回答
```

**关键文件**

| 文件 | 作用 |
|---|---|
| `shared/protocols/tool.py` | ToolManifest / BaseTool / ToolCategory / ToolStatus 定义 |
| `tools/base/registry.py` | 注册中心：校验、状态机、超时控制、健康检查 |
| `tools/bootstrap.py` | `build_tool_registry()`：实例化并注册全部工具（**新增工具必须在此登记**） |
| `services/agent_service/tool_loop.py` | 模型自主调用循环；`MODEL_EXPOSED_TOOLS` 决定哪些工具对模型可见 |

---

## 2. 5 分钟做第一个工具

**目标**：实现「载重量估算」工具 `deadweight_estimate`。

### 第 1 步：新建 `tools/computation/deadweight.py`

```python
"""载重量估算工具 — 依据主尺度与方形系数估算载重量

公式依据（务必在 docstring 写清，便于后续核对）：
    Δ = ρ · L · B · T · Cb          # 排水量
    LWT ≈ Δ · lightship_ratio        # 空船重量（经验系数法）
    DWT = Δ - LWT                    # 载重量
"""

from __future__ import annotations

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

DEADWEIGHT_MANIFEST = ToolManifest(
    tool_id="deadweight_estimate",
    name="载重量估算",
    description=(
        "根据船长、型宽、吃水与方形系数估算船舶排水量、空船重量与载重量(DWT)。"
        "适用于方案设计阶段的快速估算；如需精确值请提供完整型值表。"
    ),
    category=ToolCategory.COMPUTATION,
    input_schema={
        "type": "object",
        "properties": {
            "L": {"type": "number", "description": "垂线间长(m)，默认 100"},
            "B": {"type": "number", "description": "型宽(m)，默认 15"},
            "T": {"type": "number", "description": "设计吃水(m)，默认 5"},
            "Cb": {"type": "number", "description": "方形系数，默认 0.75"},
            "rho": {"type": "number", "description": "水密度(t/m3)，海水 1.025"},
            "lightship_ratio": {"type": "number", "description": "空船重量占排水量比例，默认 0.35"},
        },
        "required": [],
    },
    output_schema={
        "type": "object",
        "properties": {
            "displacement_t": {"type": "number"},
            "lightship_t": {"type": "number"},
            "deadweight_t": {"type": "number"},
            "status": {"type": "string"},
        },
    },
    timeout_ms=15000,
    version="0.1.0",
)


class DeadweightEstimateTool(BaseTool):
    """载重量估算"""

    def __init__(self) -> None:
        super().__init__(DEADWEIGHT_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        # 一律显式 float()：参数可能来自 numpy/pandas，numpy 标量无法被 FastAPI 序列化
        L = float(params.get("L", params.get("length", 100.0)))
        B = float(params.get("B", params.get("beam", 15.0)))
        T = float(params.get("T", params.get("draft", 5.0)))
        Cb = float(params.get("Cb", params.get("cb", 0.75)))
        rho = float(params.get("rho", 1.025))
        ratio = float(params.get("lightship_ratio", 0.35))

        displacement = rho * L * B * T * Cb
        lightship = displacement * ratio
        deadweight = displacement - lightship

        return {
            "status": "completed",
            "inputs": {"L": L, "B": B, "T": T, "Cb": Cb, "rho": rho},
            "results": {
                "displacement_t": round(displacement, 1),
                "lightship_t": round(lightship, 1),
                "deadweight_t": round(deadweight, 1),
                "lightship_ratio": ratio,
                "method": "排水量法（经验空船系数）",
            },
        }
```

### 第 2 步：注册到 `tools/bootstrap.py`

```python
from tools.computation.deadweight import DeadweightEstimateTool

TOOL_CLASSES: tuple[type[BaseTool], ...] = (
    # ... 既有工具
    DeadweightEstimateTool,   # ← 追加
)
```

### 第 3 步：验证注册成功

```bash
uv run python -c "import asyncio; from tools.bootstrap import build_tool_registry as b; r=asyncio.run(b()); print([m.tool_id for m in asyncio.run(r.list_tools())])"
```

输出中出现 `deadweight_estimate` 即注册成功。

### 第 4 步（可选）：让模型能自主调用它

在 `services/agent_service/tool_loop.py` 把工具 ID 加入白名单：

```python
MODEL_EXPOSED_TOOLS: frozenset[str] = frozenset({
    "hydrostatics", "stability", "resistance", "hull_transform", "reg_check",
    "deadweight_estimate",   # ← 新增
})
```

> 只加入**真实实现**的工具。把未实现的工具暴露给模型，只会白白消耗模型轮次。

### 第 5 步：重建镜像并重启

```bash
docker compose -f docker-compose.yml -f docker-compose.app.yml up -d --build agent-service
```

---

## 3. ToolManifest 字段详解

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tool_id` | str | 是 | 唯一标识，建议小写下划线。**模型通过这个名字调用工具**，改名等于破坏兼容 |
| `name` | str | 是 | 中文显示名 |
| `description` | str | 是 | **模型据此判断何时调用**，写法见第 7 节 |
| `category` | ToolCategory | 是 | computation / compliance / cad / report / file / search / external |
| `input_schema` | dict | 是 | JSON Schema，**不能为空**，否则注册被拒 |
| `output_schema` | dict | 是 | 输出结构说明，**不能为空** |
| `timeout_ms` | int | 否 | 默认 30000；必须 > 0。注册中心按此值执行 asyncio.wait_for |
| `requires_auth` | bool | 否 | 默认 True；当前平台无鉴权，保留字段 |
| `rate_limit_per_min` | int | 否 | 默认 60；**当前注册中心未实施限流** |
| `version` | str | 否 | 默认 0.1.0 |

**注册校验规则**（`tools/base/registry.py` 的 `_validate_tool`）：

```text
tool_id 非空  且  name 非空  且  input_schema 非空  且  output_schema 非空  且  timeout_ms > 0
```

任一不满足 → 工具被标记为 `REJECTED` 并**不进入注册中心**，日志打印 `Tool validation failed`。

**状态机**：DEVELOPING → REGISTERED → ONLINE → DEGRADED / OFFLINE

只有 `ONLINE` 的工具才会被 `execute_tool` 执行，也才会出现在给模型的清单里。
注册时 `health_check()` 返回 True 即自动置为 ONLINE（`BaseTool` 默认实现返回 True）。

---

## 4. input_schema：参数怎么写

### 基本结构

```python
input_schema={
    "type": "object",
    "properties": {
        "displacement": {"type": "number", "description": "排水量(t)"},
        "grade": {"type": "string", "enum": ["A", "B"], "description": "钢材等级"},
        "frames": {"type": "array", "items": {"type": "number"}, "description": "肋位坐标列表(m)"},
    },
    "required": ["displacement"],
}
```

### 三条硬性约定

1. **每个属性都要有 `description`。** 模型靠这段文字决定传什么值；没描述的参数模型基本传不准。
2. **`required` 尽量少。** 可缺省参数在 `execute` 里给默认值（见示例中的 `params.get("L", 100.0)`），模型少填参数也能跑通。
3. **同一含义只保留一个规范名**，需要兼容别名时在 `execute` 里做回退（示例中的 `params.get("B", params.get("beam", 15.0))`）。既有计算工具沿用了这个模式。

### 数值参数一律显式转换

参数可能来自模型（JSON 数字），也可能来自 pandas/numpy。**numpy 标量无法被 FastAPI 序列化**，统一写法：

```python
L = float(params.get("L", 100.0))
```

---

## 5. execute：返回值契约

```python
async def execute(self, params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
```

| 参数 | 含义 |
|---|---|
| `params` | 模型或编排器传入的参数（已按 input_schema 约定） |
| `context` | 会话上下文：`session_id`、`user_id`（自主调用路径会带上） |

### 必须遵守的返回结构

**成功**

```python
{
    "status": "completed",              # 必需，编排器据此归入 completed
    "inputs": {...},                    # 建议：回显实际使用的参数，便于复核
    "results": {                        # 建议：结构化结果，前端渲染成 key=value
        "deadweight_t": 3012.5,
        "method": "排水量法",
    },
}
```

**未实现（诚实失败）** —— 本项目的硬性约定

```python
{
    "status": "not_implemented",
    "message": "载重量精确计算尚未实现：未接入完整型值表与空船重量分项统计，因此不返回任何估算以外的伪造数值。",
}
```

**失败**

```python
{"status": "error", "message": "具体原因"}
```

### status 如何影响编排

| status 取值 | 编排器归入 | 对模型的含义 |
|---|---|---|
| `completed` | completed（成功） | 正常使用结果 |
| `not_implemented` | **skipped（跳过，不算失败）** | 模型会如实告知用户该能力不可用 |
| `error` / `failed` | failed（失败） | 模型会尝试其它路径或说明失败原因 |

> **绝不编造**：没有真实数据时返回 `not_implemented` 并说明原因。
> 返回伪造的文件路径、规范条款号、文献条目都属于严重缺陷。

### 异常与超时

`execute` 内抛出的异常会被 `ToolRegistry.execute_tool` 捕获并转成 `{"status": "error", "message": ...}`；
超过 `manifest.timeout_ms` 会被转成 `{"status": "error", "message": "Tool execution timeout"}`。
**建议**：能预期的错误自己捕获并给出中文原因，比抛异常更利于模型理解与用户排障。

---

## 6. 注册：让工具进入注册中心

```python
# tools/bootstrap.py
TOOL_CLASSES: tuple[type[BaseTool], ...] = (
    CadDrawTool,
    # ...
    DeadweightEstimateTool,     # ← 在这里追加
)


async def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool_cls in TOOL_CLASSES:
        tool = tool_cls()
        ok = await registry.register(tool)
        # ...
```

**要点**

- 工具类构造函数**不要有必需参数**（`build_tool_registry` 用 `tool_cls()` 无参实例化）。
- 工具实例在服务启动时**一次性创建**并长期复用 → 不要在 `execute` 里保存每次调用的状态（见第 9 节）。
- 注册完成后查看启动日志：`Tool registry built registered=N rejected=[...]`。`rejected` 非空说明有工具校验失败。

---

## 7. 让模型能自主调用你的工具

### 7.1 暴露

加入 `services/agent_service/tool_loop.py` 的 `MODEL_EXPOSED_TOOLS`（第 2 节第 4 步），然后验证：

```bash
curl http://localhost:8001/tools
```

返回中该工具的 `exposed_to_model` 应为 `true`。

### 7.2 description 怎么写，模型才选得准

模型**只看到** `tool_id`、`description`、`input_schema`。推荐的 description 结构：

```text
<做什么>。<什么时候该用>。<关键限制 / 不适用场景>。
```

对比：

| 质量 | 例子 |
|---|---|
| 差 | `"稳性分析"` |
| 好 | `"计算初稳性高度 GM 与横摇周期，并按 IMO 初稳性要求判定。已知设计船宽、吃水与方形系数时使用；若已知 KM/KG 可直接传入以获得更精确结果。不适用于破舱稳性与完整稳性曲线计算。"` |

**关键限制要写进去**，否则模型会在不该用的场景调用它。

### 7.3 控制暴露范围（配置项）

| 配置项 | 默认 | 作用 |
|---|---|---|
| `TOOL_CALLING_ENABLED` | true | 总开关；关闭后回到规则规划路径 |
| `TOOL_CALL_EXPOSE_UNIMPLEMENTED` | false | 是否把**未实现**的工具也暴露给模型 |
| `TOOL_CALL_MAX_ROUNDS` | 6 | 最多几轮「模型思考 → 调工具 → 回灌」 |
| `TOOL_CALL_TIMEOUT_SECONDS` | 120 | 整个循环的总超时 |
| `TOOL_CALL_MODEL` | deepseek-chat | 工具调用使用的模型 |

> 注意：`TOOL_CALL_EXPOSE_UNIMPLEMENTED=true` 会让 9 个尚未实现的工具也进入模型视野，
> 通常只会浪费轮次，除非你正在做能力验证。

---

## 8. 测试：三层验证

### 第 1 层：工具单体

```python
import asyncio
from tools.computation.deadweight import DeadweightEstimateTool

async def main():
    tool = DeadweightEstimateTool()
    result = await tool.execute({"L": 100, "B": 15, "T": 5, "Cb": 0.75}, {})
    assert result["status"] == "completed"
    print(result["results"])

asyncio.run(main())
```

### 第 2 层：经注册中心（含校验、超时、错误包装）

```python
import asyncio
from tools.bootstrap import build_tool_registry

async def main():
    registry = await build_tool_registry()
    ids = [m.tool_id for m in await registry.list_tools()]
    assert "deadweight_estimate" in ids, ids          # 确认已注册且为 ONLINE
    print(await registry.execute_tool("deadweight_estimate", {"L": 120}, {}))

asyncio.run(main())
```

### 第 3 层：端到端（容器内）

```bash
# 1) 工具是否暴露给模型
curl http://localhost:8001/tools

# 2) 让模型自己决定是否调用（换一句会触发该工具的话）
curl -X POST http://localhost:8001/chat -H "Content-Type: application/json" -d "{\"message\":\"帮我估算一条 120m 长、18m 宽、吃水 6m 的船载重量\",\"user_id\":\"dev\"}"
```

响应中的 `tool_trace` 应包含你新增的工具：

```json
{
  "answer": "...",
  "tool_trace": [
    {
      "round": 1,
      "tool": "deadweight_estimate",
      "arguments": {"L": 120, "B": 18, "T": 6},
      "status": "completed",
      "elapsed_ms": 3,
      "message": null
    }
  ]
}
```

前端对话气泡会以「模型自主调用工具 N 次」卡片展示这段轨迹。

---

## 9. 常见坑与约定

| 坑 | 现象 | 处理 |
|---|---|---|
| numpy 标量 | `TypeError: Object of type int64 is not JSON serializable` | 在 `execute` 里对每个数值 `float()` / `int()` |
| 工具实例被复用 | 并发调用时结果串味 | `execute` 内只用局部变量，绝不写 `self.xxx` |
| schema 为空 | 注册被拒，`rejected` 里有它 | `input_schema` / `output_schema` 都不能是 `{}` |
| 超时太短 | 大文件解析总超时 | 调大 `timeout_ms`；重活建议异步化 |
| 编造结果 | 前端出现不存在的文件路径 | 无真实数据一律 `not_implemented` |
| 只加白名单没重建镜像 | 模型看不到新工具 | 必须 `--build` 重建 agent-service |
| description 太笼统 | 模型在错误场景调用 | 写清「什么时候用 / 不适用什么」 |
| execute 里发网络请求 | 外部服务抖动导致整轮失败 | 捕获异常返回 error + 中文原因，并设置合理 timeout |

### 幂等与副作用

- **计算类工具**：天然幂等，无副作用。
- **写文件 / 发请求类工具**：`execute` 可能被模型在**同一轮对话里重复调用**（系统提示已要求不要重复，但模型不保证遵守）。请在设计上保证幂等，或在返回中明确提示「已生成一次，请勿重复调用」。

---

## 10. 提交前检查清单

- [ ] 文件放在 `tools/<category>/` 下，模块 docstring 写清公式 / 数据来源
- [ ] `tool_id` 小写下划线、语义明确、与文件名一致
- [ ] `description` 说明了「做什么 / 何时用 / 不适用什么」
- [ ] `input_schema` 每个属性都有 `description`，`required` 尽量少
- [ ] `output_schema` 非空
- [ ] `execute` 中所有数值参数都做了 `float()` / `int()` 转换
- [ ] 返回值含 `status`；无真实数据时返回 `not_implemented` + 中文原因
- [ ] `execute` 无 `self` 状态写入（保证并发安全）
- [ ] 已在 `tools/bootstrap.py` 的 `TOOL_CLASSES` 登记
- [ ] 已跑通第 8 节的第 1、2 层测试
- [ ] 如需模型自主调用，已加入 `MODEL_EXPOSED_TOOLS` 且 `curl /tools` 返回 `exposed_to_model: true`
- [ ] 已在容器内跑通第 3 层端到端测试，`tool_trace` 中能看到该工具
- [ ] 已同步更新 `docs/ARCHITECTURE.md` 的「工具能力」与「接口契约」章节

---

## 附：既有工具速查

| tool_id | 类别 | 状态 | 已暴露给模型 |
|---|---|---|---|
| `hydrostatics` | computation | 已实现 | 是 |
| `stability` | computation | 已实现 | 是 |
| `resistance` | computation | 已实现 | 是 |
| `hull_transform` | computation | 已实现 | 是 |
| `reg_check` | compliance | 已实现（内置启发式阈值，非规范条文） | 是 |
| `pdf_parser` / `xlsx_parser` / `ocr_engine` | file | 未实现 | 否 |
| `todo_manager` / `web_search` | file | 未实现 | 否 |
| `cad_draw` / `cad_parse` / `dwg_converter` | cad | 未实现 | 否 |
| `report_gen` | report | 未实现 | 否 |

> 未实现的工具同样遵循本文契约：`execute` 返回 `not_implemented` 并说明原因。
> 可参考 `tools/file/pdf_parser.py` 作为「诚实占位」模板。
