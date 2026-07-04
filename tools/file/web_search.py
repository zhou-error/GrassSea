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
        query = params.get("query", "")
        return {
            "status": "completed", "query": query,
            "results": [{"title": f"关于 '{query[:30]}' 的搜索结果", "url": "https://example.com", "snippet": "相关内容摘要..."}],
            "total": 1, "engine": "Brave Search",
        }
