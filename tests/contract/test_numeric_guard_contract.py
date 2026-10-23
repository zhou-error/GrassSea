"""计算工具数值守卫契约测试（审计 S2-1 / S3-3）

背景：四个计算工具曾直接 float(params) 代入公式，NaN / Infinity / 负值 /
明显越界的方形系数都能算出"结果"并带 status=completed 交付给模型。
"""

from __future__ import annotations

import asyncio
import math

import pytest

from tools.bootstrap import build_tool_registry


@pytest.fixture(scope="module")
def registry():
    return asyncio.run(build_tool_registry())


def call(registry, tool_id, params):
    return asyncio.run(registry.execute_tool(tool_id, params, {}))


# ---------------- 非有限值与越界 ----------------

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_hydrostatics_rejects_non_finite(registry, bad):
    r = call(registry, "hydrostatics", {"L": bad})
    assert r["status"] == "error"
    assert "有限" in r["message"]


def test_hydrostatics_rejects_zero_length(registry):
    r = call(registry, "hydrostatics", {"L": 0})
    assert r["status"] == "error"
    assert "正数" in r["message"] or "不能小于" in r["message"]


def test_hydrostatics_rejects_out_of_range_cb(registry):
    r = call(registry, "hydrostatics", {"Cb": 1.5})
    assert r["status"] == "error"
    assert "Cb" in r["message"]


def test_hydrostatics_rejects_bool(registry):
    r = call(registry, "hydrostatics", {"L": True})
    assert r["status"] == "error"


def test_resistance_rejects_negative_speed(registry):
    r = call(registry, "resistance", {"V_kn": -5})
    assert r["status"] == "error"


def test_stability_allows_negative_gm(registry):
    """GM 为负是真实的"不稳"状态，不能被当成非法输入拒绝"""
    r = call(registry, "stability", {"GM": -0.2})
    assert r["status"] == "completed"
    assert r["results"]["GM_m"] == -0.2
    assert r["results"]["criteria_passed"] is False


def test_hull_transform_rejects_unknown_method(registry):
    """审计 S3-2 同类：枚举值必须校验"""
    r = call(registry, "hull_transform", {"method": "magic"})
    assert r["status"] == "error"
    assert "length_scale" in r["message"]


# ---------------- 默认值标注（S3-3） ----------------

def test_defaults_are_marked(registry):
    r = call(registry, "hydrostatics", {})
    assert r["status"] == "completed"
    assert set(r["used_defaults"]) >= {"L", "B", "T", "Cb", "water_density"}


def test_explicit_params_not_marked(registry):
    r = call(registry, "hydrostatics", {"L": 120, "B": 18, "T": 6, "Cb": 0.72})
    assert r["status"] == "completed"
    assert "L" not in r.get("used_defaults", [])
    assert "B" not in r.get("used_defaults", [])


def test_used_defaults_absent_when_all_given(registry):
    r = call(registry, "resistance",
             {"L": 120, "B": 18, "T": 6, "V_kn": 14, "Cb": 0.72, "water_density": 1025})
    assert r["status"] == "completed"
    assert "used_defaults" not in r


# ---------------- 物理合理性：船体量级仍可算 ----------------

def test_ship_scale_still_works(registry):
    """400 m 级船体必须能算（防止把守卫设得过窄）"""
    r = call(registry, "hydrostatics", {"L": 400, "B": 60, "T": 20, "Cb": 0.85})
    assert r["status"] == "completed"
    assert r["results"]["displacement_t"] > 0
    assert math.isfinite(r["results"]["displacement_t"])
