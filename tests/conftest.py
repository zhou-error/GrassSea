"""pytest 公共夹具

- 把项目根加入 sys.path（测试无需安装包）
- 提供 mock 桥接服务夹具
- 提供配置注入夹具（改环境变量后清 get_settings 缓存）
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_mock_bridge():
    """按路径加载 tests/fixtures/mock_bridge.py（不是包）"""
    path = PROJECT_ROOT / "tests" / "fixtures" / "mock_bridge.py"
    spec = importlib.util.spec_from_file_location("mock_bridge", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_bridge():
    """启动 mock 桥接，yield (bridge, url, token)"""
    module = _load_mock_bridge()
    bridge = module.MockBridge()
    url = bridge.start()
    try:
        yield bridge, url, module.TOKEN
    finally:
        bridge.stop()


@pytest.fixture
def apply_settings(monkeypatch, tmp_path):
    """注入配置：改环境变量并清缓存，返回一个 setter"""

    def _apply(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, str(value))
        from shared.utils.config import get_settings

        get_settings.cache_clear()
        return get_settings()

    yield _apply

    from shared.utils.config import get_settings

    get_settings.cache_clear()
