"""配置枚举校验契约测试（审计 S3-2）

背景：coerce_setting 对 select 型只做类型转换、不校验枚举，
非法值（如 PDF_CONVERTER="__evil__"）会静默写进 .env 并进入运行时。
现在在 /config/update 入口拦截。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_invalid_select_value_rejected(apply_settings, tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    from services.chat_service import config_api

    monkeypatch.setattr(config_api, "ENV_FILE", env_file)
    apply_settings(DATA_DIR=str(tmp_path))

    from services.chat_service.main import app

    client = TestClient(app)
    resp = client.put("/config/update", json={"key": "PDF_CONVERTER", "value": "__evil__"})
    assert resp.status_code == 400
    assert "只支持" in resp.json()["detail"]
    # 非法值绝不能落盘
    assert "__evil__" not in env_file.read_text(encoding="utf-8")


def test_valid_select_value_accepted(apply_settings, tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    from services.chat_service import config_api

    monkeypatch.setattr(config_api, "ENV_FILE", env_file)
    apply_settings(DATA_DIR=str(tmp_path))

    from services.chat_service.main import app

    client = TestClient(app)
    resp = client.put("/config/update", json={"key": "PDF_CONVERTER", "value": "libreoffice"})
    assert resp.status_code == 200
    assert "libreoffice" in env_file.read_text(encoding="utf-8")
