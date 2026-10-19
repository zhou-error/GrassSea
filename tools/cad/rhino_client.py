"""Rhino 桥接的传输层（HTTP + token + 超时 + 幂等键）

设计要点（对应评审 P0）：
- **异步两段式**：submit 拿 request_id，再轮询 wait —— 避免同步等待造成 UI 线程死锁；
- **写操作绝不自动重试**：bake=true 的创建/布尔/删除重试会造出重复几何；
  只有只读的 query 允许失败后重试一次；
- **结构化错误**：所有失败都带 code，调用方据此决定是提示用户还是让模型修正参数。
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx

from shared.utils.logging import get_logger

logger = get_logger(__name__)

#: 与 rhino_schema.ALLOWED_OPERATIONS 保持一致
WRITE_OPERATIONS = frozenset({"create_curve", "extrude", "boolean", "delete"})
READ_OPERATIONS = frozenset({"query"})

#: 轮询间隔（秒）
POLL_INTERVAL = 0.2


class RhinoBridgeError(Exception):
    """桥接调用失败，带结构化 code"""

    def __init__(self, code: str, message: str, detail: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            **({"detail": self.detail} if self.detail else {}),
        }


class RhinoClient:
    """与 Rhino 侧桥接脚本通信"""

    def __init__(self, url: str, token: str = "", timeout_ms: int = 30000) -> None:
        self.base_url = (url or "").rstrip("/")
        self.token = token or ""
        self.timeout_ms = max(1000, int(timeout_ms))

    # ---------- 内部 ----------

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @staticmethod
    def _raise_for_payload(payload: dict) -> None:
        err = payload.get("error")
        if not err:
            return
        if isinstance(err, dict):
            raise RhinoBridgeError(
                str(err.get("code") or "internal"),
                str(err.get("message") or "桥接返回了错误"),
                err.get("detail"),
            )
        raise RhinoBridgeError("internal", str(err))

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_ms / 1000) as client:
                resp = await client.request(method, url, headers=self._headers(), **kwargs)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            raise RhinoBridgeError(
                "bridge_unreachable",
                "Rhino 桥接未连接：请确认 Rhino 已启动且桥接脚本正在运行。",
                {"url": self.base_url, "reason": type(exc).__name__},
            ) from exc
        except httpx.HTTPError as exc:
            raise RhinoBridgeError("internal", f"桥接通信失败：{exc}") from exc

        if resp.status_code == 401:
            raise RhinoBridgeError("unauthorized", "桥接令牌无效，请重启桥接脚本生成新令牌。")
        if resp.status_code == 429:
            raise RhinoBridgeError("busy", "桥接队列已满，请稍后重试。")

        try:
            payload = resp.json()
        except ValueError as exc:
            raise RhinoBridgeError("internal", f"桥接返回非法 JSON（HTTP {resp.status_code}）") from exc

        if resp.status_code >= 500:
            err = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(err, dict):
                self._raise_for_payload(payload)
            raise RhinoBridgeError("internal", f"桥接内部错误（HTTP {resp.status_code}）")

        return payload

    # ---------- 公开 ----------

    async def hello(self) -> dict:
        """握手：获取协议版本、Rhino 版本、文档单位与名称"""
        payload = await self._request("GET", "/hello")
        self._raise_for_payload(payload)
        return payload

    async def submit(
        self,
        operation: str,
        params: dict,
        bake: bool = True,
        request_id: str | None = None,
    ) -> str:
        """提交一次操作，返回 request_id（相同 id 重复提交不会重复执行）"""
        rid = request_id or str(uuid.uuid4())
        payload = await self._request(
            "POST",
            "/rpc",
            json={
                "protocol": 1,
                "request_id": rid,
                "operation": operation,
                "params": params,
                "bake": bool(bake),
                "timeout_ms": self.timeout_ms,
            },
        )
        self._raise_for_payload(payload)
        return str(payload.get("request_id") or rid)

    async def wait(self, request_id: str, timeout_ms: int | None = None) -> dict:
        """轮询直到终态；超时抛 timeout"""
        budget = (timeout_ms or self.timeout_ms) / 1000
        loop = asyncio.get_running_loop()
        deadline = loop.time() + budget

        while True:
            payload = await self._request("GET", f"/rpc/{request_id}")
            state = str(payload.get("state") or "")
            if state == "done":
                self._raise_for_payload(payload)
                return payload
            if state == "failed":
                self._raise_for_payload(payload)
                raise RhinoBridgeError("internal", "桥接报告失败但未提供原因")
            if loop.time() > deadline:
                raise RhinoBridgeError(
                    "timeout",
                    f"操作在 {budget:g} 秒内未完成（request_id={request_id}）。",
                    {"request_id": request_id},
                )
            await asyncio.sleep(POLL_INTERVAL)

    async def call(self, operation: str, params: dict, bake: bool = True) -> dict:
        """提交并等待结果

        写操作（create_curve / extrude / boolean / delete）**不重试**；
        只读操作（query）在传输层失败时重试一次。
        """
        attempts = 2 if operation in READ_OPERATIONS else 1
        last: RhinoBridgeError | None = None

        for attempt in range(attempts):
            try:
                rid = await self.submit(operation, params, bake=bake)
                result = await self.wait(rid)
                return result
            except RhinoBridgeError as exc:
                last = exc
                # 只有明确的"未连接/超时"且是只读操作，才允许再试一次
                if attempt + 1 >= attempts or exc.code not in ("bridge_unreachable", "timeout"):
                    raise
                logger.warning(
                    "只读操作重试一次",
                    operation=operation,
                    code=exc.code,
                    attempt=attempt + 1,
                )
        raise last or RhinoBridgeError("internal", "未知的桥接失败")
