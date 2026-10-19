"""Rhino 桥接的参数校验（纯函数，零 IO）

设计要点：
- 所有几何数据必须是**纯序列化值**（数字/字符串/布尔/列表/字典），不接受函数或对象；
- 长度阈值**按文档单位换算到米**后判断，避免原规范 |height|<=10000 与 400 m 船体冲突；
- 校验失败返回结构化错误，带 expected 提示，便于把 detail 回灌给模型自我修正。

本模块不导入 Rhino，也不做任何网络/文件 IO，可完全离线单测。
"""

from __future__ import annotations

import math
import re
from typing import Any

#: 首期允许的操作（与 rhino/bridge.py 的白名单保持一致，两处都要改）
ALLOWED_OPERATIONS: frozenset[str] = frozenset({
    "loft_sections",   # 断面点表 -> 曲线 -> 放样（一次请求，避免逐条建曲线后无法接放样）
    # --- 通用 ---
    "create_curve",
    "extrude",
    "boolean",
    "delete",
    "query",
    # --- 船体建模 ---
    "loft",            # 断面曲线放样成船体曲面/实体
    "mirror",          # 镜像到另一舷
    "split",           # 按平面切分（甲板/艉封板/水线）
    "offset_srf",      # 偏移成壳（板厚）
    "mass_properties", # 面积/体积/质心（校验排水量）
})

#: 文档单位 -> 米 的换算系数
UNIT_TO_M: dict[str, float] = {
    "mm": 0.001,
    "cm": 0.01,
    "m": 1.0,
    "in": 0.0254,
    "ft": 0.3048,
}

#: 挤出高度的合理区间（米）：1 mm ~ 1000 m
MIN_EXTENT_M = 0.001
MAX_EXTENT_M = 1000.0
#: 布尔运算容差上限（米）：1 m 已远超任何合理几何容差
MAX_TOLERANCE_M = 1.0

MAX_POINTS = 10000
MAX_IDS = 500
MAX_DEGREE = 3

_GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

_SCALARS = (str, int, float, bool, type(None))


def _fail(field: str, message: str, expected: Any = None) -> dict:
    detail: dict = {"field": field}
    if expected is not None:
        detail["expected"] = expected
    return {
        "ok": False,
        "error": {
            "code": "invalid_params",
            "message": f"{field}: {message}",
            "detail": detail,
        },
    }


def _is_serializable(value: Any) -> bool:
    """只允许纯序列化值，递归检查"""
    if isinstance(value, _SCALARS):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_serializable(v) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_serializable(v) for k, v in value.items())
    return False


def _finite(value: Any, field: str) -> tuple[float | None, dict | None]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, _fail(field, "必须是数值", "number")
    num = float(value)
    if not math.isfinite(num):
        return None, _fail(field, "必须是有限数值（不接受 NaN / Infinity）", "finite number")
    return num, None


def _guid(value: Any, field: str) -> tuple[str | None, dict | None]:
    if not isinstance(value, str) or not _GUID_RE.match(value):
        return None, _fail(field, "必须是 GUID 字符串", "8-4-4-4-12 的 GUID，例如 1f2e3d4c-...")
    return value.lower(), None


def _bool(value: Any, field: str, default: bool) -> tuple[bool, dict | None]:
    if value is None:
        return default, None
    if not isinstance(value, bool):
        return default, _fail(field, "必须是布尔值", "true | false")
    return value, None


def _unit_factor(unit: str) -> float:
    return UNIT_TO_M.get((unit or "mm").lower(), UNIT_TO_M["mm"])


# ---------------------------------------------------------------- 各操作

def _validate_create_curve(params: dict, factor: float) -> dict:
    points = params.get("points")
    if not isinstance(points, list):
        return _fail("points", "必须是点数组", "[[x,y,z], ...]")
    if not 2 <= len(points) <= MAX_POINTS:
        return _fail("points", f"点数必须在 2..{MAX_POINTS} 之间", f"2..{MAX_POINTS}")

    clean: list[list[float]] = []
    for idx, point in enumerate(points):
        if not isinstance(point, (list, tuple)) or len(point) != 3:
            return _fail(f"points[{idx}]", "必须是 [x,y,z] 三元数组", "[x, y, z]")
        triple: list[float] = []
        for axis, value in zip(("x", "y", "z"), point):
            num, err = _finite(value, f"points[{idx}].{axis}")
            if err:
                return err
            triple.append(num)
        clean.append(triple)

    closed, err = _bool(params.get("closed"), "closed", False)
    if err:
        return err
    if closed and len(clean) < 3:
        return _fail("points", "闭合曲线至少需要 3 个点", ">= 3")

    # 退化检查：所有点重合时曲线长度为 0，放样会失败
    distinct = {tuple(p) for p in clean}
    need = 3 if closed else 2
    if len(distinct) < need:
        return _fail(
            "points",
            f"断面退化：只有 {len(distinct)} 个互不相同的点（至少需要 {need} 个）",
            f"至少 {need} 个不同坐标",
        )

    upper = min(MAX_DEGREE, len(clean) - 1)
    if "degree" not in params or params.get("degree") is None:
        # 未指定阶数时自动取可用上限（两点->1 阶，三点->2 阶，四点以上->3 阶），
        # 而不是拿默认的 3 阶去撞上限报错。
        degree = upper
    else:
        degree = params.get("degree")
        if isinstance(degree, bool) or not isinstance(degree, int):
            return _fail("degree", "必须是整数", f"1..{MAX_DEGREE}")
        if not 1 <= degree <= upper:
            return _fail(
                "degree",
                f"阶数必须在 1..{upper} 之间（点数 {len(clean)} 决定上限）",
                f"1..{upper}",
            )

    return {
        "ok": True,
        "params": {"points": clean, "degree": degree, "closed": closed},
    }


def _validate_extrude(params: dict, factor: float) -> dict:
    curve_id, err = _guid(params.get("curve_id"), "curve_id")
    if err:
        return err

    height, err = _finite(params.get("height"), "height")
    if err:
        return err
    height_m = abs(height) * factor
    if not MIN_EXTENT_M <= height_m <= MAX_EXTENT_M:
        return _fail(
            "height",
            f"挤出高度换算后为 {height_m:g} m，超出 {MIN_EXTENT_M:g}..{MAX_EXTENT_M:g} m",
            f"{MIN_EXTENT_M/factor:g}..{MAX_EXTENT_M/factor:g}（当前单位）",
        )

    cap, err = _bool(params.get("cap"), "cap", True)
    if err:
        return err

    return {"ok": True, "params": {"curve_id": curve_id, "height": height, "cap": cap}}


def _validate_boolean(params: dict, factor: float) -> dict:
    id_a, err = _guid(params.get("brep_id_a"), "brep_id_a")
    if err:
        return err
    id_b, err = _guid(params.get("brep_id_b"), "brep_id_b")
    if err:
        return err
    if id_a == id_b:
        return _fail("brep_id_b", "两个对象不能是同一个", "与 brep_id_a 不同的 GUID")

    operation = params.get("operation")
    if operation not in ("union", "difference", "intersection"):
        return _fail(
            "operation",
            "必须是 union / difference / intersection 之一",
            ["union", "difference", "intersection"],
        )

    tolerance = params.get("tolerance")
    tol, err = _finite(tolerance, "tolerance")
    if err:
        return err
    tol_m = abs(tol) * factor
    if not 0 < tol_m <= MAX_TOLERANCE_M:
        return _fail(
            "tolerance",
            f"容差换算后为 {tol_m:g} m，必须大于 0 且不超过 {MAX_TOLERANCE_M:g} m",
            f"0 < tolerance <= {MAX_TOLERANCE_M/factor:g}（当前单位）",
        )

    return {
        "ok": True,
        "params": {
            "brep_id_a": id_a,
            "brep_id_b": id_b,
            "operation": operation,
            "tolerance": tol,
        },
    }


def _validate_ids(params: dict, factor: float) -> dict:
    raw = params.get("object_ids")
    if not isinstance(raw, list) or not raw:
        return _fail("object_ids", "必须是非空数组", "[guid, ...]")
    if len(raw) > MAX_IDS:
        return _fail("object_ids", f"一次最多 {MAX_IDS} 个", f"<= {MAX_IDS}")

    ids: list[str] = []
    for idx, value in enumerate(raw):
        guid, err = _guid(value, f"object_ids[{idx}]")
        if err:
            return err
        ids.append(guid)
    return {"ok": True, "params": {"object_ids": ids}}


# ---------------------------------------------------------------- 船体建模

#: 世界平面名 -> 法向
PLANE_NORMALS = {"yz": (1.0, 0.0, 0.0), "xz": (0.0, 1.0, 0.0), "xy": (0.0, 0.0, 1.0)}

MAX_LOFT_CURVES = 200


def _plane(value: Any, field: str) -> tuple[str | None, dict | None]:
    if value not in PLANE_NORMALS:
        return None, _fail(field, "必须是 yz / xz / xy 之一", list(PLANE_NORMALS))
    return value, None


def _guid_list(raw: Any, field: str, minimum: int, maximum: int) -> tuple[list[str] | None, dict | None]:
    if not isinstance(raw, list):
        return None, _fail(field, "必须是数组", "[guid, ...]")
    if not minimum <= len(raw) <= maximum:
        return None, _fail(field, f"数量必须在 {minimum}..{maximum} 之间", f"{minimum}..{maximum}")
    ids: list[str] = []
    for idx, value in enumerate(raw):
        guid, err = _guid(value, f"{field}[{idx}]")
        if err:
            return None, err
        ids.append(guid)
    return ids, None


def _validate_loft(params: dict, factor: float) -> dict:
    ids, err = _guid_list(params.get("curve_ids"), "curve_ids", 2, MAX_LOFT_CURVES)
    if err:
        return err
    closed, err = _bool(params.get("closed"), "closed", False)
    if err:
        return err
    solid, err = _bool(params.get("solid"), "solid", False)
    if err:
        return err
    return {"ok": True, "params": {"curve_ids": ids, "closed": closed, "solid": solid}}


def _validate_mirror(params: dict, factor: float) -> dict:
    ids, err = _guid_list(params.get("object_ids"), "object_ids", 1, MAX_IDS)
    if err:
        return err
    plane, err = _plane(params.get("plane", "yz"), "plane")
    if err:
        return err
    copy, err = _bool(params.get("copy"), "copy", True)
    if err:
        return err
    return {"ok": True, "params": {"object_ids": ids, "plane": plane, "copy": copy}}


def _validate_split(params: dict, factor: float) -> dict:
    ids, err = _guid_list(params.get("object_ids"), "object_ids", 1, MAX_IDS)
    if err:
        return err
    plane, err = _plane(params.get("plane", "yz"), "plane")
    if err:
        return err
    keep_input, err = _bool(params.get("keep_input"), "keep_input", False)
    if err:
        return err
    return {"ok": True, "params": {"object_ids": ids, "plane": plane, "keep_input": keep_input}}


def _validate_offset_srf(params: dict, factor: float) -> dict:
    object_id, err = _guid(params.get("object_id"), "object_id")
    if err:
        return err
    distance, err = _finite(params.get("distance"), "distance")
    if err:
        return err
    dist_m = abs(distance) * factor
    if not MIN_EXTENT_M <= dist_m <= MAX_EXTENT_M:
        return _fail(
            "distance",
            f"偏移距离换算后为 {dist_m:g} m，超出 {MIN_EXTENT_M:g}..{MAX_EXTENT_M:g} m",
            f"{MIN_EXTENT_M/factor:g}..{MAX_EXTENT_M/factor:g}（当前单位）",
        )
    solid, err = _bool(params.get("solid"), "solid", True)
    if err:
        return err
    return {"ok": True, "params": {"object_id": object_id, "distance": distance, "solid": solid}}


def _validate_loft_sections(params: dict, factor: float) -> dict:
    """船体放样批处理：每层给出点位，内部建曲线再放样

    存在的理由：bake=false 的预览不返回 object_ids，因此「逐条建曲线 → 用 id 放样」
    这条链在预览后无法继续。这个操作把两步合并成一次原子请求。
    """
    raw = params.get("sections")
    if not isinstance(raw, list):
        return _fail("sections", "必须是断面数组", "[[[x,y,z],...], ...]")
    if not 2 <= len(raw) <= MAX_LOFT_CURVES:
        return _fail("sections", f"断面数必须在 2..{MAX_LOFT_CURVES} 之间", f"2..{MAX_LOFT_CURVES}")

    closed_sections, err = _bool(params.get("closed_sections"), "closed_sections", False)
    if err:
        return err

    clean_sections: list[list[list[float]]] = []
    for s_idx, section in enumerate(raw):
        if not isinstance(section, list):
            return _fail(f"sections[{s_idx}]", "必须是点数组", "[[x,y,z], ...]")
        if not 2 <= len(section) <= MAX_POINTS:
            return _fail(f"sections[{s_idx}]", "点数不合法", f"2..{MAX_POINTS}")
        pts: list[list[float]] = []
        for p_idx, point in enumerate(section):
            if not isinstance(point, (list, tuple)) or len(point) != 3:
                return _fail(f"sections[{s_idx}][{p_idx}]", "必须是 [x,y,z]", "[x, y, z]")
            triple: list[float] = []
            for axis, value in zip(("x", "y", "z"), point):
                num, e2 = _finite(value, f"sections[{s_idx}][{p_idx}].{axis}")
                if e2:
                    return e2
                triple.append(num)
            pts.append(triple)
        need = 3 if closed_sections else 2
        if len({tuple(p) for p in pts}) < need:
            return _fail(
                f"sections[{s_idx}]",
                f"断面退化：至少需要 {need} 个互不相同的点",
                f"至少 {need} 个不同坐标",
            )
        clean_sections.append(pts)

    solid, err = _bool(params.get("solid"), "solid", False)
    if err:
        return err
    keep_curves, err = _bool(params.get("keep_curves"), "keep_curves", False)
    if err:
        return err

    degree = params.get("degree")
    if degree is not None:
        if isinstance(degree, bool) or not isinstance(degree, int):
            return _fail("degree", "必须是整数", f"1..{MAX_DEGREE}")
        if not 1 <= degree <= MAX_DEGREE:
            return _fail("degree", f"阶数必须在 1..{MAX_DEGREE} 之间", f"1..{MAX_DEGREE}")

    return {
        "ok": True,
        "params": {
            "sections": clean_sections,
            "closed_sections": closed_sections,
            "solid": solid,
            "keep_curves": keep_curves,
            "degree": degree,
        },
    }


def _validate_mass_properties(params: dict, factor: float) -> dict:
    ids, err = _guid_list(params.get("object_ids"), "object_ids", 1, MAX_IDS)
    if err:
        return err
    return {"ok": True, "params": {"object_ids": ids}}


_VALIDATORS = {
    "create_curve": _validate_create_curve,
    "extrude": _validate_extrude,
    "boolean": _validate_boolean,
    "delete": _validate_ids,
    "query": _validate_ids,
    "loft": _validate_loft,
    "mirror": _validate_mirror,
    "split": _validate_split,
    "offset_srf": _validate_offset_srf,
    "mass_properties": _validate_mass_properties,
    "loft_sections": _validate_loft_sections,
}


def validate(operation: str, params: Any, *, unit: str = "mm") -> dict:
    """校验并规范化一次操作

    返回 {"ok": True, "params": {...}} 或 {"ok": False, "error": {code,message,detail}}。
    校验不通过时**不应**调用桥接层。
    """
    if operation not in ALLOWED_OPERATIONS:
        return {
            "ok": False,
            "error": {
                "code": "unknown_operation",
                "message": f"不支持的操作：{operation}",
                "detail": {"allowed": sorted(ALLOWED_OPERATIONS)},
            },
        }
    if not isinstance(params, dict):
        return _fail("params", "必须是对象", "{}")
    if not _is_serializable(params):
        return _fail("params", "只能包含数字/字符串/布尔/列表/字典", "纯序列化值")

    factor = _unit_factor(unit)
    return _VALIDATORS[operation](params, factor)
