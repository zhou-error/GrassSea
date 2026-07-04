"""RAG 引擎单元测试"""

from __future__ import annotations

import pytest

from services.knowledge_service.ingestion import DocumentIngestionPipeline
from services.knowledge_service.retrieval import HybridRetriever, SearchResult
from services.knowledge_service.reranker import Reranker
from services.knowledge_service.generator import AnswerGenerator, RAG_SYSTEM_PROMPT
from shared.utils.config import Settings


class TestDocumentIngestion:
    """文档预处理测试"""

    @pytest.fixture
    def settings(self):
        return Settings()

    @pytest.fixture
    def pipeline(self, settings):
        return DocumentIngestionPipeline(settings)

    def test_clean_text(self, pipeline):
        """测试文本清洗"""
        text = "Hello\n\n\n\n\nWorld\n\n\n\n\nTest"
        cleaned = pipeline._clean_text(text)
        assert "Hello" in cleaned
        assert "World" in cleaned
        # 多余换行应被压缩（5个以上连续换行被替换为3个）
        assert cleaned.count("\n\n\n\n\n") == 0

    def test_chunk_text(self, pipeline):
        """测试文本分块"""
        text = "段落一。" * 200 + "\n\n" + "段落二。" * 300
        chunks = pipeline._chunk_text(
            text,
            chunk_size=512,
            chunk_overlap=64,
            document_id="test-doc",
            filename="test.txt",
            knowledge_base="测试库",
        )
        assert len(chunks) > 0
        # 每个 chunk 应有 metadata
        for chunk in chunks:
            assert chunk.metadata["document_id"] == "test-doc"
            assert chunk.metadata["knowledge_base"] == "测试库"
            assert chunk.text.strip()

    def test_chunk_text_empty(self, pipeline):
        """测试空文本分块"""
        chunks = pipeline._chunk_text(
            "", chunk_size=512, chunk_overlap=64,
            document_id="test", filename="test.txt", knowledge_base="test"
        )
        assert len(chunks) == 0

    def test_chunk_text_single_paragraph(self, pipeline):
        """测试单段落文本"""
        text = "这是一个简短的测试段落。"
        chunks = pipeline._chunk_text(
            text, chunk_size=512, chunk_overlap=64,
            document_id="test", filename="test.txt", knowledge_base="test"
        )
        assert len(chunks) == 1
        assert chunks[0].text.strip() == text


class TestReranker:
    """重排序测试"""

    @pytest.fixture
    def reranker(self):
        return Reranker()

    def test_score_based_rerank(self, reranker):
        """测试基于分数的重排序"""
        candidates = [
            SearchResult("1", "text1", 0.5, {}, 0),
            SearchResult("2", "text2", 0.9, {}, 1),
            SearchResult("3", "text3", 0.3, {}, 2),
            SearchResult("4", "text4", 0.7, {}, 3),
        ]
        result = reranker._score_based_rerank(candidates, top_k=2)
        assert len(result) == 2
        assert result[0].score == 0.9
        assert result[1].score == 0.7

    def test_rerank_with_few_candidates(self, reranker):
        """候选数少于 top_k 时"""
        candidates = [SearchResult("1", "text1", 0.5, {}, 0)]
        result = reranker._score_based_rerank(candidates, top_k=5)
        assert len(result) == 1


class TestHybridRetriever:
    """混合检索测试"""

    def test_tokenize(self):
        """测试分词"""
        settings = Settings()
        retriever = HybridRetriever(settings)
        tokens = retriever._tokenize("CCS 对散货船舱壁有什么要求？")
        assert len(tokens) > 0
        # 中文应被分词
        chinese_tokens = [t for t in tokens if any('一' <= c <= '鿿' for c in t)]
        assert len(chinese_tokens) > 0

    def test_tokenize_english(self):
        """测试英文分词"""
        settings = Settings()
        retriever = HybridRetriever(settings)
        tokens = retriever._tokenize("CCS bulk carrier bulkhead requirements")
        assert "ccs" in tokens
        assert "bulk" in tokens or "carrier" in tokens


class TestAnswerGenerator:
    """答案生成测试"""

    @pytest.fixture
    def settings(self):
        return Settings()

    @pytest.fixture
    def generator(self, settings):
        return AnswerGenerator(settings)

    def test_format_contexts(self, generator):
        """测试上下文格式化"""
        contexts = ["规范要求舱壁间距不小于 600mm"]
        sources = [
            SearchResult(
                "c1", "规范要求舱壁间距不小于 600mm", 0.9,
                source={"knowledge_base": "规范标准库", "filename": "CCS规范2024.pdf"},
                chunk_index=0,
            )
        ]
        formatted = generator._format_contexts(contexts, sources)
        assert "参考资料 1" in formatted
        assert "CCS规范2024.pdf" in formatted
        assert "规范标准库" in formatted
        assert "规范要求舱壁间距不小于 600mm" in formatted

    def test_fallback_answer(self, generator):
        """测试降级回答"""
        messages = [
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": "## 参考资料\n\ntest content\n"},
        ]
        answer = generator._fallback_answer(messages)
        assert "离线模式" in answer or "参考资料" in answer

    def test_format_contexts_without_sources(self, generator):
        """测试无来源信息时的格式化"""
        contexts = ["test content 1", "test content 2"]
        formatted = generator._format_contexts(contexts, [])
        assert "参考资料 1" in formatted
        assert "参考资料 2" in formatted
        assert "test content 1" in formatted


class TestPromptTemplate:
    """Prompt 模板测试"""

    def test_rag_system_prompt(self):
        """测试 RAG 系统 Prompt"""
        assert "船舶与海洋工程" in RAG_SYSTEM_PROMPT
        assert "引用来源" in RAG_SYSTEM_PROMPT
        assert "不得编造" in RAG_SYSTEM_PROMPT

    def test_rag_user_prompt_template(self):
        """测试 RAG User Prompt 模板"""
        from services.knowledge_service.generator import RAG_USER_PROMPT_TEMPLATE
        prompt = RAG_USER_PROMPT_TEMPLATE.format(
            query="测试问题",
            contexts="测试上下文",
        )
        assert "测试问题" in prompt
        assert "测试上下文" in prompt
