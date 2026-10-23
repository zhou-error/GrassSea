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
        from shared.utils.numeric import ParamError, get_phys, used_defaults_note

        ALLOWED_METHODS = ("length_scale",)
        method = str(params.get("method", "length_scale") or "length_scale")
        if method not in ALLOWED_METHODS:
            # 审计 S3-2 同类问题：枚举值不校验会被静默接受
            return {
                "status": "error",
                "message": f"method 只支持 {'/'.join(ALLOWED_METHODS)}，收到 {method!r}",
            }

        used: list[str] = []
        try:
            parent_L, d = get_phys(params, ("parent_L", "L"), 100.0, label="母型船长 parent_L", key="length_m")
            used += ["parent_L"] if d else []
            target_L, d = get_phys(params, ("target_L",), 120.0, label="目标船长 target_L", key="length_m")
            used += ["target_L"] if d else []
            parent_B, d = get_phys(params, ("parent_B", "B"), 15.0, label="母型型宽 parent_B", key="beam_m")
            used += ["parent_B"] if d else []
            parent_D, d = get_phys(params, ("parent_D", "D"), 8.0, label="母型型深 parent_D", key="depth_m")
            used += ["parent_D"] if d else []
            parent_T, d = get_phys(params, ("parent_T", "T"), 5.0, label="母型吃水 parent_T", key="draft_m")
            used += ["parent_T"] if d else []
            Cb, d = get_phys(params, ("Cb", "cb"), 0.75, label="方形系数 Cb", key="cb")
            used += ["Cb"] if d else []
            rho, d = get_phys(params, ("water_density",), 1025.0, label="水密度", key="rho")
            used += ["water_density"] if d else []
        except ParamError as exc:
            return {"status": "error", "message": str(exc)}

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

        result = {
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
        result.update(used_defaults_note(used))
        return result
