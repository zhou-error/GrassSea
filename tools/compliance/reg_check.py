"""规范合规审查工具 — 基于规范条文自动审查设计参数"""

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

REG_CHECK_MANIFEST = ToolManifest(
    tool_id="reg_check", name="规范合规审查", description="基于规范条文自动审查设计参数是否符合要求",
    category=ToolCategory.COMPLIANCE,
    input_schema={"type": "object", "properties": {"design_params": {"type": "object"}, "regulation_codes": {"type": "array", "items": {"type": "string"}}}},
    output_schema={"type": "object", "properties": {"pass": {"type": "boolean"}, "violations": {"type": "array"}}},
    timeout_ms=30000, requires_auth=True, rate_limit_per_min=30, version="0.1.0",
)


class RegCheckTool(BaseTool):
    def __init__(self): super().__init__(REG_CHECK_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        design_params = params.get("design_params", {})
        codes = params.get("regulation_codes", ["CCS"])
        violations, suggestions, passed = [], [], []

        checks = {
            "bulkhead_spacing": {"min": 600, "max": 3500, "unit": "mm", "clause": "CCS §2.5.3"},
            "web_frame_spacing": {"min": 500, "max": 4000, "unit": "mm", "clause": "CCS §2.5.4"},
            "hull_plate_thickness": {"min": 6, "max": 40, "unit": "mm", "clause": "CCS §3.2.1"},
        }

        for param, value in design_params.items():
            check = checks.get(param)
            if check and isinstance(value, (int, float)):
                if value < check["min"]:
                    violations.append({"parameter": param, "value": value, "requirement": f">= {check['min']}{check['unit']}", "clause": check["clause"], "severity": "error"})
                    suggestions.append({"parameter": param, "suggestion": f"增大 {param} 至 ≥{check['min']}{check['unit']}", "priority": "high"})
                elif value > check["max"]:
                    violations.append({"parameter": param, "value": value, "requirement": f"<= {check['max']}{check['unit']}", "clause": check["clause"], "severity": "warning"})
                else:
                    passed.append(param)

        return {"status": "completed", "pass": len(violations) == 0, "violations": violations, "suggestions": suggestions, "passed_checks": len(passed) + len(violations), "codes_checked": codes}
