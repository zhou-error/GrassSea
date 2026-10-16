"""待办管理工具 — 创建/更新/提醒待办事项"""

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

TODO_MANAGER_MANIFEST = ToolManifest(
    tool_id="todo_manager", name="待办管理", description="创建/更新/提醒待办事项，与 PostgreSQL 同步",
    category=ToolCategory.FILE,
    input_schema={"type": "object", "properties": {"action": {"type": "string"}, "title": {"type": "string"}, "priority": {"type": "string"}}},
    output_schema={"type": "object", "properties": {"todo_id": {"type": "string"}, "status": {"type": "string"}}},
    timeout_ms=10000, version="0.1.0",
)


class TodoManagerTool(BaseTool):
    def __init__(self): super().__init__(TODO_MANAGER_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        """如实返回未实现 — 不创建或更新任何待办"""
        return {
            "status": "not_implemented",
            "message": "待办管理尚未实现：未接入 PostgreSQL 待办表，无法持久化待办事项。",
        }
