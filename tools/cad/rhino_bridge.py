"""Rhino 建模桥接工具

把模型给出的建模意图翻译成一条桥接操作，交给 Rhino 侧脚本执行。
本工具**不生成 Python 代码**、不直接调用 RhinoCommon。

安全策略：
- 受配置 RHINO_BRIDGE_ENABLED 控制，默认关闭；
- boolean / delete 属于破坏性操作，bake=true 时必须显式 confirm=true；
- Rhino 未连接时如实返回错误，不伪造 object_id 或文件路径。
"""

from __future__ import annotations

import re
import time

from shared.protocols.tool import BaseTool, ToolCategory, ToolManifest
from shared.utils.config import get_settings
from shared.utils.logging import get_logger
from tools.cad.rhino_client import RhinoBridgeError, RhinoClient
from tools.cad.rhino_schema import ALLOWED_OPERATIONS, validate

logger = get_logger(__name__)

#: 破坏性操作：写入文档前必须确认
DESTRUCTIVE_OPERATIONS = frozenset({"boolean", "delete"})


def _needs_confirm(operation: str, params: dict) -> bool:
    """是否需要用户确认

    - boolean / delete：本身就会改变或删除既有几何；
    - split：keep_input=false 会删掉原始对象，等同于删除，需确认；
      keep_input=true 只新增片体，属非破坏。
    """
    if operation in DESTRUCTIVE_OPERATIONS:
        return True
    if operation in ("split", "join") and not bool(params.get("keep_input", False)):
        return True
    return False

RHINO_MANIFEST = ToolManifest(
    tool_id="rhino_bridge",
    name="Rhino 建模桥接",
    description=(
        "通过本地桥接，在已打开的 Rhino 8 中执行建模操作。"
        "通用：create_curve（插值曲线）、extrude（沿曲线法向挤出）、boolean（并/差/交）、"
        "delete、query。"
        "船体建模：loft_sections（断面点表直连放样，船体首选）、loft（按已有曲线放样）、"
        "mirror（镜像到另一舷）、"
        "split（按平面切分甲板/艉封板）、offset_srf（偏移成壳/板厚）、"
        "join（缝合曲面成整体，形成封闭实体的关键）、"
        "mass_properties（面积/体积/质心，用于核对排水量）。"
        "boolean 与 delete 属于破坏性操作，bake=true 时必须带 confirm=true。"
        "Rhino 未启动或桥接未运行时，会明确返回「桥接未连接」，不会伪造结果。"
    ),
    category=ToolCategory.CAD,
    input_schema={
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": sorted(ALLOWED_OPERATIONS),
                "description": "要执行的操作",
            },
            "params": {
                "type": "object",
                "description": (
                    "操作参数。\n"
                    "create_curve: {points:[[x,y,z]...], degree?, closed?}\n"
                    "extrude: {curve_id, height, cap?}\n"
                    "boolean: {brep_id_a, brep_id_b, operation:union|difference|intersection, tolerance}\n"
                    "delete / query / mass_properties: {object_ids:[...]}\n"
                    "loft: {curve_ids:[...], closed?, solid?}\n"
                    "loft_sections: {sections:[...], closed_sections?, solid?, keep_curves?, degree?}\n"
                    "mirror: {object_ids:[...], plane?:yz|xz|xy, copy?}\n"
                    "split: {object_ids:[...], plane?:yz|xz|xy, keep_input?}\n"
                    "offset_srf: {object_id, distance, solid?}"
                ),
            },
            "bake": {
                "type": "boolean",
                "description": "true=写入 Rhino 文档；false=只算不写（预览）。默认 true",
            },
            "confirm": {
                "type": "boolean",
                "description": "破坏性操作（boolean/delete）写入前必须为 true",
            },
        },
        "required": ["operation", "params"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "operation": {"type": "string"},
            "object_ids": {"type": "array", "items": {"type": "string"}},
            "preview_info": {"type": "object"},
            "message": {"type": "string"},
        },
    },
    timeout_ms=60000,
    requires_auth=True,
    rate_limit_per_min=20,
    version="0.1.0",
)


class RhinoBridgeTool(BaseTool):
    """Rhino 桥接执行器"""

    def __init__(self) -> None:
        super().__init__(RHINO_MANIFEST)

    # ---------- 配置 ----------

    @staticmethod
    def _settings_bundle() -> tuple[bool, str, str, int]:
        s = get_settings()
        enabled = bool(getattr(s, "RHINO_BRIDGE_ENABLED", False))
        url = (getattr(s, "RHINO_BRIDGE_URL", "") or "http://127.0.0.1:8765").strip()
        token_file = (getattr(s, "RHINO_BRIDGE_TOKEN_FILE", "") or "").strip()
        if not token_file:
            # 未显式配置时，与 Rhino 侧脚本约定放在数据目录
            from pathlib import Path as _Path

            data_dir = (getattr(s, "DATA_DIR", "") or "").strip()
            base = _Path(data_dir) if data_dir else (s.PROJECT_ROOT / "data")
            token_file = str(base / "bridge.token")
        timeout_ms = int(getattr(s, "RHINO_BRIDGE_TIMEOUT_MS", 30000) or 30000)
        return enabled, url, token_file, timeout_ms

    @staticmethod
    def _read_token(token_file: str) -> str:
        """取令牌

        支持两种填法（实测用户把令牌值直接填进了"路径"栏）：
        1. 32 位十六进制 → 视为令牌本身；
        2. 其它 → 视为文件路径，读取内容。
        """
        raw = (token_file or "").strip()
        if not raw:
            return ""
        if re.fullmatch(r"[0-9a-fA-F]{32}", raw):
            return raw
        try:
            from pathlib import Path

            path = Path(raw)
            return path.read_text(encoding="utf-8").strip() if path.exists() else ""
        except OSError:
            return ""

    # ---------- 单位缓存 ----------

    _unit_cache: dict[str, tuple[str, float]] = {}
    UNIT_TTL = 60.0

    async def _document_unit(self, client: RhinoClient) -> str:
        """取当前文档单位（缓存 60 秒；取不到时按 mm 处理并记录）"""
        key = client.base_url
        cached = self._unit_cache.get(key)
        now = time.time()
        if cached and now - cached[1] < self.UNIT_TTL:
            return cached[0]
        try:
            info = await client.hello()
            unit = str(info.get("units") or "mm").lower()
        except RhinoBridgeError:
            unit = "mm"
            logger.debug("握手失败，单位按 mm 处理", url=key)
        self._unit_cache[key] = (unit, now)
        return unit

    # ---------- 执行 ----------

    async def execute(self, params: dict, context: dict) -> dict:
        enabled, url, token_file, timeout_ms = self._settings_bundle()
        if not enabled:
            # 说明当前读到的实际值，避免"我明明开了"的困惑（多为改完未重启）
            return {
                "status": "error",
                "message": (
                    "Rhino 桥接未启用（当前 RHINO_BRIDGE_ENABLED=false）。"
                    "请在设置页「CAD」分类打开开关；若已打开仍报此错，"
                    "说明运行中的服务仍是启动时的旧配置——重启 GrassSea 即可生效。"
                ),
                "code": "bridge_disabled",
                "detail": {"enabled": enabled, "url": url},
            }

        operation = str(params.get("operation") or "").strip()
        raw_params = params.get("params")
        bake = params.get("bake", True)
        confirm = bool(params.get("confirm", False))
        if not isinstance(bake, bool):
            return {"status": "error", "message": "bake 必须是布尔值", "code": "invalid_params"}

        client = RhinoClient(url, self._read_token(token_file), timeout_ms)
        unit = await self._document_unit(client)

        checked = validate(operation, raw_params, unit=unit)
        if not checked["ok"]:
            err = checked["error"]
            return {
                "status": "error",
                "message": f"{err['message']}（文档单位 {unit}）",
                "code": err["code"],
                "detail": err.get("detail"),
            }

        if bake and _needs_confirm(operation, checked["params"]) and not confirm:
            return {
                "status": "error",
                "message": (
                    f"{operation} 会修改 Rhino 文档，需要用户确认。"
                    "请先说明将要执行的几何变更并征得同意，再用 confirm=true 调用；"
                    "或使用 bake=false 先做预览（delete 无预览语义；"
                    "split 可改用 keep_input=true 保留原件）。"
                ),
                "code": "confirmation_required",
            }

        try:
            result = await client.call(operation, checked["params"], bake=bake)
        except RhinoBridgeError as exc:
            logger.warning(
                "Rhino 桥接调用失败",
                operation=operation,
                code=exc.code,
                message=exc.message,
            )
            return {
                "status": "error",
                "operation": operation,
                "message": exc.message,
                "code": exc.code,
                "detail": exc.detail,
            }

        object_ids = result.get("object_ids") or []
        return {
            "status": "completed",
            "operation": operation,
            "bake": bake,
            "object_ids": object_ids,
            "preview_info": result.get("preview_info"),
            "unit": unit,
            "message": (
                f"已在 Rhino 中完成 {operation}，生成 {len(object_ids)} 个对象。"
                if object_ids
                else f"{operation} 执行完成，无新增对象。"
            ),
        }
