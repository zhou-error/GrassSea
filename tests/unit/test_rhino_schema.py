"""阶段 1：rhino_schema 校验层单测（纯函数，无外部依赖）"""

import pytest

from tools.cad.rhino_schema import ALLOWED_OPERATIONS, validate

VALID_GUID = "1f2e3d4c-5b6a-4798-8c1d-2e3f4a5b6c7d"
VALID_GUID_2 = "9a8b7c6d-5e4f-4321-8765-0fedcba98765"


def ok(op, params, unit="mm"):
    r = validate(op, params, unit=unit)
    assert r["ok"] is True, r
    return r["params"]


def bad(op, params, unit="mm", field=None):
    r = validate(op, params, unit=unit)
    assert r["ok"] is False, r
    assert r["error"]["code"] in ("invalid_params", "unknown_operation")
    if field:
        assert r["error"]["detail"]["field"] == field, r
    return r["error"]


# ---------------- 通用 ----------------

def test_unknown_operation():
    assert bad("run_script", {})["code"] == "unknown_operation"


def test_operation_whitelist():
    assert ALLOWED_OPERATIONS == {"create_curve", "extrude", "boolean", "delete", "query"}


def test_params_must_be_dict():
    bad("query", ["x"])


def test_non_serializable_rejected():
    bad("create_curve", {"points": [[0, 0, 0]], "closed": False, "cb": obj()})


def obj():
    return validate  # 任意函数对象，不可序列化


# ---------------- create_curve ----------------

def test_curve_minimal():
    p = ok("create_curve", {"points": [[0, 0, 0], [1, 0, 0]]}, unit="m")
    assert p["degree"] == 1  # 两点上限为 1
    assert p["closed"] is False


def test_curve_degree_default_capped():
    p = ok("create_curve", {"points": [[0, 0, 0], [1, 0, 0], [2, 1, 0]], "degree": 2}, unit="m")
    assert p["degree"] == 2


def test_curve_points_too_few():
    bad("create_curve", {"points": [[0, 0, 0]]}, field="points")


def test_curve_bad_arity():
    bad("create_curve", {"points": [[0, 0], [1, 1]]}, field="points[0]")


def test_curve_nan_rejected():
    bad("create_curve", {"points": [[0, 0, 0], [float("nan"), 0, 0]]}, field="points[1].x")


def test_curve_inf_rejected():
    bad("create_curve", {"points": [[0, 0, 0], [float("inf"), 0, 0]]}, field="points[1].x")


def test_curve_degree_exceeds_points():
    bad("create_curve", {"points": [[0, 0, 0], [1, 0, 0]], "degree": 3}, field="degree")


def test_curve_degree_not_int():
    bad("create_curve", {"points": [[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]], "degree": 2.5}, field="degree")


def test_curve_closed_needs_three():
    bad("create_curve", {"points": [[0, 0, 0], [1, 0, 0]], "closed": True}, field="points")


def test_curve_closed_ok():
    p = ok("create_curve", {"points": [[0, 0, 0], [1, 0, 0], [1, 1, 0]], "closed": True}, unit="m")
    assert p["closed"] is True


def test_curve_closed_not_bool():
    bad("create_curve", {"points": [[0, 0, 0], [1, 0, 0], [1, 1, 0]], "closed": "yes"}, field="closed")


# ---------------- extrude（含单位换算） ----------------

def test_extrude_mm_ok():
    ok("extrude", {"curve_id": VALID_GUID, "height": 5000}, unit="mm")  # 5 m


def test_extrude_ship_scale_400m_ok():
    """400 m 船体：毫米单位下 400000 必须通过（原规范 10000 会误拒）"""
    ok("extrude", {"curve_id": VALID_GUID, "height": 400000}, unit="mm")


def test_extrude_zero_rejected():
    bad("extrude", {"curve_id": VALID_GUID, "height": 0}, field="height")


def test_extrude_too_large_mm():
    bad("extrude", {"curve_id": VALID_GUID, "height": 2_000_000}, unit="mm", field="height")  # 2000 m


def test_extrude_negative_ok():
    """负高度是合法方向，只校验绝对值"""
    ok("extrude", {"curve_id": VALID_GUID, "height": -3000}, unit="mm")


def test_extrude_bad_guid():
    bad("extrude", {"curve_id": "abc", "height": 1}, field="curve_id")


def test_extrude_cap_default_true():
    p = ok("extrude", {"curve_id": VALID_GUID, "height": 100}, unit="mm")
    assert p["cap"] is True


# ---------------- boolean ----------------

def test_boolean_ok():
    p = ok("boolean", {"brep_id_a": VALID_GUID, "brep_id_b": VALID_GUID_2,
                       "operation": "union", "tolerance": 1}, unit="mm")
    assert p["operation"] == "union"


def test_boolean_same_id_rejected():
    bad("boolean", {"brep_id_a": VALID_GUID, "brep_id_b": VALID_GUID,
                    "operation": "union", "tolerance": 1}, field="brep_id_b")


def test_boolean_bad_operation():
    bad("boolean", {"brep_id_a": VALID_GUID, "brep_id_b": VALID_GUID_2,
                    "operation": "subtract", "tolerance": 1}, field="operation")


def test_boolean_missing_tolerance():
    bad("boolean", {"brep_id_a": VALID_GUID, "brep_id_b": VALID_GUID_2, "operation": "union"}, field="tolerance")


def test_boolean_zero_tolerance():
    bad("boolean", {"brep_id_a": VALID_GUID, "brep_id_b": VALID_GUID_2,
                    "operation": "union", "tolerance": 0}, field="tolerance")


# ---------------- delete / query ----------------

def test_delete_ok():
    p = ok("delete", {"object_ids": [VALID_GUID]})
    assert p["object_ids"] == [VALID_GUID.lower()]


def test_delete_empty_rejected():
    bad("delete", {"object_ids": []}, field="object_ids")


def test_delete_bad_id():
    bad("delete", {"object_ids": ["nope"]}, field="object_ids[0]")


def test_query_ok():
    ok("query", {"object_ids": [VALID_GUID, VALID_GUID_2]})


def test_query_too_many():
    bad("query", {"object_ids": [VALID_GUID] * 501}, field="object_ids")
