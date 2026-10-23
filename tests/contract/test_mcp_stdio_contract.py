"""MCP stdio 契约测试

不依赖任何 MCP SDK：直接按 JSON-RPC 逐行收发，验证
1) stdout 只承载协议（日志必须走 stderr）
2) tools/list 暴露 12 个 rhino_* 工具
3) 执行层复用 rhino_bridge，因此 bake=false 与 confirm 语义与主程序一致
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SERVER = PROJECT_ROOT / "rhino" / "mcp_server.py"

GUID = "1f2e3d4c-5b6a-4798-8c1d-2e3f4a5b6c7d"
ELLIPSE_8 = [
    [1000, 0, 0], [707, 707, 0], [0, 1000, 0], [-707, 707, 0],
    [-1000, 0, 0], [-707, -707, 0], [0, -1000, 0], [707, -707, 0],
]


def _run(requests: list[dict], mock_bridge) -> tuple[list[dict], str]:
    bridge, url, token = mock_bridge
    token_file = Path(tempfile.mkdtemp(prefix="mcp_tok_")) / "bridge.token"
    token_file.write_text(token, encoding="utf-8")

    env = dict(os.environ)
    env.update({
        "RHINO_BRIDGE_ENABLED": "true",
        "RHINO_BRIDGE_URL": url,
        "RHINO_BRIDGE_TOKEN_FILE": str(token_file),
        "RHINO_BRIDGE_TIMEOUT_MS": "5000",
        "DATA_DIR": tempfile.mkdtemp(prefix="mcp_data_"),
        "PYTHONIOENCODING": "utf-8",
    })
    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in requests) + "\n"
    proc = subprocess.run(
        [sys.executable, str(SERVER)],
        input=payload, capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=180,
    )
    lines = [l for l in proc.stdout.splitlines() if l.strip()]
    return [json.loads(l) for l in lines], proc.stderr


def _payload(result: dict) -> dict:
    return json.loads(result["result"]["content"][0]["text"])


def test_handshake_and_tool_list(mock_bridge):
    msgs, stderr = _run([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ], mock_bridge)

    by_id = {m.get("id"): m for m in msgs}
    assert by_id[1]["result"]["serverInfo"]["name"] == "grasssea-rhino"
    tools = by_id[2]["result"]["tools"]
    assert len(tools) == 12
    assert all(t["name"].startswith("rhino_") for t in tools)
    # stdout 只能有协议，日志必须走 stderr
    assert "[rhino-mcp]" not in "\n".join(json.dumps(m) for m in msgs)
    assert "[rhino-mcp]" in stderr


def test_preview_does_not_write(mock_bridge):
    msgs, _ = _run([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "rhino_loft_sections",
                    "arguments": {"sections": [ELLIPSE_8, ELLIPSE_8], "bake": False}}},
    ], mock_bridge)
    by_id = {m.get("id"): m for m in msgs}
    body = _payload(by_id[2])
    assert body["status"] == "completed"
    assert body["object_ids"] == []


def test_destructive_requires_confirm_via_mcp(mock_bridge):
    msgs, _ = _run([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "rhino_delete", "arguments": {"object_ids": [GUID]}}},
    ], mock_bridge)
    by_id = {m.get("id"): m for m in msgs}
    body = _payload(by_id[2])
    assert body["code"] == "confirmation_required"
    assert by_id[2]["result"]["isError"] is True
