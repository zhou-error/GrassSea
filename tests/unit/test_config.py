"""配置模块单元测试"""

from __future__ import annotations

import pytest

from shared.utils.config import Settings, get_settings


class TestSettings:
    """测试配置加载"""

    def test_default_settings(self) -> None:
        """测试默认配置值"""
        settings = Settings()
        assert settings.APP_NAME == "GrassSea"
        assert settings.APP_VERSION == "0.1.0"
        assert settings.APP_ENV == "development"

    def test_postgres_uri_property(self) -> None:
        """测试 PostgreSQL URI 拼接"""
        settings = Settings(
            POSTGRES_USER="testuser",
            POSTGRES_PASSWORD="testpass",
            POSTGRES_HOST="testhost",
            POSTGRES_PORT=5432,
            POSTGRES_DB="testdb",
        )
        uri = settings.POSTGRES_URI
        assert "testuser" in uri
        assert "testhost" in uri
        assert "testdb" in uri

    def test_mongodb_uri_property(self) -> None:
        """测试 MongoDB URI 拼接"""
        settings = Settings(
            MONGODB_USER="testuser",
            MONGODB_PASSWORD="testpass",
            MONGODB_HOST="testhost",
            MONGODB_PORT=27017,
            MONGODB_DB="testdb",
        )
        uri = settings.MONGODB_URI
        assert "testuser" in uri
        assert "testhost" in uri
        assert "testdb" in uri

    def test_redis_uri_no_password(self) -> None:
        """测试 Redis URI (无密码)"""
        settings = Settings(REDIS_HOST="localhost", REDIS_PORT=6379, REDIS_PASSWORD="")
        uri = settings.REDIS_URI
        assert "localhost:6379" in uri

    def test_get_settings_singleton(self) -> None:
        """测试配置单例"""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
