# 03 - 船舶工程师 Agent

## 学习目标

1. 理解 Naval Arch Agent 的四大核心能力：稳性计算、阻力计算、型线设计、规范审查
2. 掌握船舶工程中关键公式的 Python 实现（排水量、GM、横摇周期、Holtrop 法）
3. 学习 numpy 在工程计算中的应用
4. 能独立编写一个简单的船舶工程计算模块

## 前置知识

- Python 基础（函数、字典、数学运算）
- numpy 基础（数组运算、数学函数）
- 不需要船舶工程专业知识——本节会解释每个公式的含义

## 概念讲解

### Naval Arch Agent 的角色

Naval Arch Agent 是 GrassSea 中最"硬核"的 Agent，负责将船舶工程的计算公式转化为可执行的 Python 代码。

```
用户："计算这艘船的稳性"
  │
  │  参数: L=100m, B=15m, T=5m, Cb=0.75
  │
  ▼
┌──────────────────────────────────────────────────┐
│            Naval Arch Agent（船舶工程师）          │
│                                                  │
│  ① 稳性计算 ──────────────────────────────────   │
│     排水量 Δ = L × B × T × Cb × ρ               │
│     稳心高度 KM = B² / (12T) × (1 + Cb/2)        │
│     初稳性高 GM = KM - KG                        │
│     横摇周期 Tr = 2CB / √(GM)                    │
│                                                  │
│  ② 阻力计算 (Holtrop法) ─────────────────────   │
│     雷诺数 Rn = VsL / ν                          │
│     摩擦阻力系数 Cf = 0.075 / (log₁₀Rn - 2)²    │
│     湿表面积 S = L(2T+B)√Cb                     │
│     摩擦阻力 Rf = ½ρSV²Cf                        │
│                                                  │
│  ③ 型线设计 ─────────────────────────────────   │
│     母型船变换法                                  │
│     改型参数: L/B, B/T, Cb                       │
│                                                  │
│  ④ 规范审查 ─────────────────────────────────   │
│     检查计算结果是否符合 CCS/IMO 要求              │
└──────────────────────────────────────────────────┘
```

### 船舶稳性基础概念（零基础版）

在阅读代码之前，先理解几个关键术语：

```
        ┌────────────────────────────┐
        │          船舶横截面          │
        │                            │
        │       M ← 稳心(Metacenter) │
        │      /│                    │
        │     / │                    │
        │    /  │ GM (初稳性高)       │
        │   G───┼────┐ ← 重心(G)     │
        │   │   │    │              │
        │ B─┼───┘    │ ← 浮心(B)     │
        │   │        │              │
        │   │ 船体    │              │
        └───┴────────┴──────────────┘

GM = KM - KG
    KM: 稳心距基线高度
    KG: 重心距基线高度
    GM: 初稳性高 (越大越稳)

如果 GM > 0.15m，通常认为满足 IMO 完整稳性要求
如果 GM < 0，船会倾覆！
```

## 项目代码精讲

打开 `agents/naval_arch_agent/agent.py`。

### 元数据与能力声明

```python
NAVAL_ARCH_METADATA = AgentMetadata(
    agent_id="naval_arch_agent",
    name="船舶工程师 Agent",
    role="型线设计、稳性计算、规范审查、船型改造",
    capabilities=[
        AgentCapability(name="hull_design",
            description="型线设计与优化",
            tools=["cad_draw", "hull_transform"],
            estimated_latency_ms=3000),       # 3秒
        AgentCapability(name="stability_calc",
            description="完整稳性与破舱稳性计算",
            tools=["hydrostatics", "stability"],
            estimated_latency_ms=5000),       # 5秒
        AgentCapability(name="resistance_calc",
            description="阻力与推进性能计算",
            tools=["resistance"],
            estimated_latency_ms=3000),       # 3秒
        AgentCapability(name="reg_compliance",
            description="规范合规审查",
            tools=["reg_check"],
            estimated_latency_ms=2000),       # 2秒
    ],
    max_concurrent_tasks=3,  # 计算密集，限制并发
)
```

注意 `max_concurrent_tasks=3`（比 PM Agent 的 10 少很多），因为船舶计算是 CPU 密集型任务。

### 任务分发

```python
class NavalArchAgent(BaseAgent):
    async def handle_task(self, task, context, callbacks) -> dict:
        action = task.get("action", "stability_calc")
        params = task.get("inputs", {})

        if "stability" in action or "稳性" in action:
            return await self._stability_calculation(params, callbacks)
        elif "hull" in action or "型线" in action:
            return await self._hull_design(params, callbacks)
        elif "resistance" in action or "阻力" in action:
            return await self._resistance_calculation(params, callbacks)
        else:
            return await self._general_analysis(params, callbacks)
```

同时支持英文 action 名和中文关键词，增加了灵活性。

### 核心：稳性计算

这是整个 Agent 中最重要、最值得精读的方法：

```python
async def _stability_calculation(self, params, callbacks) -> dict:
    # === 第一步：提取参数（带默认值） ===
    L = params.get("length", 100.0)       # 船长 (m)
    B = params.get("beam", 15.0)           # 型宽 (m)
    D = params.get("depth", 8.0)           # 型深 (m)
    T = params.get("draft", 5.0)           # 吃水 (m)
    Cb = params.get("cb", 0.75)            # 方型系数（无单位）
    rho = params.get("water_density", 1025) # 海水密度 (kg/m³)

    # === 第二步：排水量计算 ===
    # Δ = L × B × T × Cb × ρ / 1000
    # 排水体积 × 海水密度 / 1000 = 吨
    displacement = L * B * T * Cb * rho / 1000  # 吨
```

**排水量公式解读**：
- `L × B × T` = 船长 × 船宽 × 吃水 = 包围盒体积
- `× Cb`（方型系数）= 实际水下体积 / 包围盒体积。Cb 通常 0.5-0.85
- `× ρ`（1025 kg/m³）= 转换为质量
- `/ 1000` = 转换为吨

```python
    # === 第三步：浮心纵向位置 ===
    # LCB = -0.05 × L × (1 - Cb)
    # 经验公式。舯前为正，负号表示通常在舯后
    LCB = -0.05 * L * (1 - Cb)  # 舯前为正
```

```python
    # === 第四步：稳心高度与初稳性高 ===
    # KM = B² / (12T) × (1 + Cb/2)  — 稳心距基线高度（经验公式）
    KM = B * B / (12 * T) * (1 + Cb / 2)

    # KG = 0.55 × D  — 重心高度估计（约为型深的55%）
    KG = 0.55 * D

    # GM = KM - KG  — 初稳性高（最关键的安全指标）
    GM = KM - KG
```

**GM 的判断标准**：
- GM > 0.35m：稳性良好
- 0.15m < GM < 0.35m：及格，但偏小
- GM < 0.15m：不满足 IMO 要求
- GM < 0：船会倾覆（绝对不允许）

```python
    # === 第五步：横摇周期 ===
    # Tr = 2CB / √(GM) × 经验系数
    # GM 越大（船越稳），横摇越快（周期越短）
    C = 0.38  # 经验系数
    Tr = 2 * C * B / np.sqrt(GM)
```

`np.sqrt(GM)` 来自 numpy，是求平方根。如果 GM 是负数，这里会报错——这是预期行为，因为负 GM 意味着船已经翻了。

```python
    # === 第六步：进度回调 ===
    await callbacks.on_progress(task.get("task_id", ""), 0.8) \
        if callbacks.on_progress else None

    # === 第七步：返回结果 ===
    return {
        "status": "completed",
        "calculation_type": "stability",
        "inputs": {"L": L, "B": B, "D": D, "T": T, "Cb": Cb},
        "results": {
            "displacement_t": round(displacement, 1),
            "LCB_m": round(LCB, 2),
            "KM_m": round(KM, 2),
            "GM_m": round(GM, 2),
            "roll_period_s": round(Tr, 1),
            "stability_assessment": (
                "满足 IMO 完整稳性要求" if GM > 0.15
                else "稳性不足，需要调整设计"
            ),
        },
        "warnings": (
            [] if GM > 0.35
            else ["GM 偏小，建议增大船宽或降低重心"]
        ),
    }
```

**返回结果的设计**：
- `inputs`：回显输入参数，便于追溯
- `results`：计算结果（带单位标注）
- `warnings`：自动生成的工程建议
- `stability_assessment`：人类可读的结论

### 阻力计算（Holtrop 法）

```python
async def _resistance_calculation(self, params, callbacks) -> dict:
    L = params.get("length", 100.0)
    B = params.get("beam", 15.0)
    T = params.get("draft", 5.0)
    V = params.get("speed_kn", 14.0)  # 航速（节）

    # === 1. 航速转换 ===
    # 1 节 = 0.5144 m/s
    Vs = V * 0.5144  # m/s

    # === 2. 雷诺数 ===
    # Rn = Vs × L / ν
    # ν = 1.19 × 10⁻⁶ m²/s (海水的运动粘度)
    # 雷诺数决定流动状态：层流 or 湍流
    Rn = Vs * L / 1.19e-6
```

**雷诺数 (Reynolds Number)**：流体力学中最关键的无量纲数。Rn > 10⁶ 时流动为湍流。船舶的 Rn 通常在 10⁸-10⁹ 量级。

```python
    # === 3. 摩擦阻力系数 (ITTC 1957) ===
    # Cf = 0.075 / (log₁₀Rn - 2)²
    Cf = 0.075 / (np.log10(Rn) - 2) ** 2
```

`np.log10(Rn)` 是 numpy 的以 10 为底的对数。

```python
    # === 4. 湿表面积 ===
    # S = L × (2T + B) × √Cb
    S = L * (2 * T + B) * np.sqrt(Cb)  # m²

    # === 5. 摩擦阻力 ===
    # Rf = ½ρSV²Cf / 1000
    Rf = 0.5 * 1025 * S * Vs ** 2 * Cf / 1000  # kN

    # === 6. 总阻力估算 ===
    # 总阻力 ≈ 1.35 × 摩擦阻力（简化，加入剩余阻力）
    total_R = Rf * 1.35
    # 有效功率 = 阻力 × 速度
    Pe = total_R * Vs  # kW
```

**为什么总阻力 = 1.35 × 摩擦阻力？**

船舶总阻力 = 摩擦阻力 + 剩余阻力（兴波阻力 + 粘压阻力）。对于中低速商船，摩擦阻力约占 70-75%。1.35 是一个经验比例因子。实际设计中需要更精确的方法。

```python
    return {
        "status": "completed",
        "calculation_type": "resistance",
        "results": {
            "Reynolds_number": f"{Rn:.2e}",          # 科学计数法
            "friction_coefficient": f"{Cf:.6f}",
            "wetted_surface_m2": round(S, 1),
            "friction_resistance_kN": round(Rf, 1),
            "total_resistance_estimate_kN": round(total_R, 1),
            "effective_power_kW": round(Pe, 1),
        },
    }
```

### numpy 在工程计算中的角色

在这个 Agent 中，numpy 主要提供：
- `np.sqrt()`：平方根
- `np.log10()`：以10为底的对数
- 未来扩展：矩阵运算（如有限元分析）、优化（如船型参数优化）

对于初学者，简单理解为"numpy 是 Python 的科学计算标准库"即可。

## 手把手实践

### 实验一：自己算一遍

```python
# 用手计算验证代码
L, B, T, Cb = 100, 15, 5, 0.75
rho = 1025

displacement = L * B * T * Cb * rho / 1000
print(f"排水量: {displacement:.1f} 吨")

KM = B * B / (12 * T) * (1 + Cb / 2)
KG = 0.55 * 8
GM = KM - KG
print(f"KM: {KM:.2f}m, KG: {KG:.2f}m, GM: {GM:.2f}m")

import numpy as np
Tr = 2 * 0.38 * B / np.sqrt(GM)
print(f"横摇周期: {Tr:.1f} 秒")
```

### 实验二：修改船型参数观察影响

```python
# sensitivity.py -- 观察参数变化对稳性的影响
import numpy as np

def calc_gm(L, B, T, D, Cb):
    KM = B * B / (12 * T) * (1 + Cb / 2)
    KG = 0.55 * D
    return KM - KG

# 基准方案
print(f"基准 GM: {calc_gm(100, 15, 5, 8, 0.75):.2f}m")

# 增大船宽 (B ↑ → GM ↑)
print(f"船宽+2m GM: {calc_gm(100, 17, 5, 8, 0.75):.2f}m")

# 减小吃水 (T ↓ → GM ↑)
print(f"吃水-1m GM: {calc_gm(100, 15, 4, 8, 0.75):.2f}m")

# 减小方型系数 (Cb ↓ → GM ↓)
print(f"Cb=0.65 GM: {calc_gm(100, 15, 5, 8, 0.65):.2f}m")
```

观察输出，理解"增大船宽"和"降低重心"如何提高稳性。

## 视频学习资源

请在 B站（bilibili.com）自行搜索以下关键词：

- "船舶静力学 稳性 排水量 基础" -- 理解船舶基础概念
- "numpy Python 科学计算 入门" -- 学习 numpy 应用
- "船舶阻力 Holtrop 方法" -- 了解阻力计算

## 常见问题与排错

**Q1：公式中的 "0.55"、"0.38"、"1.35" 这些魔法数字是什么？**

A：它们来自船舶工程的统计经验公式，不是凭空捏造的：
- 0.55：商船重心高度约为型深的 55%
- 0.38：横摇周期公式中的经验系数
- 1.35：剩余阻力的简化比例因子

生产级别代码可以给这些常量命名（如 `KG_RATIO = 0.55`），增加可维护性。

**Q2：`GM = KM - KG` 会不会出现负数？**

A：会出现！如果用户输入了极端参数（船太窄、重心太高）。代码中用 `np.sqrt(GM)` 时，如果 GM 为负会报错。生产代码应该先判断 `if GM <= 0: return {"error": "船体参数不合理，GM为非正数"}`。

**Q3：Holtrop 法的精度如何？**

A：Holtrop 法是阻力估算中的行业标准，对常规商船精度约 ±5-10%。对于特殊船型或高精度需求，需要使用 CFD（计算流体力学）或模型试验。

## 练习任务

1. **代码题**：为 `_stability_calculation` 增加 GM 的合法性检查：如果 GM <= 0，立即返回错误信息而不继续计算横摇周期。
2. **公式题**：修改阻力计算，加入兴波阻力系数 Cw = 0.05 (Fn/0.3)³，其中 Fn = Vs/√(gL)，g = 9.81。提示：需要新增一个 `wave_resistance` 字段。
3. **分析题**：`max_concurrent_tasks=3` 为什么是 3？如果服务器有 16 核 CPU，应该设为多少？
4. **综合题**：假设你要为 Naval Arch Agent 添加"舱容计算"能力。设计其 AgentCapability，并写出计算方法（简化版：舱容 = 船长 × 船宽 × 型深 × 0.7）。
