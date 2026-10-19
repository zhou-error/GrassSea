# Rhino 桥接功能 — 开发规划

> 状态：**规划稿**（尚未开工）
> 依据：[2026-10-17 评审](#) 提出的 P0/P1 问题；本规划已把这些修订纳入设计。
> 前提：本机**无 Rhino**，分阶段交付；阶段 1–3 可完全离线验证，阶段 4 需真机。

---

## 1. 目标与边界

**目标**：让 GrassSea 能把"建模意图"翻译成一条可执行的 Rhino 操作，并在返回前确认结果。

**边界（不做）**：
- 不生成 Python 代码交给 Rhino 执行（只发结构化操作指令）
- 不直接 import RhinoCommon（GrassSea 进程内无 Rhino 运行时）
- 不做 GH（Grasshopper）组件操作
- 不支持用户自定义 operation

---

## 2. 协议 v1（相对原规范的修订）

### 2.1 调用改为异步（解决 UI 线程死锁）

原规范 `call_rhino` 同步返回结果 + 在 UI 线程执行 = 必然死锁。修订为：

```json
// 1) 提交
POST /rpc  {
  "protocol": 1,
  "token": "<一次性令牌>",
  "request_id": "<uuid v4，幂等键>",
  "operation": "create_curve",
  "params": { "points": [[0,0,0],[1,0,0],[2,1,0],[3,0,0]], "degree": 3, "closed": false },
  "bake": true,
  "timeout_ms": 30000
}
→ 202 { "request_id": "...", "state": "queued" }

// 2) 轮询结果
GET /rpc/<request_id>
→ 200 {
  "request_id": "...",
  "state": "done" | "running" | "failed",
  "ok": true,
  "object_ids": ["..."],
  "preview_info": null,
  "error": null
}
```

**幂等**：相同 `request_id` 重复提交，返回同一结果，不重复执行（解决 bake=true 重试造重复几何）。

### 2.2 结构化错误

```json
"error": { "code": "invalid_params", "message": "...", "detail": { "field": "degree", "expected": "≤ points.Count-1" } }
```

| code | 含义 | 调用方应对 |
|---|---|---|
| `bridge_unreachable` | Rhino 未开 / 桥接未启动 | 告知用户并给启动路径 |
| `timeout` | 超过 timeout_ms | 询问是否重试（写操作不自动重试） |
| `unknown_operation` | 不在白名单 | 直接失败，记录日志 |
| `invalid_params` | 校验不通过 | 把 detail 回灌给模型修正 |
| `not_found` | object_id 不存在 | 让模型重新 query |
| `geometry_failure` | Rhino 几何运算失败 | 告知用户形状问题 |
| `busy` | 队列已满 | 稍后重试 |
| `internal` | 其他 | 记录日志 |

### 2.3 操作契约（补齐必需参数）

| operation | params | bake 语义 |
|---|---|---|
| `create_curve` | `points[][]`, **`degree`**, `closed` | false=只算不写 |
| `extrude` | `curve_id`, `height`, **`cap`** | false=只算不写 |
| `boolean` | `brep_id_a/b`, `operation`, **`tolerance`** | false=只算不写 |
| `delete` | `object_ids[]` | **忽略 bake**（本质是文档变更，需确认） |
| `query` | `object_ids[]` | 只读，无副作用 |

**挤出方向**：`Extrusion.Create` 沿**曲线所在平面法向**，不是世界 Z。规范措辞需改为"沿曲线平面法向挤出"，或提供可选 `direction` 参数（v2）。

### 2.4 原子性

每个请求包一层 undo 事务：`BeginUndoRecord("GrassSea: <op>")` → 执行 → 成功 `EndUndoRecord()` / 失败 `doc.Undo()`。失败绝不留半成品。

---

## 3. 模块与文件清单

### 新增

| 文件 | 职责 | 依赖 |
|---|---|---|
| `tools/cad/rhino_schema.py` | 参数校验（**纯函数，零 IO**） | 无 |
| `tools/cad/rhino_client.py` | 传输：HTTP、token、超时、轮询、幂等键 | httpx |
| `tools/cad/rhino_bridge.py` | 工具层：ToolManifest + execute + 诚实失败映射 | 上两者 |
| `agents/cad_agent/prompts.py` | 分节提示词（order 100–600）+ `render()` | 无 |
| `rhino/bridge.py` | Rhino 侧脚本：监听、队列、InvokeOnUiThread、undo、白名单 | RhinoCommon |
| `rhino/README.md` | 安装、启动、故障排查 | — |
| `tests/fixtures/mock_bridge.py` | mock 桥接服务（8 种错误码全覆盖） | 标准库 http.server |
| `tests/unit/test_rhino_schema.py` | 校验层单测 | pytest |
| `tests/unit/test_rhino_client.py` | 传输层 + mock 联调 | pytest |

### 修改

| 文件 | 改动 |
|---|---|
| `tools/bootstrap.py` | 注册 `RhinoBridgeTool` |
| `services/agent_service/tool_loop.py` | `MODEL_EXPOSED_TOOLS` 加入 `rhino_bridge`（**默认不暴露**，见 `7） |
| `shared/utils/config.py` | 新增 4 个配置项 |
| `app/preflight.py` | 可选：桥接连通性探测（`RHINO_BRIDGE_ENABLED=true` 时） |
| `agents/cad_agent/agent.py` | `_draw_lines` 从 `not_implemented` 改为调用 `rhino_bridge` |
| `docs/ARCHITECTURE.md` / `BACKLOG.md` | 同步 |

---

## 4. 分阶段开发计划

### 阶段 1：校验层（纯函数，零外部依赖）

**产出**：`tools/cad/rhino_schema.py`

```python
def validate(operation: str, params: dict, *, unit: str = "mm") -> dict:
    """返回 {"ok": True, "params": <规范化后>} 或 {"ok": False, "error": {...}}"""
```

**校验规则表**：

| 操作 | 规则 |
|---|---|
| `create_curve` | points 是 list；每项 len==3；数值有限（非 nan/inf）；`2 ≤ len(points) ≤ 10000`；`1 ≤ degree ≤ min(3, len-1)`；`closed` 为 bool；闭合时要求 `len ≥ 3` |
| `extrude` | `curve_id` 为 36 位 GUID 字符串；`height` 有限且**按单位换算**到米后 `0.001 ≤ abs ≤ 1000`；`cap` 为 bool |
| `boolean` | 两个 id 均为 GUID 且不相等；`operation ∈ {union,difference,intersection}`；`tolerance > 0` 且 `≤ 1.0`（米） |
| `delete` | `object_ids` 非空、≤ 500、全部 GUID |
| `query` | `object_ids` 非空、≤ 500、全部 GUID |
| 通用 | 拒绝未在白名单的 operation；拒绝 params 中出现非序列化值（函数/对象） |

**单位换算**：`unit ∈ {mm, cm, m}` → 统一换算到米再判阈值（解决原规范 `10000` 与船体 400 m 的冲突）。

**验收**：`pytest tests/unit/test_rhino_schema.py`，覆盖每条的**合法 / 边界 / 非法**三组，至少 40 个用例。

---

### 阶段 2：传输层 + mock 桥接

**产出**：`rhino_client.py` + `tests/fixtures/mock_bridge.py`

```python
class RhinoClient:
    def __init__(self, url: str, token: str, timeout_ms: int = 30000): ...
    async def hello(self) -> dict: ...          # 握手：protocol/rhino_version/units/doc_name
    async def submit(self, op: str, params: dict, bake: bool) -> str: ...   # 返回 request_id
    async def wait(self, request_id: str, timeout_ms: int) -> dict: ...     # 轮询直到终态
    async def call(self, op: str, params: dict, bake: bool = True) -> dict: ...  # submit + wait
```

**mock 桥接**必须能模拟：8 种错误码、慢响应（触发 timeout）、重复 request_id（幂等）、队列满（busy）。

**验收**：`pytest tests/unit/test_rhino_client.py`，断言 8 个分支各自的返回值与**不重试写操作**。

---

### 阶段 3：工具层接入

**产出**：`tools/cad/rhino_bridge.py` + 注册 + 配置

```python
RHINO_MANIFEST = ToolManifest(
    tool_id="rhino_bridge",
    name="Rhino 建模桥接",
    description="通过本地桥接在已打开的 Rhino 中创建曲线、挤出、布尔、删除、查询；"
                "Rhino 未运行时如实返回未连接，不伪造结果。",
    category=ToolCategory.CAD,
    timeout_ms=60000,
    requires_auth=True,
    rate_limit_per_min=20,
)
```

**诚实失败映射**：`bridge_unreachable` → `{"status":"error","message":"Rhino 桥接未连接：……"}`；`not_implemented` 不再使用（能力已实现）。

**验收**：注册表 `list_tools()` 出现 `rhino_bridge`；未配置时返回 `error` 而非崩溃；`--check` 通过。

---

### 阶段 4：Rhino 侧脚本（**唯一需真机**）

**产出**：`rhino/bridge.py` + `rhino/README.md`

核心结构：

```
listener 线程（socketserver/HTTP）→ 有界队列(32)
  → RhinoApp.InvokeOnUiThread(handler)
    → BeginUndoRecord → 执行 → EndUndoRecord / Undo
      → 结果写回 dict → 客户端轮询取走
```

**必须实现**：token 校验、Host 校验、白名单硬校验、幂等缓存（最近 100 个 request_id）、超时取消、`/hello` 握手。

**验收清单（真机）**：

| # | 验证项 | 期望 |
|---|---|---|
| 1 | `/hello` | 返回 protocol=1、rhino 版本、文档单位 |
| 2 | create_curve 4 点 3 阶 | 生成曲线，返回 GUID |
| 3 | extrude cap=true | 生成闭合挤出体 |
| 4 | boolean union | 返回单个 Brep |
| 5 | delete 不存在的 id | `not_found`，不崩 |
| 6 | 制造几何失败（共面布尔） | `geometry_failure` + 文档**无残留** |
| 7 | 相同 request_id 提交两次 | 只执行一次 |
| 8 | 关闭 Rhino 后调用 | `bridge_unreachable`，GrassSea 不挂 |
| 9 | 非法 operation | `unknown_operation`，Rhino 无动作 |
| 10 | 无 token 调用 | 401 |

---

### 阶段 5：提示词与 Agent 接入

**产出**：`agents/cad_agent/prompts.py`

把原规范的 6 节转成常量，按 order 拼接：

```python
SECTIONS = [
    (100, "rhino:identity", IDENTITY),
    (200, "rhino:protocol", PROTOCOL),      # 改写：异步 + 错误码
    (300, "rhino:operations", OPERATIONS),  # 补 degree/cap/tolerance
    (400, "rhino:thread-safety", THREAD),
    (500, "rhino:execution-policy", POLICY),
    (600, "rhino:geometry-validation", VALIDATION),
]
def render() -> str: return "\n\n".join(text for _, _, text in sorted(SECTIONS))
```

**与现有提示词的关系**（待你确认，见 `9）：作为 `cad_agent` 的独立 system prompt，与 `tool_loop` 的通用提示词并行——通用提示词负责"何时调工具"，这份负责"怎么调 Rhino"。

**验收**：`cad_agent._draw_lines` 在 Rhino 不可用时返回 `error` 并说明；可用时返回几何摘要。

---

## 5. 配置项

| key | 默认 | 说明 |
|---|---|---|
| `RHINO_BRIDGE_ENABLED` | `false` | 总开关；关闭时工具返回未启用 |
| `RHINO_BRIDGE_URL` | `http://127.0.0.1:8765` | 桥接地址 |
| `RHINO_BRIDGE_TIMEOUT_MS` | `30000` | 单次调用超时 |
| `RHINO_BRIDGE_TOKEN_FILE` | `<DATA_DIR>/bridge.token` | 令牌文件路径 |

全部加入 `CONFIG_SCHEMA`（带中英双语标签），设置页可改。

---

## 6. 安全清单（P0 项）

| 项 | 措施 |
|---|---|
| 未授权访问 | 一次性 token（文件权限 600），每次调用校验 |
| 跨站请求 | 只绑 `127.0.0.1`，校验 `Host` 与 `Origin` |
| 操作注入 | 桥接端**硬编码白名单**，与提示词解耦 |
| 提示词注入 | 破坏性操作（boolean/delete）默认 `bake=false` 需确认；`delete` 强制确认 |
| 路径/代码执行 | 参数只接受数字/字符串/布尔/列表，桥接端二次类型校验 |

---

## 7. 是否暴露给模型的决策

**建议初期不加入 `MODEL_EXPOSED_TOOLS`**，原因：
1. 无 Rhino 环境下模型会频繁命中 `bridge_unreachable`，浪费轮次；
2. 破坏性操作在真机验证完成前不该由模型自主触发。

验证通过后，用配置项 `RHINO_BRIDGE_ENABLED=true` + 白名单加入来开启。

---

## 8. 风险与未验证项

| 项 | 状态 | 说明 |
|---|---|---|
| `RhinoApp.InvokeOnUiThread` 在 Rhino 6/7/8 的可用性 | ⚠️ 待验证 | 需真机确认签名与行为 |
| `Extrusion.Create` 沿平面法向 | ⚠️ 待验证 | 影响"向上挤出"的语义 |
| 布尔 API 的 tolerance 重载 | ⚠️ 待验证 | 具体重载可能随版本差异 |
| IronPython 2.7（Rhino 7）与 CPython（Rhino 8）语法差异 | ⚠️ 待决策 | 脚本需按目标版本写；建议先支持 Rhino 8 |
| 文档单位获取 | ⚠️ 待验证 | `doc.ModelUnitSystem` 的枚举值 |

---

## 9. 待你确认的 3 个问题

1. **目标 Rhino 版本**：8（CPython，脚本更易写）还是 7（IronPython）？决定 `rhino/bridge.py` 的写法。
2. **提示词归属**：作为 `cad_agent` 独立 system prompt（推荐），还是并入 `tool_loop` 通用提示词？
3. **是否允许模型自主触发破坏性操作**（boolean/delete）：建议默认禁止、需用户在对话中明确确认。

---

## 10. 工作量估算

| 阶段 | 内容 | 估时 |
|---|---|---|
| 1 | 校验层 + 40 用例 | 0.5 天 |
| 2 | 传输层 + mock + 8 分支 | 0.5 天 |
| 3 | 工具层 + 注册 + 配置 | 0.5 天 |
| 4 | Rhino 脚本（无真机编写） | 1 天 |
| 5 | 提示词 + agent 接入 | 0.5 天 |
| — | **合计（不含真机验证）** | **约 3 天** |
| — | 真机验证与调试 | 待定（依赖 Rhino 环境） |

---

## 11. 里程碑

| 里程碑 | 判据 |
|---|---|
| M1 | 校验层单测全绿，40+ 用例覆盖合法/边界/非法 |
| M2 | mock 桥接下 8 种错误码全部按契约返回，写操作不重试 |
| M3 | `--check` 通过，`rhino_bridge` 已注册，未配置时诚实报错 |
| M4 | 真机 10 项验收清单通过 |
| M5 | `cad_agent` 可用；BACKLOG/ARCHITECTURE 同步 |

