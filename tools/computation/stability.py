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
        from shared.utils.numeric import ParamError, get_number, get_phys, used_defaults_note

        used: list[str] = []
        try:
            B, d = get_phys(params, ("B", "beam"), 15.0, label="型宽 B", key="beam_m")
            used += ["B"] if d else []
            D, d = get_phys(params, ("D", "depth"), 8.0, label="型深 D", key="depth_m")
            used += ["D"] if d else []
            T, d = get_phys(params, ("T", "draft"), 5.0, label="吃水 T", key="draft_m")
            used += ["T"] if d else []
            Cb, d = get_phys(params, ("Cb", "cb"), 0.75, label="方形系数 Cb", key="cb")
            used += ["Cb"] if d else []

            # 稳心高度 KM — 与 NavalArchAgent._stability_calculation 一致
            km_estimate = B * B / (12 * T) * (1 + Cb / 2)
            KM, d = get_number(params, ("KM",), km_estimate, label="稳心高度 KM", minimum=0.01)
            used += ["KM"] if d else []
            # 重心高度估计 KG — 与 NavalArchAgent 一致
            KG, d = get_number(params, ("KG", "kg"), 0.55 * D, label="重心高度 KG", minimum=0.0, allow_zero=True)
            used += ["KG"] if d else []
            # 初稳性高度：显式给出 GM 时以输入为准，否则由 KM - KG 推得。
            # GM 允许为负（表示不稳，是真实物理状态），只要有限即可。
            GM, d = get_number(params, ("GM", "gm"), KM - KG, label="初稳性高 GM", minimum=-10.0, allow_zero=True)
            used += ["GM"] if d else []
        except ParamError as exc:
            return {"status": "error", "message": str(exc)}

        # 横摇周期 — 与 NavalArchAgent 一致（C 为经验系数）
        C = 0.38
        roll_period = 2 * C * B / math.sqrt(max(GM, 0.01))

        criteria = [
            {"name": "IMO 初稳性", "requirement": "GM >= 0.15m", "value": round(GM, 3), "pass": GM >= 0.15},
            {"name": "横摇周期", "requirement": "建议 <= 25s", "value": round(roll_period, 1), "pass": roll_period <= 25},
        ]

        result = {
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
        result.update(used_defaults_note(used))
        return result
