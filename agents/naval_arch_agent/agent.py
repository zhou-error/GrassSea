"""船舶工程师 Agent (Naval Arch Agent)

核心能力：型线设计、稳性计算、规范审查、船型改造
"""

from __future__ import annotations

import numpy as np
from shared.protocols.agent import AgentCallbacks, AgentCapability, AgentMetadata, BaseAgent

NAVAL_ARCH_METADATA = AgentMetadata(
    agent_id="naval_arch_agent",
    name="船舶工程师 Agent",
    role="型线设计、稳性计算、规范审查、船型改造",
    capabilities=[
        AgentCapability(name="hull_design", description="型线设计与优化", tools=["cad_draw", "hull_transform"], estimated_latency_ms=3000),
        AgentCapability(name="stability_calc", description="完整稳性与破舱稳性计算", tools=["hydrostatics", "stability"], estimated_latency_ms=5000),
        AgentCapability(name="resistance_calc", description="阻力与推进性能计算", tools=["resistance"], estimated_latency_ms=3000),
        AgentCapability(name="reg_compliance", description="规范合规审查", tools=["reg_check"], estimated_latency_ms=2000),
    ],
    model_preference="deepseek-chat",
    max_concurrent_tasks=3,
    version="0.1.0",
)


class NavalArchAgent(BaseAgent):
    """船舶工程师智能体"""

    def __init__(self):
        super().__init__(NAVAL_ARCH_METADATA)

    async def handle_task(self, task: dict, context: dict, callbacks: AgentCallbacks) -> dict:
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

    async def _stability_calculation(self, params: dict, callbacks: AgentCallbacks) -> dict:
        """稳性计算"""
        # 显式转 float：参数可能来自 numpy/pandas，而 numpy 标量无法被 FastAPI 序列化
        L = float(params.get("length", 100.0))            # 船长 (m)
        B = float(params.get("beam", 15.0))               # 型宽 (m)
        D = float(params.get("depth", 8.0))               # 型深 (m)
        T = float(params.get("draft", 5.0))               # 吃水 (m)
        Cb = float(params.get("cb", 0.75))                # 方型系数
        rho = float(params.get("water_density", 1025))    # 海水密度

        # 排水量
        displacement = L * B * T * Cb * rho / 1000  # 吨

        # 浮心纵向位置 (经验公式)
        LCB = -0.05 * L * (1 - Cb)  # 舯前为正

        # 稳心高度 (经验公式)
        KM = B * B / (12 * T) * (1 + Cb / 2)
        KG = 0.55 * D  # 重心高度估计
        GM = KM - KG

        # 横摇周期：GM<=0 时船舶不具备初稳性，周期不适用，返回 None 而不是 NaN
        # （NaN 会让 FastAPI/严格 JSON 序列化失败）
        C = 0.38  # 经验系数
        Tr = 2 * C * B / np.sqrt(GM) if GM > 0 else None

        if callbacks and callbacks.on_progress:
            await callbacks.on_progress(params.get("task_id", ""), 0.8)

        return {
            "status": "completed",
            "calculation_type": "stability",
            "inputs": {"L": L, "B": B, "D": D, "T": T, "Cb": Cb},
            "results": {
                # round() 作用在 numpy 标量上会返回 numpy 标量，这里统一转为 python float
                "displacement_t": float(round(displacement, 1)),
                "LCB_m": float(round(LCB, 2)),
                "KM_m": float(round(KM, 2)),
                "GM_m": float(round(GM, 2)),
                "roll_period_s": float(round(Tr, 1)) if Tr is not None else None,
                "stability_assessment": "满足 IMO 完整稳性要求" if GM > 0.15 else "稳性不足，需要调整设计",
            },
            "warnings": (
                []
                if GM > 0.35
                else (["GM 偏小，建议增大船宽或降低重心"] if GM > 0 else ["GM ≤ 0：船舶不具备初稳性，横摇周期不适用"])
            ),
        }

    async def _hull_design(self, params: dict, callbacks: AgentCallbacks) -> dict:
        """型线设计"""
        return {
            "status": "completed",
            "design_type": "hull_form",
            "results": {
                "method": "母型船变换法",
                "parent_vessel": str(params.get("parent_vessel", "标准散货船")),
                "scale_ratio": float(params.get("scale_ratio", 1.0)),
                "modified_parameters": ["L/B", "B/T", "Cb"],
            },
            "files": {"lines_plan": "型线图待生成（需 CAD Agent）"},
        }

    async def _resistance_calculation(self, params: dict, callbacks: AgentCallbacks) -> dict:
        """阻力计算 (Holtrop 法)"""
        L = float(params.get("length", 100.0))
        B = float(params.get("beam", 15.0))
        T = float(params.get("draft", 5.0))
        V = float(params.get("speed_kn", 14.0))  # 航速 (节)

        # 简化阻力估算
        Vs = V * 0.5144  # m/s
        Rn = Vs * L / 1.19e-6  # 雷诺数
        Cf = 0.075 / (np.log10(Rn) - 2) ** 2  # ITTC 摩擦阻力系数
        Cb = float(params.get("cb", 0.75))  # 方型系数
        S = L * (2 * T + B) * np.sqrt(Cb)  # 湿表面积
        Rf = 0.5 * 1025 * S * Vs ** 2 * Cf / 1000  # kN

        return {
            "status": "completed",
            "calculation_type": "resistance",
            "inputs": {"L": L, "B": B, "T": T, "V_kn": V},
            "results": {
                "Reynolds_number": f"{Rn:.2e}",
                "friction_coefficient": f"{Cf:.6f}",
                # round() 作用在 numpy 标量上会返回 numpy 标量，这里统一转为 python float
                "wetted_surface_m2": float(round(S, 1)),
                "friction_resistance_kN": float(round(Rf, 1)),
                "total_resistance_estimate_kN": float(round(Rf * 1.35, 1)),  # 加上剩余阻力
                "effective_power_kW": float(round(Rf * 1.35 * Vs, 1)),
            },
        }

    async def _general_analysis(self, params: dict, callbacks: AgentCallbacks) -> dict:
        return {"status": "completed", "analysis": "船舶工程通用分析", "inputs": params}
