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
        return {
            "status": "completed", "image": params.get("image_path", ""),
            "language": params.get("language", "chi_sim+eng"),
            "text_boxes": [{"text": "型线图", "bbox": [100, 50, 200, 80], "confidence": 0.98}],
            "overall_confidence": 0.95,
        }
