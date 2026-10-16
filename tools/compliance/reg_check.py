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
        """如实返回未实现 — 不给出任何合规判定"""
        return {
            "status": "not_implemented",
            "message": "规范合规审查尚未实现：未接入规范条文知识库/RAG，无法给出条文级判定，因此不返回 pass/violations 结论。",
        }
