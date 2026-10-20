"""打印当前实现的规模数字（供文档与状态卡核对）

用法：
    uv run python scripts/status_counts.py

输出：Agent 数 / 工具数 / 模型可见工具数 / 配置项数 / Rhino 操作数

存在的理由：文档里的计数必须能一条命令复测，避免凭记忆写错
（曾把静水力公式行数写成 121，实际 59）。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


async def main() -> int:
    from services.agent_service.registry import AgentRegistry
    from services.agent_service.tool_loop import MODEL_EXPOSED_TOOLS
    from services.chat_service.config_api import CONFIG_SCHEMA
    from tools.bootstrap import build_tool_registry
    from tools.cad.rhino_schema import ALLOWED_OPERATIONS

    registry = await build_tool_registry()
    tools = await registry.list_tools()
    tool_ids = {t.tool_id for t in tools}
    unimplemented = sorted(tool_ids - MODEL_EXPOSED_TOOLS)

    agent_registry = AgentRegistry()
    await agent_registry.initialize()
    agents = await agent_registry.list_agents()

    categories = sorted({item["category"] for item in CONFIG_SCHEMA})

    print(f"agents      {len(agents)}")
    print(f"tools       {len(tools)}")
    print(f"exposed     {len(MODEL_EXPOSED_TOOLS)}")
    print(f"unimpl      {len(unimplemented)}  {', '.join(unimplemented) if unimplemented else ''}")
    print(f"config      {len(CONFIG_SCHEMA)}  ({len(categories)} 类: {', '.join(categories)})")
    print(f"rhino_ops   {len(ALLOWED_OPERATIONS)}")
    print(f"agent_ids   {', '.join(a['agent_id'] for a in agents)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
