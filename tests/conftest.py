"""
测试配置和共享 fixtures
"""
import sys
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Generator

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="function", autouse=True)
def setup_test_env(monkeypatch):
    """设置测试环境变量"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-api-key-for-testing")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    yield
    # 清理（如果需要）


@pytest.fixture
def temp_dir(tmp_path) -> Path:
    """创建临时目录"""
    return tmp_path


@pytest.fixture
def temp_db_path(tmp_path) -> Path:
    """创建临时数据库文件路径"""
    return tmp_path / "test.db"


@pytest.fixture
def system_db_path(tmp_path) -> Path:
    """创建临时系统数据库路径"""
    db_path = tmp_path / "system.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


@pytest.fixture
def data_db_path(tmp_path) -> Path:
    """创建测试数据数据库路径"""
    db_path = tmp_path / "data.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 创建一个简单的测试表
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_table (
            id INTEGER PRIMARY KEY,
            name TEXT,
            value INTEGER,
            created_at TEXT
        )
    """)
    cursor.execute("INSERT INTO test_table (name, value, created_at) VALUES (?, ?, ?)", 
                   ("test1", 100, "2024-01-01"))
    cursor.execute("INSERT INTO test_table (name, value, created_at) VALUES (?, ?, ?)", 
                   ("test2", 200, "2024-01-02"))
    conn.commit()
    conn.close()
    
    return db_path


@pytest.fixture
def mock_llm_service():
    """模拟 LLM 服务"""
    class MockLLMService:
        def __init__(self):
            self.calls = []
        
        async def generate(self, prompt: str, **kwargs):
            """模拟 LLM 生成"""
            self.calls.append({"prompt": prompt, "kwargs": kwargs})
            # 返回一个简单的模拟响应
            return "Mock LLM Response"
        
        def generate_sync(self, prompt: str, **kwargs):
            """同步版本的生成"""
            self.calls.append({"prompt": prompt, "kwargs": kwargs})
            return "Mock LLM Response"
    
    return MockLLMService()


@pytest.fixture
def clean_modules():
    """清理已导入的模块，用于测试配置重载"""
    import importlib
    
    modules_to_clean = [
        "app.config",
        "app.services.prompt_config",
        "app.services.prompt_manager",
    ]
    
    for module_name in modules_to_clean:
        if module_name in sys.modules:
            del sys.modules[module_name]
    
    yield
    
    # 测试后清理（如果需要）

