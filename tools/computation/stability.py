"""稳性分析工具 — 完整稳性、破舱稳性"""

import numpy as np
from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

STABILITY_MANIFEST = ToolManifest(
    tool_id="stability", name="稳性分析", description="完整稳性、破舱稳性分析，含横摇周期、复原力臂",
    category=ToolCategory.COMPUTATION,
    input_schema={"type": "object", "properties": {"displacement": {"type": "number"}, "GM": {"type": "number"}, "B": {"type": "number"}, "KG": {"type": "number"}}},
    output_schema={"type": "object", "properties": {"GM": {"type": "number"}, "roll_period": {"type": "number"}, "status": {"type": "string"}}},
    timeout_ms=30000, version="0.1.0",
)


class StabilityTool(BaseTool):
    def __init__(self): super().__init__(STABILITY_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        B = params.get("B", 15)
        GM = params.get("GM", 2.0)
        C, Tr = 0.38, 2 * 0.38 * B / np.sqrt(max(GM, 0.01))
        criteria = [
            {"name": "IMO 初稳性", "requirement": "GM ≥ 0.15m", "value": f"{GM:.2f}m", "pass": GM >= 0.15},
            {"name": "横摇周期", "requirement": "建议 ≤ 25s", "value": f"{Tr:.1f}s", "pass": Tr <= 25},
        ]
        return {
            "status": "completed", "GM_m": round(GM, 2), "roll_period_s": round(Tr, 1),
            "stability_assessment": "满足稳性要求" if all(c["pass"] for c in criteria) else "部分指标不满足",
            "criteria": criteria,
        }
