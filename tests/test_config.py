import importlib
import sys

import pytest


def reload_config():
    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    return importlib.import_module("app.config")


def test_config_reads_env_paths(tmp_path, monkeypatch):
    data_db = tmp_path / "custom_data.db"
    logs_db = tmp_path / "custom_logs.db"
    vanna_dir = tmp_path / "custom_vanna"

    monkeypatch.setenv("DEEPSEEK_API_KEY", "key-123")
    monkeypatch.setenv("DATA_DB_PATH", str(data_db))
    monkeypatch.setenv("LOGS_DB_PATH", str(logs_db))
    monkeypatch.setenv("VANNA_DATA_DIR", str(vanna_dir))
    monkeypatch.setenv("DEEPSEEK_MODEL", "custom-model")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.com")

    config = reload_config()

    assert config.DATA_DB_PATH == data_db.resolve()
    assert config.LOGS_DB_PATH == logs_db.resolve()
    assert config.VANNA_DATA_DIR == vanna_dir.resolve()
    assert config.DEEPSEEK_API_KEY == "key-123"
    assert config.DEEPSEEK_MODEL == "custom-model"
    assert config.DEEPSEEK_BASE_URL == "https://example.com"


def test_config_missing_key_raises(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    with pytest.raises(RuntimeError):
        importlib.import_module("app.config")

