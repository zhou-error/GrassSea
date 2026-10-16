"""静水力计算工具

公式复用 agents/naval_arch_agent/agent.py 中的排水量、浮心、稳心经验公式。
"""

from __future__ import annotations

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

HYDROSTATICS_MANIFEST = ToolManifest(
    tool_id="hydrostatics", name="静水力计算", description="排水量、浮心、稳心、邦戎曲线等静水力参数计算",
    category=ToolCategory.COMPUTATION,
    input_schema={"type": "object", "properties": {"L": {"type": "number"}, "B": {"type": "number"}, "T": {"type": "number"}, "Cb": {"type": "number"}}},
    output_schema={"type": "object", "properties": {"displacement": {"type": "number"}, "LCB": {"type": "number"}, "KM": {"type": "number"}}},
    timeout_ms=30000, version="0.1.0",
)


class HydrostaticsTool(BaseTool):
    """静水力计算"""

    def __init__(self) -> None:
        super().__init__(HYDROSTATICS_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        """按经验公式计算静水力参数"""
        L = float(params.get("L", params.get("length", 100.0)))       # 船长 (m)
        B = float(params.get("B", params.get("beam", 15.0)))          # 型宽 (m)
        T = float(params.get("T", params.get("draft", 5.0)))          # 吃水 (m)
        Cb = float(params.get("Cb", params.get("cb", 0.75)))          # 方型系数
        rho = float(params.get("water_density", 1025))                # 水密度 (kg/m³)

        # 排水量 (t) — 与 NavalArchAgent._stability_calculation 一致
        displacement = L * B * T * Cb * rho / 1000
        # 浮心纵向位置 (m，舯前为正)
        lcb = -0.05 * L * (1 - Cb)
        # 稳心高度 (m) — 与 NavalArchAgent 一致
        km = B * B / (12 * T) * (1 + Cb / 2)
        kb = T * 0.5
        bm = km - kb
        # 湿表面积 (m²) — 与 NavalArchAgent._resistance_calculation 一致
        wetted_surface = L * (2 * T + B) * (Cb ** 0.5)

        return {
            "status": "completed",
            "inputs": {"L": L, "B": B, "T": T, "Cb": Cb, "water_density": rho},
            "results": {
                "displacement_t": round(displacement, 1),
                "LCB_m": round(lcb, 3),
                "LCB_from_midship_m": round(lcb, 3),
                "KB_m": round(kb, 3),
                "BM_m": round(bm, 3),
                "KM_m": round(km, 3),
                "block_coefficient": Cb,
                "wetted_surface_m2": round(wetted_surface, 1),
                "method": "经验公式估算（与 NavalArchAgent 静水力估算同一套公式）",
            },
        }
