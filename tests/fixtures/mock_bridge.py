"""mock Rhino 桥接服务（仅测试用）

用标准库 http.server 模拟协议与全部错误分支，不需要 Rhino。

场景通过 params["scenario"] 指定：
  ok / slow / busy / unknown / invalid / not_found / geometry_failure / internal
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

#: 与真实实现共用同一份白名单，避免 mock 与代码漂移
#: （曾出现：mock 只认 5 个旧操作，新增的 loft_sections 被判 unknown_operation）
try:  # pragma: no cover - 仅在项目内可用
    from tools.cad.rhino_schema import ALLOWED_OPERATIONS as ALLOWED  # type: ignore
except Exception:  # noqa: BLE001  # 独立运行时退化为字面量
    ALLOWED = {
        "create_curve", "extrude", "boolean", "delete", "query",
        "loft", "loft_sections", "mirror", "split", "offset_srf",
        "mass_properties", "join",
    }

TOKEN = "test-token"


class MockBridge:
    """在后台线程里跑一个最小桥接服务"""

    def __init__(self, port: int = 0, token: str = TOKEN) -> None:
        self.token = token
        self._results: dict[str, dict] = {}
        self._executed: list[str] = []      # 记录真正执行过的 request_id（验证幂等）
        self._server = ThreadingHTTPServer(("127.0.0.1", port), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    # ---------- 生命周期 ----------
    def start(self) -> str:
        self._thread.start()
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    @property
    def executed(self) -> list[str]:
        return list(self._executed)

    # ---------- 处理 ----------
    def _handler(self):
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):  # 静默
                pass

            def _send(self, code: int, payload: dict) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _authorized(self) -> bool:
                return self.headers.get("Authorization", "") == f"Bearer {bridge.token}"

            def do_GET(self):
                if not self._authorized():
                    return self._send(401, {"error": {"code": "unauthorized", "message": "bad token"}})
                if self.path == "/hello":
                    return self._send(200, {
                        "protocol": 1, "rhino_version": "8.0 (mock)",
                        "units": "mm", "doc_name": "mock.3dm",
                    })
                if self.path.startswith("/rpc/"):
                    rid = self.path[len("/rpc/"):]
                    entry = bridge._results.get(rid)
                    if entry is None:
                        return self._send(404, {"error": {"code": "not_found", "message": "unknown request"}})
                    return self._send(200, entry)
                return self._send(404, {"error": {"code": "not_found", "message": "no route"}})

            def do_POST(self):
                if not self._authorized():
                    return self._send(401, {"error": {"code": "unauthorized", "message": "bad token"}})
                if self.path != "/rpc":
                    return self._send(404, {"error": {"code": "not_found", "message": "no route"}})

                length = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    return self._send(400, {"error": {"code": "invalid_params", "message": "bad json"}})

                rid = body.get("request_id") or str(uuid.uuid4())
                op = body.get("operation")
                params = body.get("params") or {}
                scenario = str(params.get("scenario") or "ok")

                # 幂等：相同 request_id 直接返回缓存，不重复执行
                if rid in bridge._results:
                    return self._send(202, {"request_id": rid, "state": "queued", "idempotent": True})

                if op not in ALLOWED:
                    body_err = {"code": "unknown_operation", "message": f"unsupported: {op}"}
                    bridge._results[rid] = {"request_id": rid, "state": "failed", "error": body_err}
                    return self._send(400, {"request_id": rid, "state": "failed", "error": body_err})

                if scenario == "busy":
                    return self._send(429, {"error": {"code": "busy", "message": "queue full"}})
                if scenario == "invalid":
                    err = {"code": "invalid_params", "message": "degree: bad", "detail": {"field": "degree"}}
                    bridge._results[rid] = {"request_id": rid, "state": "failed", "error": err}
                    return self._send(400, {"request_id": rid, "state": "failed", "error": err})

                bridge._executed.append(rid)

                if scenario == "slow":
                    bridge._results[rid] = {"request_id": rid, "state": "running"}
                    threading.Timer(
                        2.0,
                        lambda: bridge._results.__setitem__(rid, {
                            "request_id": rid, "state": "done", "ok": True,
                            "object_ids": ["slow-id"], "preview_info": None, "error": None,
                        }),
                    ).start()
                    return self._send(202, {"request_id": rid, "state": "running"})

                if scenario == "geometry_failure":
                    bridge._results[rid] = {
                        "request_id": rid, "state": "failed", "ok": False, "object_ids": [],
                        "error": {"code": "geometry_failure", "message": "布尔运算失败：对象非闭合实体"},
                    }
                    return self._send(202, {"request_id": rid, "state": "queued"})

                if scenario == "internal":
                    return self._send(500, {"error": {"code": "internal", "message": "boom"}})

                if scenario == "not_found":
                    bridge._results[rid] = {
                        "request_id": rid, "state": "done", "ok": False, "object_ids": [],
                        "error": {"code": "not_found", "message": "object not found",
                                  "detail": {"missing": params.get("object_ids", [])}},
                    }
                    return self._send(202, {"request_id": rid, "state": "queued"})

                # 默认成功。必须与真实桥接一致：
                # bake=false（且不是 delete/query）是预览，**不写文档**，object_ids 为空。
                bake = bool(body.get("bake", True))
                dry_run = (not bake) and op not in ("delete", "query")
                if dry_run:
                    bridge._results[rid] = {
                        "request_id": rid, "state": "done", "ok": True,
                        "object_ids": [],
                        "preview_info": {"type": "Preview", "dry_run": True},
                        "error": None,
                    }
                else:
                    bridge._results[rid] = {
                        "request_id": rid, "state": "done", "ok": True,
                        "object_ids": [f"obj-{uuid.uuid4().hex[:8]}"],
                        "preview_info": None, "error": None,
                    }
                return self._send(202, {"request_id": rid, "state": "queued"})

        return Handler
