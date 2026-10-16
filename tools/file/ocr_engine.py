"""图纸 OCR 工具 — 扫描图纸文字/标注识别"""

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest

OCR_ENGINE_MANIFEST = ToolManifest(
    tool_id="ocr_engine", name="图纸 OCR", description="扫描图纸文字/标注识别，支持 PaddleOCR/Tesseract",
    category=ToolCategory.FILE,
    input_schema={"type": "object", "properties": {"image_path": {"type": "string"}, "language": {"type": "string"}}},
    output_schema={"type": "object", "properties": {"text_boxes": {"type": "array"}, "confidence": {"type": "number"}}},
    timeout_ms=60000, version="0.1.0",
)


class OcrEngineTool(BaseTool):
    def __init__(self): super().__init__(OCR_ENGINE_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        """如实返回未实现 — 不返回任何识别结果"""
        return {
            "status": "not_implemented",
            "message": "图纸 OCR 尚未实现：未接入 PaddleOCR/Tesseract 引擎，无法返回文本框与置信度。",
        }
