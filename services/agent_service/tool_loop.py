"""模型自主工具调用循环（OpenAI function calling）

职责
----
把 ToolRegistry 中**真实可用**的工具以 OpenAI function-calling 格式暴露给大模型，
由模型自行决定调用哪个工具、传什么参数；工具执行结果回灌给模型继续推理，
直到模型给出最终回答，或触达轮次 / 总超时上限。

与既有规则规划器的关系
----------------------
- 本模块是**新增的自主路径**：意图为 tool_call / professional_task 且开关开启时优先尝试。
- 既有 planner + executor 的规则 DAG 路径**完整保留**，作为：
  * 未配置可用模型时的回落；
  * 本循环调用失败 / 超时时的回落；
  * sub_agent_orchestration 意图的既有处理方式。

安全边界
--------
- 只暴露白名单内的已实现工具（见 MODEL_EXPOSED_TOOLS），未实现的工具默认不下发，
  避免模型把轮次浪费在必然返回 not_implemented 的调用上。
- 轮次与总超时均有上限；单次工具执行超时由 ToolRegistry 按 manifest.timeout_ms 控制。
- 工具返回 not_implemented 时，把真实原因原样回灌，模型据此如实告知用户，
  不允许编造结果（与项目「诚实失败」约定一致）。
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from shared.protocols.tool import BaseTool, ToolManifest, ToolStatus
from shared.utils.config import Settings
from services.agent_service.history import history
from shared.utils.logging import get_logger

logger = get_logger(__name__)


# 系统提示：约束模型的工具使用行为
TOOL_CALL_SYSTEM_PROMPT = """你是 GrassSea AI，专注于船舶与海洋工程领域。

你可以调用工具完成「读 → 算 → 查 → 写 → 交付」全流程。当前可用的能力类别：
- 专业计算：静水力、稳性、阻力与功率、型线变换、规范核查
- 工作文件夹：列目录、读文件（支持 PDF / Word .docx / Excel .xlsx / 文本）、写文本文件
- 文档交付：新建 Word（docx_create）、修改 Word（docx_edit）、转 PDF（docx_to_pdf）、
  把 Markdown 渲染成 Word 并可同时导出 PDF（report_gen）

请遵守以下规则：
1. 需要精确数值（稳性、静水力、阻力等）时，调用相应工具，不要凭记忆估算。
2. 用户要求「保存为 Word / 导出 PDF / 生成报告文件」时，**必须实际调用文档工具去写文件**，
   不要声称自己缺少写入或导出能力——只有工具真的返回错误时，才据实说明失败原因。
3. 工具返回 status="not_implemented" 表示该能力尚未实现：如实告知用户，绝不编造结果、文件路径或规范条款号。
4. 读取文件返回 truncated=true 时，说明内容被截断；应告知用户哪些部分没读到，不要假装读过全文。
5. 关键参数缺失时，使用工具的默认值并在回答中说明，或直接向用户询问。
6. 得到工具结果后，用中文简洁说明关键数值、单位与结论。
7. 不要重复调用同一个工具、同一组参数。
"""


# 暴露给模型的工具白名单（均已真实实现）
# 说明：reg_check 为内置启发式阈值校验，不涉及规范条文库，描述中已如实标注。
MODEL_EXPOSED_TOOLS: frozenset[str] = frozenset({
    "hydrostatics",
    "stability",
    "resistance",
    "hull_transform",
    "reg_check",
    # 工作文件夹（仅桌面模式且用户已选目录时才会真正执行）
    "workspace_list",
    "workspace_read",
    "workspace_write",
    # Word / PDF 文档
    "docx_create",
    "docx_edit",
    "docx_to_pdf",
    "report_gen",
})


def manifest_to_openai_tool(manifest: ToolManifest) -> dict:
    """把 ToolManifest 转换为 OpenAI function-calling 的 tool 定义

    ToolManifest.input_schema 本身就是 JSON Schema，与 parameters 字段同构，
    因此这里只做字段搬移，不做任何语义转换。
    """
    return {
        "type": "function",
        "function": {
            "name": manifest.tool_id,
            "description": manifest.description,
            "parameters": manifest.input_schema or {"type": "object", "properties": {}},
        },
    }


class ToolCallLoop:
    """模型自主工具调用循环"""

    def __init__(self, settings: Settings, tool_registry: Any) -> None:
        self.settings = settings
        self.tool_registry = tool_registry

    # ---------- 工具暴露 ----------

    async def list_exposed_tools(self) -> list[ToolManifest]:
        """列出可暴露给模型的工具（仅状态为 ONLINE 的）"""
        manifests = await self.tool_registry.list_tools()
        if self.settings.TOOL_CALL_EXPOSE_UNIMPLEMENTED:
            return list(manifests)
        return [m for m in manifests if m.tool_id in MODEL_EXPOSED_TOOLS]

    async def openai_tools(self) -> list[dict]:
        """构造下发给模型的 tools 参数"""
        return [manifest_to_openai_tool(m) for m in await self.list_exposed_tools()]

    # ---------- 主流程 ----------

    async def run(
        self,
        message: str,
        session_id: str,
        user_id: str | None = None,
    ) -> dict:
        """执行工具调用循环（自动带上该会话的历史）"""
        prior = history.get(session_id)
        result = await self._run_with_history(message, session_id, user_id, prior)
        # 只有真的拿到回答才记入历史，避免把失败也当成上下文
        if result.get("answer"):
            history.append(session_id, "user", message)
            history.append(session_id, "assistant", str(result["answer"]))
        return result

    async def _run_with_history(
        self,
        message: str,
        session_id: str,
        user_id: str | None,
        prior: list[dict],
    ) -> dict:
        """执行工具调用循环

        返回:
            {
              "ok": bool,             # 是否成功得到最终回答
              "answer": str | None,   # 最终回答（ok=False 时为 None）
              "tool_trace": list,     # 每次工具调用的记录，供前端展示
              "rounds": int,          # 实际使用的轮次
              "reason": str | None,   # ok=False 的原因
            }
        """
        if not self.settings.TOOL_CALLING_ENABLED:
            return {"ok": False, "answer": None, "tool_trace": [], "rounds": 0, "reason": "tool_calling_disabled"}

        tools = await self.openai_tools()
        if not tools:
            logger.warning("No exposable tools, skip tool-call loop")
            return {"ok": False, "answer": None, "tool_trace": [], "rounds": 0, "reason": "no_exposable_tools"}

        messages: list[dict] = [
            {"role": "system", "content": TOOL_CALL_SYSTEM_PROMPT},
            *prior,
            {"role": "user", "content": message},
        ]
        trace: list[dict] = []
        deadline = time.monotonic() + self.settings.TOOL_CALL_TIMEOUT_SECONDS
        rounds = 0

        async with httpx.AsyncClient(timeout=90.0) as client:
            for round_index in range(1, self.settings.TOOL_CALL_MAX_ROUNDS + 1):
                if time.monotonic() > deadline:
                    logger.warning("Tool-call loop exceeded total timeout", rounds=rounds)
                    break

                rounds = round_index
                try:
                    completion = await self._call_model(client, messages, tools)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Tool-call model invocation failed", error=str(exc), round=round_index)
                    return {"ok": False, "answer": None, "tool_trace": trace, "rounds": rounds,
                            "reason": f"model_error: {exc}"}

                tool_calls = completion.get("tool_calls") or []
                if not tool_calls:
                    # 模型给出最终回答，正常结束
                    return {
                        "ok": True,
                        "answer": completion.get("content") or "",
                        "tool_trace": trace,
                        "rounds": rounds,
                        "reason": None,
                    }

                # 记录 assistant 的工具调用意图，保证多轮上下文完整
                messages.append({
                    "role": "assistant",
                    "content": completion.get("content") or None,
                    "tool_calls": tool_calls,
                })

                for call in tool_calls:
                    await self._execute_one(call, messages, trace, round_index, session_id, user_id)

            # 轮次或超时用尽：再要一次不带工具的纯文本回答，避免用户拿到空白
            return await self._finalize(client, messages, trace, rounds)

    # ---------- 内部 ----------

    async def _call_model(
        self, client: httpx.AsyncClient, messages: list[dict], tools: list[dict] | None
    ) -> dict:
        """调用模型网关的 OpenAI 兼容接口"""
        payload: dict = {
            "model": self.settings.TOOL_CALL_MODEL,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        if tools:
            payload["tools"] = tools
        response = await client.post(
            f"{self.settings.MODEL_GATEWAY_URL}/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        return {
            "content": msg.get("content") or "",
            "tool_calls": msg.get("tool_calls") or [],
            "finish_reason": choice.get("finish_reason"),
        }

    async def _execute_one(
        self,
        call: dict,
        messages: list[dict],
        trace: list[dict],
        round_index: int,
        session_id: str,
        user_id: str | None,
    ) -> None:
        """执行一次工具调用，并把结果作为 tool 消息回灌"""
        function = call.get("function") or {}
        tool_id = function.get("name") or ""
        raw_args = function.get("arguments") or "{}"
        try:
            params = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            if not isinstance(params, dict):
                params = {}
        except (json.JSONDecodeError, TypeError):
            logger.warning("Model produced invalid tool arguments", tool_id=tool_id, raw=raw_args[:200])
            params = {}

        started = time.monotonic()
        result = await self.tool_registry.execute_tool(
            tool_id, params, {"session_id": session_id, "user_id": user_id}
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)

        status = result.get("status", "unknown")
        trace.append({
            "round": round_index,
            "tool": tool_id,
            "arguments": params,
            "status": status,
            "elapsed_ms": elapsed_ms,
            "message": result.get("message"),
        })
        logger.info("Tool invoked by model", tool=tool_id, status=status, elapsed_ms=elapsed_ms, round=round_index)

        messages.append({
            "role": "tool",
            "tool_call_id": call.get("id"),
            "name": tool_id,
            "content": self._stringify(result),
        })

    @staticmethod
    def _stringify(result: dict) -> str:
        """把工具结果序列化为回灌给模型的文本（截断超长内容）"""
        try:
            text = json.dumps(result, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(result)
        limit = 30000
        if len(text) <= limit:
            return text
        return text[:limit] + (
            f"\n…（工具结果已截断：完整内容 {len(text)} 字符，仅回灌前 {limit} 字符。"
            "如需剩余部分，请读取更小的范围。）"
        )

    async def _finalize(
        self,
        client: httpx.AsyncClient,
        messages: list[dict],
        trace: list[dict],
        rounds: int,
    ) -> dict:
        """轮次/超时用尽后的收尾：不带工具再要一次文本回答"""
        messages.append({
            "role": "user",
            "content": "请基于以上工具返回的结果给出最终回答；若工具未能提供数据，请如实说明原因。",
        })
        try:
            completion = await self._call_model(client, messages, None)
            answer = completion.get("content") or ""
            if answer:
                return {"ok": True, "answer": answer, "tool_trace": trace, "rounds": rounds, "reason": None}
        except Exception as exc:  # noqa: BLE001
            logger.error("Finalization call failed", error=str(exc))
        return {
            "ok": False,
            "answer": None,
            "tool_trace": trace,
            "rounds": rounds,
            "reason": "max_rounds_or_timeout",
        }
