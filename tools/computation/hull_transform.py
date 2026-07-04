"""船型改造工具 — 母型船变换、参数优化"""

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

HULL_TRANSFORM_MANIFEST = ToolManifest(
    tool_id="hull_transform", name="船型改造", description="母型船变换、参数优化、多方案对比",
    category=ToolCategory.COMPUTATION,
    input_schema={"type": "object", "properties": {"parent_L": {"type": "number"}, "target_L": {"type": "number"}, "method": {"type": "string"}}},
    output_schema={"type": "object", "properties": {"scale_ratio": {"type": "number"}, "new_parameters": {"type": "object"}}},
    timeout_ms=60000, version="0.1.0",
)


class HullTransformTool(BaseTool):
    def __init__(self): super().__init__(HULL_TRANSFORM_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        parent_L, target_L = params.get("parent_L", 100), params.get("target_L", 120)
        ratio = target_L / parent_L
        return {
            "status": "completed", "method": params.get("method", "length_scale"),
            "scale_ratio": round(ratio, 4), "parent_L": parent_L, "target_L": target_L,
            "new_parameters": {"L": target_L, "B": round(15 * ratio, 1), "D": round(8 * ratio, 1), "T": round(5 * ratio, 1)},
            "warnings": ["缩放比超过 1.2，建议进行 CFD 验证"] if ratio > 1.2 else [],
        }
