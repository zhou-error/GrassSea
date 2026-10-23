"""提示词契约测试

背景：系统提示词曾只写「计算与核查」，导致模型不知道自己能写文件、
能调 Rhino，于是回答「我没有导出能力 / 没有建模工具」。能力清单必须出现在提示词里。
"""

from __future__ import annotations

from services.agent_service.tool_loop import MODEL_EXPOSED_TOOLS, TOOL_CALL_SYSTEM_PROMPT


def test_prompt_lists_write_capability():
    assert "docx_create" in TOOL_CALL_SYSTEM_PROMPT
    assert "report_gen" in TOOL_CALL_SYSTEM_PROMPT
    assert "不要声称自己缺少写入" in TOOL_CALL_SYSTEM_PROMPT


def test_prompt_lists_cad_capability():
    assert "rhino_bridge" in TOOL_CALL_SYSTEM_PROMPT
    assert "不要声称自己不具备建模能力" in TOOL_CALL_SYSTEM_PROMPT


def test_prompt_forbids_guessing_when_context_missing():
    """用户只说「继续」且无上下文时，必须反问而不是挑话题"""
    assert "继续" in TOOL_CALL_SYSTEM_PROMPT
    assert "绝不允许凭空挑一个话题" in TOOL_CALL_SYSTEM_PROMPT


def test_prompt_requires_confirm_for_destructive():
    assert "confirm=true" in TOOL_CALL_SYSTEM_PROMPT


def test_exposed_tools_exclude_unimplemented():
    """未实现的工具不得下发，否则白白消耗模型轮次"""
    import asyncio

    from tools.bootstrap import build_tool_registry

    async def _tools():
        registry = await build_tool_registry()
        return await registry.list_tools()

    tools = asyncio.run(_tools())
    unimplemented = {t.tool_id for t in tools} - MODEL_EXPOSED_TOOLS
    assert len(unimplemented) == 8
    assert MODEL_EXPOSED_TOOLS.isdisjoint(unimplemented)


def test_rhino_prompt_sections_ordered():
    from agents.rhino_agent.prompts import SECTIONS, render

    orders = [order for order, _, _ in SECTIONS]
    assert orders == sorted(orders)
    text = render()
    # 原规范缺的三个参数必须在提示词里出现
    for token in ("degree", "cap", "tolerance"):
        assert token in text
    # 平面语义必须写对
    assert "xz" in text
