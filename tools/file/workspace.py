"""工作文件夹工具 — 让模型按需读写用户选定文件夹中的文件

三个工具：
  workspace_list   列出目录内容
  workspace_read   读取文本文件
  workspace_write  写入文本文件（保存模型产出）

仅在桌面模式（DESKTOP_MODE=true）且用户已选择工作文件夹时可用；
路径越界、文件过大、覆盖未授权等情况一律返回 error 并给出中文原因。
"""

from __future__ import annotations

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest
from shared.utils import workspace as ws

LIST_MANIFEST = ToolManifest(
    tool_id="workspace_list",
    name="列出工作文件夹",
    description=(
        "列出用户选定工作文件夹中某个目录的内容（只列一层）。"
        "在不确定文件夹里有哪些文件、或需要确认某文件是否存在时使用。"
        "不传 path 时列出根目录。"
    ),
    category=ToolCategory.FILE,
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "相对工作文件夹的目录路径，留空表示根目录"},
        },
        "required": [],
    },
    output_schema={
        "type": "object",
        "properties": {
            "root": {"type": "string"},
            "path": {"type": "string"},
            "entries": {"type": "array"},
            "count": {"type": "integer"},
            "status": {"type": "string"},
        },
    },
    timeout_ms=15000,
    version="0.1.0",
)

READ_MANIFEST = ToolManifest(
    tool_id="workspace_read",
    name="读取工作文件夹中的文件",
    description=(
        "读取用户选定工作文件夹中某个文件的内容，自动提取纯文本。"
        "支持：文本类（txt/md/csv/json/yaml/代码等，UTF-8/GB18030 自动识别）、"
        "PDF（提取文本层）、Word（.docx）、Excel（.xlsx/.xlsm，逐表转为 CSV 风格文本）。"
        "在需要依据用户现有资料作答时使用——包括设计说明书、型值表、计算表格这类工程资料。"
        "不支持：旧版 .doc/.xls（请先另存为新格式）、.dwg/.dxf（CAD 能力未实现）、"
        "扫描版 PDF（无 OCR）。这些情况会返回明确原因与替代做法，不会返回乱码。"
    ),
    category=ToolCategory.FILE,
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "相对工作文件夹的文件路径，例如 data/型值表.csv"},
        },
        "required": ["path"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "size": {"type": "integer"},
            "format": {"type": "string", "description": "pdf/docx/xlsx/text"},
            "parser": {"type": "string", "description": "实际使用的解析器"},
            "chars": {"type": "integer"},
            "text": {"type": "string"},
            "truncated": {"type": "boolean"},
            "status": {"type": "string"},
        },
    },
    timeout_ms=20000,
    version="0.1.0",
)

WRITE_MANIFEST = ToolManifest(
    tool_id="workspace_write",
    name="把结果保存到工作文件夹",
    description=(
        "把文本内容写入用户选定工作文件夹中的文件，用于保存计算书、报告、表格等产出。"
        "用户未指定保存格式时，请根据内容自行选择合适的扩展名"
        "（说明性内容用 .md，表格用 .csv，结构化数据用 .json，纯文本用 .txt，脚本用 .py）。"
        "目标文件已存在时必须显式传 overwrite=true 才会覆盖。"
    ),
    category=ToolCategory.FILE,
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "相对工作文件夹的目标路径，含文件名与扩展名"},
            "content": {"type": "string", "description": "要写入的完整文本内容"},
            "overwrite": {"type": "boolean", "description": "目标已存在时是否覆盖，默认 false"},
        },
        "required": ["path", "content"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "bytes": {"type": "integer"},
            "created": {"type": "boolean"},
            "status": {"type": "string"},
        },
    },
    timeout_ms=20000,
    version="0.1.0",
)


class _WorkspaceToolBase(BaseTool):
    """统一处理启用检查与异常转错误结果"""

    async def execute(self, params: dict, context: dict) -> dict:  # pragma: no cover - 抽象
        raise NotImplementedError

    def _guard(self) -> dict | None:
        if not ws.is_enabled():
            return {
                "status": "not_implemented",
                "message": "工作文件夹功能仅在桌面模式下可用（请用 app.launcher --desktop 启动）。",
            }
        if ws.get_root() is None:
            return {
                "status": "error",
                "message": "用户尚未选择工作文件夹，请先在界面上选择一个文件夹。",
            }
        return None

    @staticmethod
    def _fail(exc: Exception) -> dict:
        return {"status": "error", "message": str(exc)}


class WorkspaceListTool(_WorkspaceToolBase):
    """列出工作文件夹目录"""

    def __init__(self) -> None:
        super().__init__(LIST_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        guard = self._guard()
        if guard:
            return guard
        try:
            result = ws.list_dir(str(params.get("path") or ""))
        except Exception as exc:  # noqa: BLE001
            return self._fail(exc)
        result["status"] = "completed"
        return result


class WorkspaceReadTool(_WorkspaceToolBase):
    """读取工作文件夹中的文件"""

    def __init__(self) -> None:
        super().__init__(READ_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        guard = self._guard()
        if guard:
            return guard
        path = str(params.get("path") or "").strip()
        if not path:
            return {"status": "error", "message": "必须提供 path"}
        try:
            result = ws.read_file(path)
        except Exception as exc:  # noqa: BLE001
            return self._fail(exc)
        result["status"] = "completed"
        return result


class WorkspaceWriteTool(_WorkspaceToolBase):
    """把内容写入工作文件夹"""

    def __init__(self) -> None:
        super().__init__(WRITE_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        guard = self._guard()
        if guard:
            return guard
        path = str(params.get("path") or "").strip()
        content = params.get("content")
        if not path:
            return {"status": "error", "message": "必须提供 path"}
        if not isinstance(content, str):
            return {"status": "error", "message": "必须提供字符串类型的 content"}
        try:
            result = ws.write_file(path, content, bool(params.get("overwrite", False)))
        except Exception as exc:  # noqa: BLE001
            return self._fail(exc)
        result["status"] = "completed"
        return result
