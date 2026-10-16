"""船型改造工具 — 母型船变换、参数优化

按几何相似对母型船做缩比变换，排水量按 L^3 缩放
（复用 agents/naval_arch_agent/agent.py 的排水量公式）。
"""

from __future__ import annotations

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

HULL_TRANSFORM_MANIFEST = ToolManifest(
    tool_id="hull_transform", name="船型改造", description="母型船变换、参数优化、多方案对比",
    category=ToolCategory.COMPUTATION,
    input_schema={"type": "object", "properties": {"parent_L": {"type": "number"}, "target_L": {"type": "number"}, "method": {"type": "string"}}},
    output_schema={"type": "object", "properties": {"scale_ratio": {"type": "number"}, "new_parameters": {"type": "object"}}},
    timeout_ms=60000, version="0.1.0",
)


class HullTransformTool(BaseTool):
    """母型船变换"""

    def __init__(self) -> None:
        super().__init__(HULL_TRANSFORM_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        """按主尺度缩比生成新船参数并核验排水量缩放关系"""
        parent_L = float(params.get("parent_L", params.get("L", 100.0)))
        target_L = float(params.get("target_L", 120.0))
        method = str(params.get("method", "length_scale"))
        if parent_L <= 0 or target_L <= 0:
            return {"status": "error", "message": "parent_L 与 target_L 必须为正数"}

        parent_B = float(params.get("parent_B", params.get("B", 15.0)))
        parent_D = float(params.get("parent_D", params.get("D", 8.0)))
        parent_T = float(params.get("parent_T", params.get("T", 5.0)))
        Cb = float(params.get("Cb", params.get("cb", 0.75)))
        rho = float(params.get("water_density", 1025))

        ratio = target_L / parent_L
        new_parameters = {
            "L": round(target_L, 3),
            "B": round(parent_B * ratio, 3),
            "D": round(parent_D * ratio, 3),
            "T": round(parent_T * ratio, 3),
        }

        # 排水量 — 与 NavalArchAgent._stability_calculation 一致
        parent_displacement = parent_L * parent_B * parent_T * Cb * rho / 1000
        target_displacement = (
            new_parameters["L"] * new_parameters["B"] * new_parameters["T"] * Cb * rho / 1000
        )

        warnings: list[str] = []
        if ratio > 1.2:
            warnings.append("缩放比超过 1.2，建议进行 CFD 验证")
        if ratio < 0.8:
            warnings.append("缩放比小于 0.8，建议复核型线与总布置")

        return {
            "status": "completed",
            "inputs": {
                "parent_L": parent_L, "parent_B": parent_B, "parent_D": parent_D,
                "parent_T": parent_T, "target_L": target_L, "Cb": Cb,
                "water_density": rho, "method": method,
            },
            "results": {
                "method": method,
                "scale_ratio": round(ratio, 4),
                "new_parameters": new_parameters,
                "parent_displacement_t": round(parent_displacement, 1),
                "target_displacement_t": round(target_displacement, 1),
                "displacement_ratio": round(target_displacement / parent_displacement, 4),
                "block_coefficient": Cb,
                "warnings": warnings,
            },
        }
