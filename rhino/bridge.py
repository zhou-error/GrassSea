#! python 3
"""GrassSea Rhino 8 桥接脚本

在 Rhino 8 的 ScriptEditor（RhinoCode）里以 Python 3 运行。
启动后监听 127.0.0.1:8765，接收 GrassSea 发来的建模操作。

⚠️ 本脚本编写时**没有真机运行过**（开发机安装 Rhino 8 但未做端到端验证）。
   首次使用请按 rhino/README.md 的 10 项验收清单逐条核对。

协议要点：
- 两段式：POST /rpc 提交 -> GET /rpc/<id> 轮询，避免调用方阻塞 UI 线程；
- 所有文档操作通过 RhinoApp.InvokeOnUiThread 回到主线程执行；
- 每个请求包一层 undo 事务，失败主动 Undo，不留半成品；
- 相同 request_id 幂等，重复提交不重复执行；
- 白名单硬校验，未知操作直接拒绝。
"""

import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import Rhino
import scriptcontext as sc
from System import Action, Guid

# ---------------------------------------------------------------- 配置

PORT = int(os.environ.get("GRASSEA_BRIDGE_PORT", "8765"))

#: 令牌文件：与 GrassSea 的 RHINO_BRIDGE_TOKEN_FILE 指向同一个位置
_DATA_DIR = os.environ.get("GRASSEA_DATA_DIR", "")
if _DATA_DIR:
    TOKEN_FILE = Path(_DATA_DIR) / "bridge.token"
else:
    # 请改成你的 GrassSea data 目录，例如 r"F:\GrassSea\data"
    TOKEN_FILE = Path.home() / "GrassSea" / "bridge.token"

ALLOWED_OPERATIONS = {"create_curve", "extrude", "boolean", "delete", "query"}
QUEUE_LIMIT = 32
MAX_IDEMPOTENT_ENTRIES = 100
PROTOCOL_VERSION = 1

# ---------------------------------------------------------------- 状态

_lock = threading.Lock()
_results = {}          # request_id -> 结果 dict
_executed = []         # 已执行过的 request_id（幂等缓存，按序裁剪）
_pending = []          # 待执行请求
_busy = threading.Event()

# ---------------------------------------------------------------- 工具函数


def _register_token():
    """获取令牌：**已存在就复用**，只有首次才生成

    此前每次运行都重新生成并覆盖文件，导致「重启桥接」会把 GrassSea
    手里正在用的令牌作废，表现为莫名其妙的 unauthorized（已实测踩到）。
    如需换令牌，请先删除令牌文件再运行，或在 Rhino 里显式调用 rotate_token()。
    """
    try:
        if TOKEN_FILE.exists():
            existing = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if existing:
                print("[GrassSea] 复用已有令牌:", TOKEN_FILE)
                print("[GrassSea] 令牌（如需手动填写）:", existing)
                return existing
    except Exception as exc:  # noqa: BLE001
        print("[GrassSea] 读取已有令牌失败，将重新生成:", exc)

    token = uuid.uuid4().hex
    try:
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(token, encoding="utf-8")
        print("[GrassSea] 新令牌已写入:", TOKEN_FILE)
    except Exception as exc:  # noqa: BLE001
        print("[GrassSea] 令牌写入失败:", exc)
    print("[GrassSea] 令牌（如需手动填写）:", token)
    return token


def rotate_token():
    """显式轮换令牌（令牌泄露或需要重置时用）

    在 RhinoCode 控制台执行：  rotate_token()
    然后重启 GrassSea 侧（它会重新读取令牌文件）。
    """
    try:
        TOKEN_FILE.write_text(uuid.uuid4().hex, encoding="utf-8")
        print("[GrassSea] 令牌已轮换，请重启桥接与 GrassSea")
    except Exception as exc:  # noqa: BLE001
        print("[GrassSea] 轮换失败:", exc)


TOKEN = ""


def _units() -> str:
    try:
        return str(sc.doc.ModelUnitSystem).lower()
    except Exception:  # noqa: BLE001
        return "mm"


def _guid(text):
    """字符串 -> System.Guid（Rhino 的对象 id 类型）

    注意：不存在 Rhino.Geometry.Guid，必须用 System.Guid（真机踩到，报 AttributeError）。
    """
    return Guid(str(text))


def _uuid_from_obj_id(obj_id):
    return uuid.UUID(str(obj_id))


def _error(code, message, detail=None):
    err = {"code": code, "message": message}
    if detail:
        err["detail"] = detail
    return err


# ---------------------------------------------------------------- 各操作
# 每个函数返回 (object_ids, preview_info)；异常抛出 (code, message)


def op_create_curve(params, dry_run=False):
    points = [Rhino.Geometry.Point3d(p[0], p[1], p[2]) for p in params["points"]]
    degree = int(params.get("degree", min(3, len(points) - 1)))
    closed = bool(params.get("closed", False))

    curve = Rhino.Geometry.Curve.CreateInterpolatedCurve(points, degree)
    if curve is None:
        raise ValueError("曲线创建失败：点集可能共线或退化")

    if closed:
        curve.MakeClosed(1e-6)
    if not curve.IsValid:
        raise ValueError("曲线无效（自交或点序异常）")

    if dry_run:
        return [], {"type": "Curve", "length": curve.GetLength(), "dry_run": True}
    obj_id = sc.doc.Objects.AddCurve(curve)
    return [str(_uuid_from_obj_id(obj_id))], {"type": "Curve", "length": curve.GetLength()}


def op_extrude(params, dry_run=False):
    guid = _guid(params["curve_id"])
    obj = sc.doc.Objects.FindId(guid)
    if obj is None:
        raise LookupError(f"找不到对象：{params['curve_id']}")

    curve = obj.CurveGeometry
    if curve is None:
        raise ValueError("指定对象不是曲线，无法挤出")

    height = float(params["height"])
    cap = bool(params.get("cap", True))
    extrusion = Rhino.Geometry.Extrusion.Create(curve, height, cap)
    if extrusion is None:
        raise ValueError("挤出失败：高度或曲线不合法")

    brep = extrusion.ToBrep(False)
    preview = {
        "type": "Extrusion",
        "cap": cap,
        "volume": brep.GetVolume() if brep else None,
    }
    if dry_run:
        preview["dry_run"] = True
        return [], preview
    obj_id = sc.doc.Objects.AddExtrusion(extrusion)
    return [str(_uuid_from_obj_id(obj_id))], preview


def _brep_of(obj_id_text):
    obj = sc.doc.Objects.FindId(_guid(obj_id_text))
    if obj is None:
        raise LookupError(f"找不到对象：{obj_id_text}")
    brep = Rhino.Geometry.Brep.TryConvertBrep(obj.Geometry)
    if brep is None:
        raise ValueError(f"对象不是 Brep/实体：{obj_id_text}")
    return brep


def op_boolean(params, dry_run=False):
    a = _brep_of(params["brep_id_a"])
    b = _brep_of(params["brep_id_b"])
    tol = float(params["tolerance"])
    mode = params["operation"]

    if mode == "union":
        result = Rhino.Geometry.Brep.CreateBooleanUnion([a, b], tol)
    elif mode == "difference":
        result = Rhino.Geometry.Brep.CreateBooleanDifference(a, [b], tol)
    else:
        result = Rhino.Geometry.Brep.CreateBooleanIntersection(a, [b], tol)

    if not result or len(result) == 0:
        raise ValueError("布尔运算未产生结果：对象可能不相交、非闭合或容差不当")

    if dry_run:
        return [], {"type": "Brep", "count": len(result), "dry_run": True}
    ids = []
    for brep in result:
        ids.append(str(_uuid_from_obj_id(sc.doc.Objects.AddBrep(brep))))
    return ids, {"type": "Brep", "count": len(ids)}


def op_delete(params, dry_run=False):   # 删除无预览语义，忽略 dry_run
    deleted, missing = [], []
    for text in params["object_ids"]:
        guid = _guid(text)
        if sc.doc.Objects.FindId(guid) is None:
            missing.append(text)
            continue
        sc.doc.Objects.Delete(guid, True)
        deleted.append(text)
    if missing and not deleted:
        raise LookupError("对象均不存在", )
    return deleted, {"deleted": len(deleted), "missing": missing}


def op_query(params, dry_run=False):
    summary = []
    missing = []
    for text in params["object_ids"]:
        obj = sc.doc.Objects.FindId(_guid(text))
        if obj is None:
            missing.append(text)
            continue
        geom = obj.Geometry
        bbox = geom.GetBoundingBox(True)
        item = {
            "object_id": text,
            "type": type(geom).__name__,
            "bounding_box": {
                "min": [bbox.Min.X, bbox.Min.Y, bbox.Min.Z],
                "max": [bbox.Max.X, bbox.Max.Y, bbox.Max.Z],
            },
            "brep_face_count": None,
        }
        brep = Rhino.Geometry.Brep.TryConvertBrep(geom)
        if brep is not None:
            item["brep_face_count"] = brep.Faces.Count
        summary.append(item)
    return [], {"objects": summary, "missing": missing}


_HANDLERS = {
    "create_curve": op_create_curve,
    "extrude": op_extrude,
    "boolean": op_boolean,
    "delete": op_delete,
    "query": op_query,
}


# ---------------------------------------------------------------- 执行（UI 线程）


def _execute(request):
    """在 Rhino 主线程执行；返回结果 dict"""
    rid = request["request_id"]
    operation = request["operation"]
    params = request["params"]
    bake = bool(request.get("bake", True))

    # bake=false 时**不写入文档**（此前只影响 undo 分组，几何照样被 Add 进文档，属实现缺陷）
    dry_run = (not bake) and operation != "delete"

    handler = _HANDLERS.get(operation)
    if handler is None:
        return {"request_id": rid, "state": "failed",
                "error": _error("unknown_operation", f"不支持的操作：{operation}")}

    undo = None
    try:
        writing = bake and not dry_run and operation != "query"
        if writing:
            sc.doc.BeginUndoRecord(f"GrassSea: {operation}")
            undo = True
        object_ids, preview = handler(params, dry_run)
        if undo:
            sc.doc.EndUndoRecord()
        if writing:
            sc.doc.Views.Redraw()
        return {
            "request_id": rid, "state": "done", "ok": True,
            "object_ids": object_ids, "preview_info": preview, "error": None,
        }
    except LookupError as exc:
        if undo:
            try:
                sc.doc.Undo()
            except Exception:  # noqa: BLE001
                pass
        return {"request_id": rid, "state": "failed",
                "error": _error("not_found", str(exc))}
    except ValueError as exc:
        if undo:
            try:
                sc.doc.Undo()
            except Exception:  # noqa: BLE001
                pass
        code = "geometry_failure" if "布尔" in str(exc) or "挤出" in str(exc) else "invalid_params"
        return {"request_id": rid, "state": "failed", "error": _error(code, str(exc))}
    except Exception as exc:  # noqa: BLE001
        if undo:
            try:
                sc.doc.Undo()
            except Exception:  # noqa: BLE001
                pass
        # 未知异常属于桥接自身问题，不要伪装成几何失败
        return {"request_id": rid, "state": "failed",
                "error": _error("internal", f"{type(exc).__name__}: {exc}")}


def _drain_queue():
    """由 InvokeOnUiThread 反复调度，串行消费队列"""
    while True:
        with _lock:
            if not _pending:
                _busy.clear()
                return
            request = _pending.pop(0)
            _results[request["request_id"]] = {"request_id": request["request_id"],
                                               "state": "running"}
        result = _execute(request)
        with _lock:
            _results[request["request_id"]] = result


def _schedule():
    if _busy.is_set():
        return
    _busy.set()
    Rhino.RhinoApp.InvokeOnUiThread(Action(_drain_queue))


# ---------------------------------------------------------------- HTTP


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        # 只允许本机访问
        host = self.headers.get("Host", "")
        if not (host.startswith("127.0.0.1") or host.startswith("localhost")):
            return False
        return self.headers.get("Authorization", "") == f"Bearer {TOKEN}"

    def do_GET(self):
        if not self._authorized():
            return self._send(401, {"error": _error("unauthorized", "令牌无效")})
        if self.path == "/hello":
            return self._send(200, {
                "protocol": PROTOCOL_VERSION,
                "rhino_version": str(Rhino.RhinoApp.Version),
                "units": _units(),
                "doc_name": os.path.basename(sc.doc.Path) if sc.doc.Path else "(未保存)",
            })
        if self.path.startswith("/rpc/"):
            rid = self.path[len("/rpc/"):]
            with _lock:
                entry = _results.get(rid)
            if entry is None:
                return self._send(404, {"error": _error("not_found", "未找到该请求")})
            return self._send(200, entry)
        return self._send(404, {"error": _error("not_found", "无此路由")})

    def do_POST(self):
        if not self._authorized():
            return self._send(401, {"error": _error("unauthorized", "令牌无效")})
        if self.path != "/rpc":
            return self._send(404, {"error": _error("not_found", "无此路由")})

        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send(400, {"error": _error("invalid_params", "请求体不是合法 JSON")})

        operation = body.get("operation")
        if operation not in ALLOWED_OPERATIONS:
            return self._send(400, {"error": _error(
                "unknown_operation", f"不支持的操作：{operation}",
                {"allowed": sorted(ALLOWED_OPERATIONS)})})

        rid = body.get("request_id") or str(uuid.uuid4())
        with _lock:
            if rid in _executed:
                return self._send(202, {"request_id": rid, "state": "queued", "idempotent": True})
            if len(_pending) >= QUEUE_LIMIT:
                return self._send(429, {"error": _error("busy", "队列已满，请稍后重试")})
            _executed.append(rid)
            if len(_executed) > MAX_IDEMPOTENT_ENTRIES:
                del _executed[: len(_executed) - MAX_IDEMPOTENT_ENTRIES]
            _pending.append({
                "request_id": rid,
                "operation": operation,
                "params": body.get("params") or {},
                "bake": body.get("bake", True),
            })

        _schedule()
        return self._send(202, {"request_id": rid, "state": "queued"})


class _Server(ThreadingHTTPServer):
    """关闭端口复用

    ThreadingHTTPServer 默认 allow_reuse_address=True，而在 Windows 上
    SO_REUSEADDR 允许**绑定到已被监听的端口**——重复运行脚本会"看起来启动成功"，
    实际却是幽灵监听（实测踩到：后两次启动的令牌全部 401）。这里强制关闭。
    """

    allow_reuse_address = False
    daemon_threads = True


def start():
    global TOKEN
    TOKEN = _register_token()
    try:
        server = _Server(("127.0.0.1", PORT), Handler)
    except OSError as exc:
        print(f"[GrassSea] 无法监听 127.0.0.1:{PORT} —— {exc}")
        print("[GrassSea] 通常表示已有一个桥接在运行。")
        print("[GrassSea] 同一个 Rhino 里重复运行本脚本是无效的；")
        print("[GrassSea] 请重启 Rhino（或关闭 ScriptEditor 会话）后只运行一次。")
        return None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[GrassSea] Rhino 桥接已启动: http://127.0.0.1:{PORT}")
    print(f"[GrassSea] 文档单位: {_units()} | Rhino: {Rhino.RhinoApp.Version}")
    print("[GrassSea] 在 GrassSea 设置页把 RHINO_BRIDGE_ENABLED 打开即可调用。")
    return server


# 在 RhinoCode 里执行本文件即启动
_server = start()
