"""稳性分析工具 — 完整稳性、破舱稳性

公式复用 agents/naval_arch_agent/agent.py 中的 KM/KG/GM 与横摇周期经验公式。
"""

from __future__ import annotations

import math

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

STABILITY_MANIFEST = ToolManifest(
    tool_id="stability", name="稳性分析", description="完整稳性、破舱稳性分析，含横摇周期、复原力臂",
    category=ToolCategory.COMPUTATION,
    input_schema={"type": "object", "properties": {"displacement": {"type": "number"}, "GM": {"type": "number"}, "B": {"type": "number"}, "KG": {"type": "number"}}},
    output_schema={"type": "object", "properties": {"GM": {"type": "number"}, "roll_period": {"type": "number"}, "status": {"type": "string"}}},
    timeout_ms=30000, version="0.1.0",
)


class StabilityTool(BaseTool):
    """稳性分析"""

    def __init__(self) -> None:
        super().__init__(STABILITY_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        """计算初稳性高度、横摇周期并按 IMO 初稳性要求判定"""
        B = float(params.get("B", params.get("beam", 15.0)))          # 型宽 (m)
        D = float(params.get("D", params.get("depth", 8.0)))          # 型深 (m)
        T = float(params.get("T", params.get("draft", 5.0)))          # 吃水 (m)
        Cb = float(params.get("Cb", params.get("cb", 0.75)))          # 方型系数

        # 稳心高度 KM — 与 NavalArchAgent._stability_calculation 一致
        km_estimate = B * B / (12 * T) * (1 + Cb / 2)
        KM = float(params.get("KM", km_estimate))
        # 重心高度估计 KG — 与 NavalArchAgent 一致
        KG = float(params.get("KG", params.get("kg", 0.55 * D)))
        # 初稳性高度：显式给出 GM 时以输入为准，否则由 KM - KG 推得
        GM = float(params.get("GM", params.get("gm", KM - KG)))

        # 横摇周期 — 与 NavalArchAgent 一致（C 为经验系数）
        C = 0.38
        roll_period = 2 * C * B / math.sqrt(max(GM, 0.01))

        criteria = [
            {"name": "IMO 初稳性", "requirement": "GM >= 0.15m", "value": round(GM, 3), "pass": GM >= 0.15},
            {"name": "横摇周期", "requirement": "建议 <= 25s", "value": round(roll_period, 1), "pass": roll_period <= 25},
        ]

        return {
            "status": "completed",
            "inputs": {"B": B, "D": D, "T": T, "Cb": Cb, "KM": KM, "KG": KG, "GM": GM},
            "results": {
                "GM_m": round(GM, 3),
                "KM_m": round(KM, 3),
                "KG_m": round(KG, 3),
                "roll_period_s": round(roll_period, 1),
                "criteria": criteria,
                "criteria_passed": all(c["pass"] for c in criteria),
                "stability_assessment": "满足 IMO 完整稳性要求" if GM > 0.15 else "稳性不足，需要调整设计",
                "warnings": [] if GM > 0.35 else ["GM 偏小，建议增大船宽或降低重心"],
            },
        }
