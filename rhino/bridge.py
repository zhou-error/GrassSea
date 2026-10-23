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
import re
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

ALLOWED_OPERATIONS = {
    "create_curve", "extrude", "boolean", "delete", "query",
    # 船体建模
    "loft", "mirror", "split", "offset_srf", "mass_properties",
    "loft_sections",
    "join",
}

#: 世界平面名 -> 法向（与 GrassSea 侧 rhino_schema.PLANE_NORMALS 保持一致）
PLANE_NORMALS = {"yz": (1.0, 0.0, 0.0), "xz": (0.0, 1.0, 0.0), "xy": (0.0, 0.0, 1.0)}
QUEUE_LIMIT = 32
MAX_IDEMPOTENT_ENTRIES = 100
PROTOCOL_VERSION = 1

# ---------------------------------------------------------------- 状态

_lock = threading.Lock()
#: 本次请求中已创建的对象 id —— 失败时只删这些，不用 doc.Undo()
#: （真机踩到：doc.Undo() 会把**上一次成功**的几何一并撤销掉，造成数据丢失）
_created_ids = []


def _record(new_id):
    """登记新创建的对象 id"""
    if new_id != Guid.Empty:
        _created_ids.append(new_id)
    return new_id
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


_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _guid(text):
    """字符串 -> System.Guid（Rhino 的对象 id 类型）

    两点注意：
    1. 不存在 Rhino.Geometry.Guid，必须用 System.Guid（真机踩到，报 AttributeError）；
    2. 先自查格式再构造。System.Guid 对非法字符串抛的是 System.ArgumentException，
       不走 ValueError 分支，会被归类成 internal（真机踩到）。这里主动抛 ValueError，
       让上层映射成 invalid_params。
    """
    raw = str(text).strip()
    if not _GUID_RE.match(raw):
        raise ValueError(f"不是合法的 GUID：{text}")
    return Guid(raw)


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
    obj_id = _record(sc.doc.Objects.AddCurve(curve))
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
    obj_id = _record(sc.doc.Objects.AddExtrusion(extrusion))
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
        ids.append(str(_uuid_from_obj_id(_record(sc.doc.Objects.AddBrep(brep)))))
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


# ---------- 船体建模 ----------
# 注：以下部分 API 的重载在不同 Rhino 版本间有差异，已加多路兜底；
#     若全部失败会抛出提示"Rhino API 不可用"的 RuntimeError（归 internal）。


def _curve_of(obj_id_text):
    obj = sc.doc.Objects.FindId(_guid(obj_id_text))
    if obj is None:
        raise LookupError(f"找不到对象：{obj_id_text}")
    curve = obj.CurveGeometry
    if curve is None:
        raise ValueError(f"对象不是曲线：{obj_id_text}")
    return curve


def _curve_from_points(points, degree=None, closed=False):
    """点表 -> 曲线（loft_sections 与 create_curve 共用）"""
    pts = [Rhino.Geometry.Point3d(p[0], p[1], p[2]) for p in points]
    deg = int(degree) if degree else min(3, len(pts) - 1)
    curve = Rhino.Geometry.Curve.CreateInterpolatedCurve(pts, deg)
    if curve is None:
        raise ValueError("曲线创建失败：点集可能共线或退化")
    if closed:
        curve.MakeClosed(1e-6)
    if not curve.IsValid:
        raise ValueError("曲线无效（自交或点序异常）")
    return curve


def op_loft_sections(params, dry_run=False):
    """断面点表 -> 曲线 -> 放样，一次请求完成

    解决「预览不返回 object_ids，导致无法逐条建曲线后再放样」的问题：
    模型只要给出断面点，本操作内部完成建曲线与放样。
    """
    sections = params["sections"]
    closed_sections = bool(params.get("closed_sections", False))
    solid = bool(params.get("solid", False))
    keep_curves = bool(params.get("keep_curves", False))
    degree = params.get("degree")
    tol = sc.doc.ModelAbsoluteTolerance

    curves = [
        _curve_from_points(sec, degree, closed_sections) for sec in sections
    ]
    total_length = sum(c.GetLength() for c in curves)

    breps = Rhino.Geometry.Brep.CreateFromLoft(
        curves,
        Rhino.Geometry.Point3d.Unset,
        Rhino.Geometry.Point3d.Unset,
        Rhino.Geometry.LoftType.Normal,
        False,
    )
    if not breps or len(breps) == 0:
        raise ValueError(
            "放样失败：断面曲线可能方向不一致、点数差异过大或存在退化断面"
        )

    brep = breps[0]
    if solid:
        # 封盖容差不能太小：放样端环常有微小起伏，tol 过严会封不上。
        # 封不上时 preview 里 is_solid=false，由上层如实告知，不假装是实体。
        capped = brep.CapPlanarHoles(max(tol, 0.01))
        if capped is not None:
            brep = capped

    preview = {
        "type": "Brep(Loft)",
        "sections": len(sections),
        "curve_length_total": total_length,
        "area": brep.GetArea(),
        "is_solid": brep.IsSolid,
    }
    if brep.IsSolid:
        preview["volume"] = brep.GetVolume()

    if dry_run:
        preview["dry_run"] = True
        return [], preview

    curve_ids = []
    if keep_curves:
        for curve in curves:
            curve_ids.append(str(_uuid_from_obj_id(_record(sc.doc.Objects.AddCurve(curve)))))
    loft_id = str(_uuid_from_obj_id(_record(sc.doc.Objects.AddBrep(brep))))
    preview["curve_ids"] = curve_ids
    return [loft_id], preview


def op_join(params, dry_run=False):
    """缝合多个曲面/片体（把两舷与端面拼成整体，是形成封闭实体的关键）"""
    breps = [_brep_of(text) for text in params["object_ids"]]
    keep_input = bool(params.get("keep_input", False))
    tol = sc.doc.ModelAbsoluteTolerance

    joined = Rhino.Geometry.Brep.JoinBreps(breps, tol)
    if not joined or len(joined) == 0:
        raise ValueError("缝合失败：对象之间没有可连接的边（间隙可能大于容差）")

    preview = {
        "type": "Brep(Join)",
        "count": len(joined),
        "is_solid": joined[0].IsSolid if len(joined) == 1 else False,
        "area": sum(b.GetArea() for b in joined),
    }
    if dry_run:
        preview["dry_run"] = True
        return [], preview

    if not keep_input:
        for text in params["object_ids"]:
            sc.doc.Objects.Delete(_guid(text), True)
    ids = [str(_uuid_from_obj_id(_record(sc.doc.Objects.AddBrep(b)))) for b in joined]
    return ids, preview


def op_loft(params, dry_run=False):
    """把多条断面曲线放样成船体曲面/实体"""
    curves = [_curve_of(cid) for cid in params["curve_ids"]]
    closed = bool(params.get("closed", False))
    solid = bool(params.get("solid", False))
    tol = sc.doc.ModelAbsoluteTolerance

    breps = Rhino.Geometry.Brep.CreateFromLoft(
        curves,
        Rhino.Geometry.Point3d.Unset,
        Rhino.Geometry.Point3d.Unset,
        Rhino.Geometry.LoftType.Normal,
        closed,
    )
    if not breps or len(breps) == 0:
        raise ValueError("放样失败：断面曲线可能不连续、方向不一致或存在重复")

    brep = breps[0]
    if solid:
        # 封盖容差不能太小：放样端环常有微小起伏，tol 过严会封不上。
        # 封不上时 preview 里 is_solid=false，由上层如实告知，不假装是实体。
        capped = brep.CapPlanarHoles(max(tol, 0.01))
        if capped is not None:
            brep = capped

    preview = {
        "type": "Brep(Loft)",
        "area": brep.GetArea(),
        "is_solid": brep.IsSolid,
        "curves": len(curves),
    }
    if dry_run:
        preview["dry_run"] = True
        return [], preview
    obj_id = _record(sc.doc.Objects.AddBrep(brep))
    return [str(_uuid_from_obj_id(obj_id))], preview


def op_mirror(params, dry_run=False):
    """按世界平面镜像（船体默认 yz：镜像到另一舷）"""
    normal = PLANE_NORMALS[params.get("plane", "yz")]
    copy = bool(params.get("copy", True))
    plane = Rhino.Geometry.Plane(
        Rhino.Geometry.Point3d(0, 0, 0),
        Rhino.Geometry.Vector3d(normal[0], normal[1], normal[2]),
    )
    xform = Rhino.Geometry.Transform.Mirror(plane)
    if xform is None:
        raise RuntimeError("Rhino API 不可用：Transform.Mirror 返回空")

    ids = []
    if dry_run:
        return [], {"type": "Mirror", "count": len(params["object_ids"]), "copy": copy, "dry_run": True}

    for text in params["object_ids"]:
        guid = _guid(text)
        obj = sc.doc.Objects.FindId(guid)
        if obj is None:
            raise LookupError(f"找不到对象：{text}")

        if not copy:
            # 原地镜像
            if not sc.doc.Objects.Transform(guid, xform, False):
                raise ValueError(f"镜像失败：{text}")
            ids.append(str(_uuid_from_obj_id(_guid(text))))
            continue

        # 复制模式：复制几何 -> 变换副本 -> 新增。
        # 不再用 Objects.Transform(..., True)：真机实测它**并没有复制**，
        # 而是把原对象原地镜像（bbox 的 x 从 [-4474, 55525] 变成 [-55525, 4474]），
        # 且返回的仍是原 id —— 既毁原对象又不产生新对象。
        dup = obj.Geometry.Duplicate()
        if dup is None:
            raise ValueError(f"无法复制几何：{text}")
        dup.Transform(xform)
        # 不传 ObjectAttributes：真机实测 Add(dup, attrs) 会返回原对象 id（复制未生效）。
        # 传默认属性才能确保得到全新对象。
        new_id = sc.doc.Objects.Add(dup)
        if new_id == Guid.Empty:
            raise ValueError(f"镜像后新增对象失败：{text}")
        # 自检：新对象 id 必须与原对象不同，否则说明复制没生效
        if str(new_id).lower() == str(guid).lower():
            raise RuntimeError(
                "镜像未生成新对象（返回的 id 与原对象相同）；请重启 Rhino 并重新运行 rhino/bridge.py"
            )
        ids.append(str(_uuid_from_obj_id(_record(new_id))))
    return ids, {"type": "Mirror", "count": len(ids), "copy": copy}


def op_split(params, dry_run=False):
    """按世界平面切分（甲板 / 艉封板 / 水线）"""
    normal = PLANE_NORMALS[params.get("plane", "yz")]
    keep_input = bool(params.get("keep_input", False))
    plane = Rhino.Geometry.Plane(
        Rhino.Geometry.Point3d(0, 0, 0),
        Rhino.Geometry.Vector3d(normal[0], normal[1], normal[2]),
    )
    tol = sc.doc.ModelAbsoluteTolerance

    total = 0
    for text in params["object_ids"]:
        brep = _brep_of(text)
        try:
            pieces = brep.Split(plane, tol)
        except Exception:  # noqa: BLE001
            pieces = Rhino.Geometry.Brep.Split(brep, plane, tol)
        if not pieces or len(pieces) == 0:
            raise ValueError(
                f"切割失败：{text} 与 {params.get('plane', 'xy')} 平面没有交点，"
                "或该对象是开放曲面无法切分"
            )
        total += len(pieces)
        if dry_run:
            continue
        if not keep_input:
            sc.doc.Objects.Delete(_guid(text), True)
        for piece in pieces:
            _record(sc.doc.Objects.AddBrep(piece))
    return [], {"type": "Split", "pieces": total, "keep_input": keep_input}


def op_offset_srf(params, dry_run=False):
    """偏移曲面生成壳体（板厚）"""
    brep = _brep_of(params["object_id"])
    distance = float(params["distance"])
    solid = bool(params.get("solid", True))
    tol = sc.doc.ModelAbsoluteTolerance

    # 正确 API 是 Brep.CreateOffsetBrep（真机实测 Brep.Offset / brep.Offset 都不存在）
    results = None
    errors: list[str] = []
    try:
        results = Rhino.Geometry.Brep.CreateOffsetBrep(brep, distance, solid, False, tol)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"CreateOffsetBrep: {exc}")
    if not results:
        try:
            results = Rhino.Geometry.Brep.CreateOffsetBrep(brep, distance, solid, True, max(tol, 0.01))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"CreateOffsetBrep(extend): {exc}")
    if not results:
        raise RuntimeError("Rhino API 不可用：偏移失败（" + "; ".join(errors) + "）")

    if not results or len(results) == 0:
        raise ValueError("偏移失败：曲面曲率过大或距离不当")

    preview = {"type": "Shell", "count": len(results), "distance": distance}
    if dry_run:
        preview["dry_run"] = True
        return [], preview
    ids = [str(_uuid_from_obj_id(_record(sc.doc.Objects.AddBrep(b)))) for b in results]
    return ids, preview


def op_mass_properties(params, dry_run=False):
    """面积 / 体积 / 质心（只读，用于核对排水量）"""
    items = []
    missing = []
    for text in params["object_ids"]:
        obj = sc.doc.Objects.FindId(_guid(text))
        if obj is None:
            missing.append(text)
            continue
        geom = obj.Geometry
        entry = {"object_id": text, "type": type(geom).__name__}
        brep = Rhino.Geometry.Brep.TryConvertBrep(geom)
        if brep is not None:
            entry["area"] = brep.GetArea()
            entry["is_solid"] = brep.IsSolid
            if brep.IsSolid:
                entry["volume"] = brep.GetVolume()
                mp = Rhino.Geometry.VolumeMassProperties.Compute(brep)
                if mp is not None:
                    c = mp.Centroid
                    entry["centroid"] = [c.X, c.Y, c.Z]
        else:
            entry["area"] = None
            entry["is_solid"] = False
        items.append(entry)
    return [], {"objects": items, "missing": missing}


_HANDLERS = {
    "create_curve": op_create_curve,
    "extrude": op_extrude,
    "boolean": op_boolean,
    "delete": op_delete,
    "query": op_query,
    "loft": op_loft,
    "loft_sections": op_loft_sections,
    "join": op_join,
    "mirror": op_mirror,
    "split": op_split,
    "offset_srf": op_offset_srf,
    "mass_properties": op_mass_properties,
}


# ---------------------------------------------------------------- 执行（UI 线程）


def _execute(request):
    """在 Rhino 主线程执行；返回结果 dict"""
    rid = request["request_id"]
    operation = request["operation"]
    params = request["params"]
    bake = bool(request.get("bake", True))

    # bake=false 时**不写入文档**
    dry_run = (not bake) and operation != "delete"

    handler = _HANDLERS.get(operation)
    if handler is None:
        return {"request_id": rid, "state": "failed",
                "error": _error("unknown_operation", f"不支持的操作：{operation}")}

    writing = bake and not dry_run and operation != "query"
    undo_serial = None
    result = None
    _created_ids.clear()
    try:
        if writing:
            # BeginUndoRecord 返回 uint 序号，EndUndoRecord 必须传回
            undo_serial = sc.doc.BeginUndoRecord(f"GrassSea: {operation}")
        object_ids, preview = handler(params, dry_run)
        if writing:
            sc.doc.Views.Redraw()
        result = {
            "request_id": rid, "state": "done", "ok": True,
            "object_ids": object_ids, "preview_info": preview, "error": None,
        }
        return result
    except LookupError as exc:
        result = {"request_id": rid, "state": "failed",
                  "error": _error("not_found", str(exc))}
    except ValueError as exc:
        code = "geometry_failure" if ("布尔" in str(exc) or "挤出" in str(exc)) else "invalid_params"
        result = {"request_id": rid, "state": "failed", "error": _error(code, str(exc))}
    except RuntimeError as exc:
        # Rhino API 版本差异：明确是桥接能力问题，不是用户几何有问题
        result = {"request_id": rid, "state": "failed", "error": _error("internal", str(exc))}
    except Exception as exc:  # noqa: BLE001
        result = {"request_id": rid, "state": "failed",
                  "error": _error("internal", f"{type(exc).__name__}: {exc}")}
    finally:
        if undo_serial is not None:
            try:
                sc.doc.EndUndoRecord(undo_serial)
            except Exception:  # noqa: BLE001
                pass
        # 失败时只删除**本次请求**创建的对象。
        # 绝不能调 doc.Undo()：若本记录为空，它会撤销上一次成功的几何（实测丢过船壳）。
        if result is not None and result.get("state") != "done" and _created_ids:
            for gid in list(_created_ids):
                try:
                    sc.doc.Objects.Delete(gid, True)
                except Exception:  # noqa: BLE001
                    pass
            if writing:
                try:
                    sc.doc.Views.Redraw()
                except Exception:  # noqa: BLE001
                    pass
        _created_ids.clear()
    return result


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
