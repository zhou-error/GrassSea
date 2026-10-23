"""CAD 桥接端口

对应实现：tools/cad/rhino_client.py + rhino/bridge.py（Rhino 侧脚本）。
未来接 AutoCAD / SolidWorks 时，实现同一端口即可复用上层工具与测试。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class CADResult(dict):
    """桥接结果（本质是 dict，便于直接回灌给模型）

    约定字段：
      state        "done" | "failed" | "running"
      ok           bool
      object_ids   list[str] —— **空列表表示未写入文档**（预览或只读）
      preview_info dict | None —— 几何摘要；预览时含 dry_run=true
      error        {code, message, detail?} | None
      unit         str —— 文档单位（mm/cm/m…）
    """


@runtime_checkable
class CADBridgePort(Protocol):
    """CAD 桥接的契约

    实现方必须保证的**硬约束**（均有契约测试）：
    1. bake=False 时**绝不写入文档**，object_ids 必须为空；
    2. copy=True 的镜像必须**新增**对象、原对象不变，且返回的新 id 与输入不同；
    3. 写操作**不自动重试**（重试会造重复几何）；
    4. 失败时必须回滚**本次**创建的对象，不得影响此前已有的几何；
    5. 未知 operation 必须拒绝（白名单在实现侧硬编码，不依赖提示词）；
    6. 非法参数返回 invalid_params，几何运算失败返回 geometry_failure，
       两者不得混为一谈（前者让模型改参数，后者要用户改形状）；
    7. 不可达时返回 bridge_unreachable，不得伪造 object_ids。
    """

    async def hello(self) -> dict:
        """握手：protocol / version / units / doc_name"""
        ...

    async def call(self, operation: str, params: dict[str, Any], bake: bool = True) -> CADResult:
        """执行一次操作并等待结果"""
        ...

    async def submit(self, operation: str, params: dict[str, Any], bake: bool = True,
                     request_id: str | None = None) -> str:
        """提交操作，返回 request_id（同 id 幂等）"""
        ...

    async def wait(self, request_id: str, timeout_ms: int | None = None) -> CADResult:
        """轮询直到终态"""
        ...
