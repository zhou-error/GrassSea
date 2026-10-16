"""联网搜索工具 — 补充最新信息"""

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

WEB_SEARCH_MANIFEST = ToolManifest(
    tool_id="web_search", name="联网搜索", description="联网搜索补充最新信息，支持 Brave Search / Bing API",
    category=ToolCategory.SEARCH,
    input_schema={"type": "object", "properties": {"query": {"type": "string"}, "num_results": {"type": "integer"}}},
    output_schema={"type": "object", "properties": {"results": {"type": "array"}, "total": {"type": "integer"}}},
    timeout_ms=15000, version="0.1.0",
)


class WebSearchTool(BaseTool):
    def __init__(self): super().__init__(WEB_SEARCH_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        """如实返回未实现 — 不返回任何检索结果"""
        return {
            "status": "not_implemented",
            "message": "联网搜索尚未实现：未配置 Brave/Bing 搜索 API Key，无法返回真实检索结果。",
        }
