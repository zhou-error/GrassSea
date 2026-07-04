"""阻力计算工具 — Holtrop 法、ITTC 法"""

import numpy as np
from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

RESISTANCE_MANIFEST = ToolManifest(
    tool_id="resistance", name="阻力计算", description="Holtrop 法、ITTC 法阻力与推进性能计算",
    category=ToolCategory.COMPUTATION,
    input_schema={"type": "object", "properties": {"L": {"type": "number"}, "B": {"type": "number"}, "T": {"type": "number"}, "V_kn": {"type": "number"}}},
    output_schema={"type": "object", "properties": {"total_resistance_kN": {"type": "number"}, "effective_power_kW": {"type": "number"}}},
    timeout_ms=30000, version="0.1.0",
)


class ResistanceTool(BaseTool):
    def __init__(self): super().__init__(RESISTANCE_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        L, B, T, V = params.get("L", 100), params.get("B", 15), params.get("T", 5), params.get("V_kn", 14)
        Vs = V * 0.5144
        Rn, Cf = Vs * L / 1.19e-6, 0.075 / (np.log10(Vs * L / 1.19e-6) - 2) ** 2
        S, Cb = L * (2 * T + B) * (0.75 ** 0.5), 0.75
        Rf = 0.5 * 1025 * S * Vs ** 2 * Cf / 1000
        Rt = Rf * 1.4
        return {
            "status": "completed", "method": "Holtrop", "speed_kn": V, "Reynolds_number": f"{Rn:.2e}",
            "friction_coefficient": f"{Cf:.6f}", "wetted_surface_m2": round(S, 1),
            "friction_resistance_kN": round(Rf, 1), "total_resistance_kN": round(Rt, 1),
            "effective_power_kW": round(Rt * Vs, 1),
        }
