"""模型网关单元测试"""

from __future__ import annotations

import pytest

from services.model_gateway.router import ModelRouter, ModelRouteRequest, TASK_MODEL_MAP
from shared.utils.config import Settings


class TestModelRouter:
    """模型路由测试"""

    @pytest.fixture
    def settings(self):
        return Settings(
            DEEPSEEK_API_KEY="test-key",
            CLAUDE_API_KEY="test-key",
        )

    @pytest.fixture
    async def router(self, settings):
        r = ModelRouter(settings)
        await r.initialize()
        yield r
        await r.close()

    @pytest.mark.asyncio
    async def test_route_simple_chat(self, router):
        """测试简单对话路由"""
        request = ModelRouteRequest(
            model="deepseek-chat",
            task_type="simple_chat",
        )
        result = await router.route(request)
        assert result.model == "deepseek-chat"
        assert result.provider == "deepseek"

    @pytest.mark.asyncio
    async def test_route_complex_reasoning(self, router):
        """测试复杂推理路由"""
        request = ModelRouteRequest(
            model="deepseek-reasoner",
            task_type="complex_reasoning",
        )
        result = await router.route(request)
        assert result.model == "deepseek-reasoner"

    @pytest.mark.asyncio
    async def test_route_unknown_model_fallback(self, router):
        """测试未知模型降级"""
        request = ModelRouteRequest(
            model="unknown-model",
            task_type="simple_chat",
        )
        # 应该降级到 deepseek-chat
        result = await router.route(request)
        assert result.model == "deepseek-chat"

    def test_task_model_map_completeness(self):
        """测试任务-模型映射表完整性"""
        assert "simple_chat" in TASK_MODEL_MAP
        assert "knowledge_qa" in TASK_MODEL_MAP
        assert "complex_reasoning" in TASK_MODEL_MAP
        assert "code_generation" in TASK_MODEL_MAP
        assert "report_generation" in TASK_MODEL_MAP


class TestModelRouteRequest:
    """路由请求模型测试"""

    def test_default_values(self):
        request = ModelRouteRequest()
        assert request.model == "deepseek-chat"
        assert request.task_type == "simple_chat"
        assert request.temperature == 0.7
        assert request.max_tokens == 4096

    def test_custom_values(self):
        request = ModelRouteRequest(
            model="claude-sonnet",
            task_type="code_generation",
            temperature=0.1,
            max_tokens=8192,
        )
        assert request.model == "claude-sonnet"
        assert request.temperature == 0.1
