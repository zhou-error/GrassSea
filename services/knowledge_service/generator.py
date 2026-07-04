"""答案生成模块

基于检索上下文构建 Prompt，调用 LLM 生成答案。
答案附带引用标注 `[来源: 文档名, §章节, P页码]`。
"""

from __future__ import annotations

from shared.utils.config import Settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)


# 知识库问答 Prompt 模板
RAG_SYSTEM_PROMPT = """你是一个船舶与海洋工程领域的专业 AI 助手（GrassSea AI）。

## 回答规则
1. **基于参考资料回答**：你的回答必须严格基于下方提供的参考资料，不得编造或臆测。
2. **引用来源**：每个论断都必须标注出处，格式为 `[来源: 文档名, chunk_{chunk_index}]`。
3. **信息不足时说明**：如果参考资料中找不到相关信息，明确说明"根据现有资料，无法回答此问题"。
4. **专业准确**：使用船舶专业术语，保持回答严谨、准确。
5. **结构清晰**：使用 Markdown 格式组织回答，复杂问题可按要点分列。
"""

RAG_USER_PROMPT_TEMPLATE = """## 用户问题
{query}

## 参考资料
{contexts}

请基于以上参考资料回答问题，并标注引用来源。"""


class AnswerGenerator:
    """RAG 答案生成器"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._http_client = None

    async def _get_client(self):
        """获取 HTTP 客户端"""
        if self._http_client is None:
            import httpx
            self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._http_client

    async def generate(
        self,
        query: str,
        contexts: list[str],
        sources: list | None = None,
    ) -> str:
        """生成答案

        Args:
            query: 用户原始问题
            contexts: 检索上下文字符串列表
            sources: 检索来源元数据列表 (SearchResult)

        Returns:
            生成的答案文本（含引用标注）
        """
        if not contexts:
            return "根据现有资料，无法回答此问题。请尝试上传相关文档或调整问题表述。"

        # 构建带引用的上下文
        formatted_contexts = self._format_contexts(contexts, sources or [])

        # 构建 Prompt
        user_prompt = RAG_USER_PROMPT_TEMPLATE.format(
            query=query,
            contexts=formatted_contexts,
        )

        messages = [
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 调用 LLM 生成
        answer = await self._call_llm(messages)

        return answer

    def _format_contexts(
        self,
        contexts: list[str],
        sources: list,
    ) -> str:
        """格式化上下文（含来源标注）"""
        formatted = []
        for i, (ctx, src) in enumerate(zip(contexts, sources)):
            kb = getattr(src, "source", {}).get("knowledge_base", "未知库")
            filename = getattr(src, "source", {}).get("filename", "未知文档")
            chunk_idx = getattr(src, "chunk_index", i)

            formatted.append(
                f"### 参考资料 {i + 1}\n"
                f"**来源**: {filename}（{kb}）\n"
                f"**位置**: chunk_{chunk_idx}\n"
                f"**内容**:\n{ctx}\n"
            )

        # 如果 sources 不足，补齐剩余 contexts
        if len(sources) < len(contexts):
            for i in range(len(sources), len(contexts)):
                formatted.append(
                    f"### 参考资料 {i + 1}\n"
                    f"**内容**:\n{contexts[i]}\n"
                )

        return "\n---\n".join(formatted)

    async def _call_llm(self, messages: list[dict]) -> str:
        """调用 LLM 生成答案

        使用模型网关或直接调用 DeepSeek API。
        """
        import httpx

        client = await self._get_client()

        # 优先使用 DeepSeek
        if self.settings.DEEPSEEK_API_KEY:
            try:
                response = await client.post(
                    f"{self.settings.DEEPSEEK_BASE_URL}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": messages,
                        "temperature": 0.3,  # 低温度，减少幻觉
                        "max_tokens": 2048,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error("LLM call failed, using fallback", error=str(e))

        # Fallback: 基于检索结果直接拼接回答
        return self._fallback_answer(messages)

    def _fallback_answer(self, messages: list[dict]) -> str:
        """降级回答（无 LLM 时使用）

        直接基于检索结果拼接参考信息。
        """
        # 从 user prompt 中提取 contexts
        user_content = messages[-1]["content"] if messages else ""

        return (
            "## 参考资料摘要（离线模式）\n\n"
            "当前未配置 LLM API Key，无法生成完整的回答。"
            "以下是检索到的相关参考资料：\n\n"
            f"{user_content.split('## 参考资料')[1] if '## 参考资料' in user_content else ''}\n\n"
            "---\n"
            "⚠️ **提示**: 请配置 `DEEPSEEK_API_KEY` 环境变量以启用完整的 RAG 生成功能。"
        )

    async def close(self) -> None:
        """清理资源"""
        if self._http_client:
            await self._http_client.aclose()
