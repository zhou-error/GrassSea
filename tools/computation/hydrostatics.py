"""静水力计算工具"""

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

HYDROSTATICS_MANIFEST = ToolManifest(
    tool_id="hydrostatics", name="静水力计算", description="排水量、浮心、稳心、邦戎曲线等静水力参数计算",
    category=ToolCategory.COMPUTATION,
    input_schema={"type": "object", "properties": {"L": {"type": "number"}, "B": {"type": "number"}, "T": {"type": "number"}, "Cb": {"type": "number"}}},
    output_schema={"type": "object", "properties": {"displacement": {"type": "number"}, "LCB": {"type": "number"}, "KM": {"type": "number"}}},
    timeout_ms=30000, version="0.1.0",
)


class HydrostaticsTool(BaseTool):
    def __init__(self): super().__init__(HYDROSTATICS_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        L, B, T, Cb = params.get("L", 100), params.get("B", 15), params.get("T", 5), params.get("Cb", 0.75)
        disp = L * B * T * Cb * 1.025
        lcb = -0.05 * L * (1 - Cb)
        km = B * B / (12 * T) * (1 + Cb / 2)
        return {
            "status": "completed",
            "displacement_t": round(disp, 1), "LCB_m": round(lcb, 2), "LCB_from_midship": round(lcb, 2),
            "KM_m": round(km, 2), "KB_m": round(T * 0.5, 2), "BM_m": round(km - T * 0.5, 2),
            "block_coefficient": Cb, "wetted_surface_m2": round(L * (2 * T + B) * (Cb ** 0.5), 1),
        }
