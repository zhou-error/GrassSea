#!/usr/bin/env python
r"""Rhino MCP server（stdio 传输，零新增依赖）

注意：本 docstring 必须是 raw 字符串：里面含 Windows 路径 C:\Users\...，
     普通字符串会把反斜杠+U 当成 unicode 转义并报 SyntaxError（已踩）。

把 Rhino 桥接的 12 个操作暴露成 MCP 工具，供支持 MCP 的客户端调用。
执行层**直接复用** tools/cad/rhino_bridge.py，因此参数校验、bake 语义、
破坏性操作确认、诚实失败等契约与主程序完全一致（已由 tests/contract 覆盖）。

启动（由客户端 spawn，或用命令行手动起）：
    uv run python rhino/mcp_server.py

配置（环境变量，与主程序同名）：
    RHINO_BRIDGE_ENABLED=true
    RHINO_BRIDGE_URL=http://127.0.0.1:8765
    RHINO_BRIDGE_TOKEN_FILE=C:\Users\<你>\GrassSea\bridge.token

⚠️ stdout 是协议通道：任何 print/日志写进 stdout 都会让客户端解析失败。
   因此启动第一件事就是把 sys.stdout 换成 stderr，协议只走保存下来的原始 stdout。
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---- 必须先做的重定向：stdout 只留给协议 ----
_PROTOCOL_OUT = sys.stdout
sys.stdout = sys.stderr  # 之后任何 print() 都进 stderr

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "grasssea-rhino", "version": "0.1.0"}


def _log(message: str) -> None:
    # 显式写 stderr，绝不能用 print（已被重定向到 stderr，但这里更明确）
    sys.stderr.write(f"[rhino-mcp] {message}\n")
    sys.stderr.flush()


# ---------------------------------------------------------------- 工具定义

def _points_schema() -> dict:
    return {"type": "array", "items": {"type": "array", "items": {"type": "number"},
                                       "minItems": 3, "maxItems": 3},
            "minItems": 2, "description": "[[x,y,z], ...]，至少 2 个互不相同的点"}


def _ids_schema() -> dict:
    return {"type": "array", "items": {"type": "string"}, "minItems": 1,
            "description": "对象 GUID 列表"}


TOOL_SPECS: dict[str, dict] = {
    "create_curve": {
        "description": "用插值点创建曲线。degree 省略时自动取可用上限；闭合曲线至少 3 个点。",
        "properties": {
            "points": _points_schema(),
            "degree": {"type": "integer", "minimum": 1, "maximum": 3},
            "closed": {"type": "boolean", "default": False},
        },
        "required": ["points"],
    },
    "extrude": {
        "description": "沿曲线所在平面的法向挤出成体；做布尔前请保持 cap=true。",
        "properties": {
            "curve_id": {"type": "string"},
            "height": {"type": "number"},
            "cap": {"type": "boolean", "default": True},
        },
        "required": ["curve_id", "height"],
    },
    "loft_sections": {
        "description": "船体放样首选：直接给断面点表，内部建曲线再放样，一次请求完成。",
        "properties": {
            "sections": {"type": "array", "items": _points_schema(), "minItems": 2},
            "closed_sections": {"type": "boolean", "default": False},
            "solid": {"type": "boolean", "default": False},
            "keep_curves": {"type": "boolean", "default": False},
            "degree": {"type": "integer", "minimum": 1, "maximum": 3},
        },
        "required": ["sections"],
    },
    "loft": {
        "description": "把文档中已有的多条断面曲线放样成曲面。",
        "properties": {
            "curve_ids": {"type": "array", "items": {"type": "string"}, "minItems": 2},
            "closed": {"type": "boolean", "default": False},
            "solid": {"type": "boolean", "default": False},
        },
        "required": ["curve_ids"],
    },
    "mirror": {
        "description": "按世界平面镜像。船体左右舷对称用 xz（y->-y）；yz 会把首尾翻转。",
        "properties": {
            "object_ids": _ids_schema(),
            "plane": {"type": "string", "enum": ["yz", "xz", "xy"], "default": "xz"},
            "copy": {"type": "boolean", "default": True},
        },
        "required": ["object_ids"],
    },
    "split": {
        "description": "按世界平面切分（甲板/艉封板/水线）。keep_input=false 会删除原对象，需要 confirm。",
        "properties": {
            "object_ids": _ids_schema(),
            "plane": {"type": "string", "enum": ["yz", "xz", "xy"], "default": "xy"},
            "keep_input": {"type": "boolean", "default": False},
        },
        "required": ["object_ids"],
    },
    "join": {
        "description": "缝合多个曲面/片体成整体，是形成封闭实体的关键一步。",
        "properties": {
            "object_ids": _ids_schema(),
            "keep_input": {"type": "boolean", "default": False},
        },
        "required": ["object_ids"],
    },
    "offset_srf": {
        "description": "偏移曲面生成壳体（板厚）；负值向内。",
        "properties": {
            "object_id": {"type": "string"},
            "distance": {"type": "number"},
            "solid": {"type": "boolean", "default": True},
        },
        "required": ["object_id", "distance"],
    },
    "boolean": {
        "description": "对两个实体做并/差/交。破坏性操作，bake=true 时需要 confirm。",
        "properties": {
            "brep_id_a": {"type": "string"},
            "brep_id_b": {"type": "string"},
            "operation": {"type": "string", "enum": ["union", "difference", "intersection"]},
            "tolerance": {"type": "number"},
        },
        "required": ["brep_id_a", "brep_id_b", "operation", "tolerance"],
    },
    "delete": {
        "description": "按 GUID 删除文档对象。破坏性操作，需要 confirm。",
        "properties": {"object_ids": _ids_schema()},
        "required": ["object_ids"],
    },
    "query": {
        "description": "查询对象的类型、包围盒与面数（只读）。",
        "properties": {"object_ids": _ids_schema()},
        "required": ["object_ids"],
    },
    "mass_properties": {
        "description": "读面积/体积/质心（只读）。体积只有闭合实体才有意义。",
        "properties": {"object_ids": _ids_schema()},
        "required": ["object_ids"],
    },
}


def _mcp_tools() -> list[dict]:
    tools = []
    for operation, spec in TOOL_SPECS.items():
        tools.append({
            "name": f"rhino_{operation}",
            "description": spec["description"],
            "inputSchema": {
                "type": "object",
                "properties": {
                    **spec["properties"],
                    "bake": {"type": "boolean", "default": True,
                             "description": "false=只算不写（预览）"},
                    "confirm": {"type": "boolean", "default": False,
                                "description": "破坏性操作写入前必须为 true"},
                },
                "required": spec["required"],
            },
        })
    return tools


# ---------------------------------------------------------------- 执行

async def _call_tool(name: str, arguments: dict) -> dict:
    operation = name[len("rhino_"):] if name.startswith("rhino_") else name
    if operation not in TOOL_SPECS:
        return {"content": [{"type": "text", "text": f"未知工具：{name}"}], "isError": True}

    bake = arguments.pop("bake", True)
    confirm = arguments.pop("confirm", False)

    from tools.cad.rhino_bridge import RhinoBridgeTool

    result = await RhinoBridgeTool().execute(
        {"operation": operation, "params": arguments, "bake": bake, "confirm": confirm},
        {},
    )
    text = json.dumps(result, ensure_ascii=False, default=str)
    return {
        "content": [{"type": "text", "text": text}],
        "isError": result.get("status") != "completed",
    }


# ---------------------------------------------------------------- JSON-RPC

def _send(message: dict) -> None:
    _PROTOCOL_OUT.write(json.dumps(message, ensure_ascii=False) + "\n")
    _PROTOCOL_OUT.flush()


def _error(msg_id: Any, code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}})


def _handle(request: dict) -> None:
    method = request.get("method")
    msg_id = request.get("id")
    params = request.get("params") or {}

    if method == "initialize":
        _send({"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }})
        return

    if method in ("notifications/initialized", "notifications/cancelled"):
        return  # 通知无需响应

    if method == "ping":
        _send({"jsonrpc": "2.0", "id": msg_id, "result": {}})
        return

    if method == "tools/list":
        _send({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": _mcp_tools()}})
        return

    if method == "tools/call":
        import asyncio

        name = params.get("name") or ""
        arguments = dict(params.get("arguments") or {})
        try:
            result = asyncio.run(_call_tool(name, arguments))
        except Exception as exc:  # noqa: BLE001
            _log(f"工具执行异常：{type(exc).__name__}: {exc}")
            result = {"content": [{"type": "text", "text": f"执行失败：{exc}"}], "isError": True}
        _send({"jsonrpc": "2.0", "id": msg_id, "result": result})
        return

    if msg_id is not None:
        _error(msg_id, -32601, f"Method not found: {method}")


def main() -> int:
    _log("Rhino MCP server 启动（stdio）")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError:
            _error(None, -32700, "Parse error")
            continue
        try:
            _handle(request)
        except Exception as exc:  # noqa: BLE001
            _log(f"处理请求失败：{exc}\n{traceback.format_exc()}")
            if isinstance(request, dict) and request.get("id") is not None:
                _error(request["id"], -32603, f"Internal error: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
