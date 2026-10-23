"""端口层（Ports）

把系统与外部世界的**边界**显式化：LLM、CAD 桥接、会话存储、工具、向量库。

为什么需要：本项目 70+ 轮迭代里修掉的 17 个 bug，按根因归类后
**没有一个是"架构层次不清"**，全部是**边界上的契约问题**（类型错、语义反、
静默失败、状态丢失）。端口层的价值不在"解耦"，而在于让这些契约
**可被测试断言**——换个 CAD 引擎或换模型供应商时，先跑契约测试。

原则：
1. 端口只描述**行为与返回值语义**，不含实现细节；
2. 实现方（local/milvus、Rhino/未来 CAD、DeepSeek/其他模型）各自适配；
3. 契约测试放在 tests/contract/，每个端口一份。
"""

from shared.ports.cad_bridge import CADBridgePort, CADResult
from shared.ports.llm import Completion, LLMPort, ToolCall
from shared.ports.storage import ConversationStorePort, HistoryMessage

__all__ = [
    "CADBridgePort",
    "CADResult",
    "Completion",
    "ConversationStorePort",
    "HistoryMessage",
    "LLMPort",
    "ToolCall",
]
