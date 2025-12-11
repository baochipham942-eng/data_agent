"""
PromptManager 服务测试
"""
import pytest
from pathlib import Path

from app.services.prompt_config import PromptConfig
from app.services.prompt_manager import PromptManager


@pytest.mark.service
class TestPromptManager:
    """PromptManager 服务测试"""
    
    def test_init(self, system_db_path):
        """测试初始化"""
        prompt_config = PromptConfig(db_path=system_db_path)
        manager = PromptManager(prompt_config)
        assert manager.prompt_config == prompt_config
    
    def test_get_active_prompt_with_fallback(self, system_db_path):
        """测试获取激活的 Prompt（带 fallback）"""
        prompt_config = PromptConfig(db_path=system_db_path)
        manager = PromptManager(prompt_config)
        
        fallback = "Default prompt content"
        content = manager.get_active_prompt_content("non_existent_prompt", fallback=fallback)
        assert content == fallback
    
    def test_cache_mechanism(self, system_db_path):
        """测试缓存机制"""
        prompt_config = PromptConfig(db_path=system_db_path)
        manager = PromptManager(prompt_config)
        
        # 第一次获取
        content1 = manager.get_active_prompt_content("system_prompt", fallback="default")
        
        # 第二次获取（应该使用缓存）
        assert "system_prompt" in manager._cache
        
        # 刷新缓存
        manager.refresh_cache("system_prompt")
        assert "system_prompt" not in manager._cache or len(manager._cache) == 0
    
    def test_format_prompt(self, system_db_path):
        """测试 Prompt 格式化"""
        prompt_config = PromptConfig(db_path=system_db_path)
        manager = PromptManager(prompt_config)
        
        # 创建一个带占位符的 prompt（使用不同的变量名避免与 prompt name 冲突）
        prompt_config.create_prompt(
            name="test_prompt",
            version="v1.0",
            content="Hello {user_name}, you are {user_role}",
            category="test",
        )
        
        # 激活 prompt
        prompt_config.set_active_prompt("test_prompt", "v1.0")
        
        # 刷新缓存
        manager.refresh_cache()
        
        # 格式化
        formatted = manager.format_prompt("test_prompt", user_name="Alice", user_role="admin")
        assert "Alice" in formatted
        assert "admin" in formatted
    
    def test_format_prompt_missing_args(self, system_db_path):
        """测试 Prompt 格式化（缺少参数）"""
        prompt_config = PromptConfig(db_path=system_db_path)
        manager = PromptManager(prompt_config)
        
        # 创建一个带占位符的 prompt
        prompt_config.create_prompt(
            name="test_prompt2",
            version="v1.0",
            content="Hello {name}",
            category="test",
        )
        
        # 激活 prompt
        prompt_config.set_active_prompt("test_prompt2", "v1.0")
        
        manager.refresh_cache()
        
        # 格式化时缺少参数
        formatted = manager.format_prompt("test_prompt2")  # 缺少 name 参数
        # 应该返回原始内容或处理错误
        assert isinstance(formatted, str)

