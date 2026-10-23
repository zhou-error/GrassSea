"""阻力计算工具 — Holtrop 法、ITTC 法

公式复用 agents/naval_arch_agent/agent.py 中的 ITTC 摩擦阻力系数与湿表面积估算。
"""

from __future__ import annotations

import math

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

RESISTANCE_MANIFEST = ToolManifest(
    tool_id="resistance", name="阻力计算", description="Holtrop 法、ITTC 法阻力与推进性能计算",
    category=ToolCategory.COMPUTATION,
    input_schema={"type": "object", "properties": {"L": {"type": "number"}, "B": {"type": "number"}, "T": {"type": "number"}, "V_kn": {"type": "number"}}},
    output_schema={"type": "object", "properties": {"total_resistance_kN": {"type": "number"}, "effective_power_kW": {"type": "number"}}},
    timeout_ms=30000, version="0.1.0",
)


class ResistanceTool(BaseTool):
    """阻力与有效功率计算"""

    def __init__(self) -> None:
        super().__init__(RESISTANCE_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        """按 ITTC-1957 摩擦阻力系数估算总阻力与有效功率"""
        from shared.utils.numeric import ParamError, get_phys, used_defaults_note

        used: list[str] = []
        try:
            L, d = get_phys(params, ("L", "length"), 100.0, label="船长 L", key="length_m")
            used += ["L"] if d else []
            B, d = get_phys(params, ("B", "beam"), 15.0, label="型宽 B", key="beam_m")
            used += ["B"] if d else []
            T, d = get_phys(params, ("T", "draft"), 5.0, label="吃水 T", key="draft_m")
            used += ["T"] if d else []
            V, d = get_phys(params, ("V_kn", "speed_kn"), 14.0, label="航速 V", key="speed_kn")
            used += ["V_kn"] if d else []
            Cb, d = get_phys(params, ("Cb", "cb"), 0.75, label="方形系数 Cb", key="cb")
            used += ["Cb"] if d else []
            rho, d = get_phys(params, ("water_density",), 1025.0, label="水密度", key="rho")
            used += ["water_density"] if d else []
        except ParamError as exc:
            return {"status": "error", "message": str(exc)}

        Vs = V * 0.5144                       # 航速 (m/s)
        Rn = Vs * L / 1.19e-6                 # 雷诺数
        Cf = 0.075 / (math.log10(Rn) - 2) ** 2  # ITTC 摩擦阻力系数
        S = L * (2 * T + B) * math.sqrt(Cb)   # 湿表面积 (m²)
        Rf = 0.5 * rho * S * Vs ** 2 * Cf / 1000   # 摩擦阻力 (kN)
        Rt = Rf * 1.35                        # 计入剩余阻力的总阻力估算 (kN)
        Pe = Rt * Vs                          # 有效功率 (kW)

        result = {
            "status": "completed",
            "inputs": {"L": L, "B": B, "T": T, "V_kn": V, "Cb": Cb, "water_density": rho},
            "results": {
                "method": "ITTC-1957 摩擦阻力 + 剩余阻力系数 1.35（与 NavalArchAgent 同一套公式）",
                "speed_m_s": round(Vs, 3),
                "Reynolds_number": f"{Rn:.2e}",
                "friction_coefficient": f"{Cf:.6f}",
                "wetted_surface_m2": round(S, 1),
                "friction_resistance_kN": round(Rf, 1),
                "total_resistance_kN": round(Rt, 1),
                "effective_power_kW": round(Pe, 1),
            },
        }
        result.update(used_defaults_note(used))
        return result
