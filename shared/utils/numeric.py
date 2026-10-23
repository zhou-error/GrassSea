"""数值参数守卫

背景（审计 S2-1）：计算工具直接把 params 值 float() 后代入公式，
于是 NaN / Infinity / 负值 / 1e12 这类明显不合物理的输入也会算出"结果"，
并带着 status=completed 交给模型，最终可能写进报告。
这不是"伪造"，但把无意义输入当有效输入同样是失真。

本模块提供统一的取值与校验：
- 只接受有限数值（拒绝 NaN / Infinity / 字符串 / 布尔）
- 按物理合理区间校验（船长 1~1000 m、方形系数 0.05~0.95 等）
- 记录哪些参数用了默认值，供工具在输出里标注（审计 S3-3）
"""

from __future__ import annotations

import math
from typing import Iterable


class ParamError(ValueError):
    """参数不合法（信息可直接展示给用户/模型）"""


def get_number(
    params: dict,
    names: Iterable[str],
    default: float,
    *,
    label: str,
    minimum: float | None = None,
    maximum: float | None = None,
    allow_zero: bool = False,
) -> tuple[float, bool]:
    """取一个数值参数并做健全性校验

    返回 (值, 是否使用了默认值)。
    校验不通过时抛 ParamError，附带可操作的中文说明。
    """
    raw = None
    used_alias = None
    for name in names:
        if name in params and params[name] is not None:
            raw = params[name]
            used_alias = name
            break

    used_default = raw is None
    if used_default:
        value = float(default)
    else:
        if isinstance(raw, bool):
            raise ParamError(f"{label} 必须是数值，不能是布尔值")
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ParamError(f"{label} 必须是数值，收到 {raw!r}") from exc
        if not math.isfinite(value):
            raise ParamError(f"{label} 必须是有限数值，不接受 NaN / Infinity")

    if allow_zero:
        if minimum is not None and value < minimum:
            raise ParamError(f"{label} 不能小于 {minimum:g}，收到 {value:g}")
    elif minimum is not None and value <= 0:
        raise ParamError(f"{label} 必须为正数，收到 {value:g}")

    if minimum is not None and not allow_zero and value < minimum:
        raise ParamError(f"{label} 不能小于 {minimum:g}，收到 {value:g}")
    if maximum is not None and value > maximum:
        raise ParamError(f"{label} 不能大于 {maximum:g}，收到 {value:g}")

    # 便于排障：别名命中时把实际字段名留在值上（不影响数值）
    del used_alias
    return value, used_default


#: 常用物理区间（单位见各工具注释）
LIMITS = {
    "length_m": (1.0, 1000.0),      # 船长：1 m ~ 1000 m
    "beam_m": (0.5, 100.0),         # 型宽
    "depth_m": (0.5, 100.0),        # 型深
    "draft_m": (0.1, 50.0),         # 吃水
    "speed_kn": (0.1, 60.0),        # 航速
    "cb": (0.05, 0.95),             # 方形系数
    "rho": (900.0, 1100.0),         # 水密度 kg/m³
}


def get_phys(params: dict, names: Iterable[str], default: float, *, label: str, key: str):
    """按 LIMITS 里的物理区间取参数（key 见 LIMITS）"""
    lo, hi = LIMITS[key]
    return get_number(params, names, default, label=label, minimum=lo, maximum=hi)


def used_defaults_note(fields: list[str]) -> dict:
    """生成"使用了默认值"的标注（审计 S3-3）"""
    if not fields:
        return {}
    return {"used_defaults": fields}
