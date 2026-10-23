"""CAD 桥接端口契约测试

覆盖的是**真机上踩过的坑**，mock 桥接只能验证"上层契约"是否正确，
真机 API 语义仍需 tests/README 里的 10 项验收清单。
"""

from __future__ import annotations

import asyncio

import pytest

from tools.cad.rhino_schema import ALLOWED_OPERATIONS, validate

GUID_A = "1f2e3d4c-5b6a-4798-8c1d-2e3f4a5b6c7d"
GUID_B = "9a8b7c6d-5e4f-4321-8765-0fedcba98765"

ELLIPSE_8 = [
    [1000, 0, 0], [707, 707, 0], [0, 1000, 0], [-707, 707, 0],
    [-1000, 0, 0], [-707, -707, 0], [0, -1000, 0], [707, -707, 0],
]


def _tool_with_env(apply_settings, mock_bridge):
    """按**真实用法**配置：令牌写文件，配置指向该文件"""
    import tempfile
    from pathlib import Path

    bridge, url, token = mock_bridge
    token_file = Path(tempfile.mkdtemp(prefix="tok_")) / "bridge.token"
    token_file.write_text(token, encoding="utf-8")
    apply_settings(
        DATA_DIR=str(tempfile.mkdtemp(prefix="ct_")),
        RHINO_BRIDGE_ENABLED="true",
        RHINO_BRIDGE_URL=url,
        RHINO_BRIDGE_TOKEN_FILE=str(token_file),
        RHINO_BRIDGE_TIMEOUT_MS="5000",
    )
    from tools.cad.rhino_bridge import RhinoBridgeTool

    return RhinoBridgeTool(), bridge


def test_disabled_returns_bridge_disabled(apply_settings):
    apply_settings(RHINO_BRIDGE_ENABLED="false")
    from tools.cad.rhino_bridge import RhinoBridgeTool

    result = asyncio.run(
        RhinoBridgeTool().execute({"operation": "query", "params": {"object_ids": [GUID_A]}}, {})
    )
    assert result["status"] == "error"
    assert result["code"] == "bridge_disabled"


def test_destructive_requires_confirm(apply_settings, mock_bridge):
    tool, _ = _tool_with_env(apply_settings, mock_bridge)
    for payload in (
        {"operation": "delete", "params": {"object_ids": [GUID_A]}},
        {"operation": "boolean", "params": {"brep_id_a": GUID_A, "brep_id_b": GUID_B,
                                            "operation": "union", "tolerance": 1}},
        # split 在 keep_input=false 时等同删除
        {"operation": "split", "params": {"object_ids": [GUID_A], "plane": "xy"}},
    ):
        result = asyncio.run(tool.execute(payload, {}))
        assert result["code"] == "confirmation_required", payload["operation"]


def test_split_keep_input_is_not_destructive(apply_settings, mock_bridge):
    tool, _ = _tool_with_env(apply_settings, mock_bridge)
    result = asyncio.run(
        tool.execute(
            {"operation": "split", "params": {"object_ids": [GUID_A], "plane": "xy",
                                              "keep_input": True}},
            {},
        )
    )
    # 不是 confirmation_required 即说明未被拦截（mock 会正常处理）
    assert result.get("code") != "confirmation_required"


def test_invalid_params_not_reaching_bridge(apply_settings, mock_bridge):
    tool, bridge = _tool_with_env(apply_settings, mock_bridge)
    before = len(bridge.executed)
    result = asyncio.run(
        tool.execute({"operation": "create_curve", "params": {"points": [[0, 0, 0]]}}, {})
    )
    assert result["code"] == "invalid_params"
    # 校验失败不应产生任何桥接请求
    assert len(bridge.executed) == before


def test_degenerate_section_rejected(apply_settings, mock_bridge):
    """模型曾用 9 个相同点凑数，必须在校验层拒绝"""
    tool, bridge = _tool_with_env(apply_settings, mock_bridge)
    result = asyncio.run(
        tool.execute(
            {"operation": "create_curve",
             "params": {"points": [[0, 0, -600]] * 9, "closed": True}},
            {},
        )
    )
    assert result["code"] == "invalid_params"
    assert "退化" in result["message"]


def test_preview_sends_bake_false_and_returns_no_ids(apply_settings, mock_bridge):
    tool, _ = _tool_with_env(apply_settings, mock_bridge)
    result = asyncio.run(
        tool.execute(
            {"operation": "loft_sections",
             "params": {"sections": [ELLIPSE_8, ELLIPSE_8]},
             "bake": False},
            {},
        )
    )
    assert result["status"] == "completed"
    # 预览不返回 object_ids —— 这是设计约定，链式建模必须用批处理操作
    assert result["object_ids"] == []


def test_unknown_operation_rejected_locally(apply_settings, mock_bridge):
    tool, bridge = _tool_with_env(apply_settings, mock_bridge)
    before = len(bridge.executed)
    result = asyncio.run(tool.execute({"operation": "run_script", "params": {}}, {}))
    assert result["code"] == "unknown_operation"
    assert len(bridge.executed) == before


def test_unreachable_reports_bridge_unreachable(apply_settings):
    apply_settings(
        DATA_DIR=str(__import__("tempfile").mkdtemp(prefix="ct_")),
        RHINO_BRIDGE_ENABLED="true",
        RHINO_BRIDGE_URL="http://127.0.0.1:1",     # 一定不可达
        RHINO_BRIDGE_TOKEN_FILE="0" * 32,
        RHINO_BRIDGE_TIMEOUT_MS="1200",
    )
    from tools.cad.rhino_bridge import RhinoBridgeTool

    result = asyncio.run(
        RhinoBridgeTool().execute({"operation": "query", "params": {"object_ids": [GUID_A]}}, {})
    )
    assert result["code"] in ("bridge_unreachable", "timeout")
    assert result.get("object_ids") in (None, [])   # 绝不伪造 id


def test_operation_whitelist_is_twelve():
    assert len(ALLOWED_OPERATIONS) == 12
    assert "loft_sections" in ALLOWED_OPERATIONS
    assert "join" in ALLOWED_OPERATIONS


def test_mirror_defaults_to_xz_for_port_starboard():
    """船体左右舷对称是 xz（y->-y）；yz 会把首尾翻转"""
    result = validate("mirror", {"object_ids": [GUID_A]})
    assert result["ok"]
    assert result["params"]["plane"] == "xz"
