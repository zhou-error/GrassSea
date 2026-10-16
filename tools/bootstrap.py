"""工具引导模块 — 统一实例化并注册 tools/ 下的全部工具

TaskExecutor 通过 build_tool_registry() 拿到已注册的 ToolRegistry（注册即健康检查，
通过后状态置为 ONLINE），从而具备真实派发工具的能力。
"""

from __future__ import annotations

from shared.protocols.tool import BaseTool
from shared.utils.logging import get_logger
from tools.base.registry import ToolRegistry

# CAD 工具
from tools.cad.cad_draw import CadDrawTool
from tools.cad.cad_parse import CadParseTool
from tools.cad.dwg_converter import DwgConverterTool
# 合规工具
from tools.compliance.reg_check import RegCheckTool
# 船舶计算工具
from tools.computation.hydrostatics import HydrostaticsTool
from tools.computation.stability import StabilityTool
from tools.computation.resistance import ResistanceTool
from tools.computation.hull_transform import HullTransformTool
# 文件/检索/报告工具
from tools.file.ocr_engine import OcrEngineTool
from tools.file.pdf_parser import PdfParserTool
from tools.file.todo_manager import TodoManagerTool
from tools.file.web_search import WebSearchTool
from tools.file.workspace import WorkspaceListTool, WorkspaceReadTool, WorkspaceWriteTool
from tools.file.xlsx_parser import XlsxParserTool
from tools.report.report_gen import ReportGenTool

logger = get_logger(__name__)

# tools/ 下全部工具类，注册顺序即列表顺序
TOOL_CLASSES: tuple[type[BaseTool], ...] = (
    CadDrawTool,
    CadParseTool,
    DwgConverterTool,
    RegCheckTool,
    HydrostaticsTool,
    StabilityTool,
    ResistanceTool,
    HullTransformTool,
    OcrEngineTool,
    PdfParserTool,
    TodoManagerTool,
    WebSearchTool,
    WorkspaceListTool,
    WorkspaceReadTool,
    WorkspaceWriteTool,
    XlsxParserTool,
    ReportGenTool,
)


async def build_tool_registry() -> ToolRegistry:
    """实例化 tools/ 下全部工具并注册到 ToolRegistry

    返回的注册中心中每个工具都经过 ToolRegistry._validate_tool 校验；
    健康检查通过的工具状态为 ONLINE，可被 execute_tool 调度。
    """
    registry = ToolRegistry()
    registered: list[str] = []
    rejected: list[str] = []

    for tool_cls in TOOL_CLASSES:
        tool = tool_cls()  # type: ignore[call-arg]
        ok = await registry.register(tool)
        if ok:
            registered.append(tool.manifest.tool_id)
        else:
            rejected.append(tool.manifest.tool_id)

    logger.info(
        "Tool registry built",
        registered=len(registered),
        rejected=rejected,
        tools=registered,
    )
    return registry
