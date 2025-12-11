"""
Prompt 管理器 - 统一管理所有 Prompt 的获取和使用
"""

import logging
from typing import Optional, Dict, Any
from app.services.prompt_config import PromptConfig

logger = logging.getLogger(__name__)


class PromptManager:
    """Prompt 管理器，统一从 PromptConfig 获取激活的 Prompt"""
    
    def __init__(self, prompt_config: PromptConfig):
        self.prompt_config = prompt_config
        self._cache: Dict[str, str] = {}  # 缓存激活的prompt内容
    
    def get_active_prompt_content(self, name: str, fallback: Optional[str] = None) -> str:
        """
        获取激活的 Prompt 内容
        
        Args:
            name: Prompt 名称（如 'system_prompt', 'rewrite_prompt' 等）
            fallback: 如果没有激活版本，使用的默认内容
        
        Returns:
            Prompt 内容字符串
        """
        # 先检查缓存
        if name in self._cache:
            return self._cache[name]
        
        # 从数据库获取激活版本
        active_prompt = self.prompt_config.get_active_prompt(name)
        
        if active_prompt and active_prompt.get("content"):
            content = active_prompt["content"]
            # 更新缓存
            self._cache[name] = content
            logger.info(f"使用激活的 {name} 版本: {active_prompt.get('version', 'unknown')}")
            return content
        
        # 如果没有激活版本，使用fallback
        if fallback:
            logger.warning(f"未找到激活的 {name}，使用默认内容")
            return fallback
        
        logger.error(f"未找到激活的 {name} 且没有fallback")
        return ""
    
    def refresh_cache(self, name: Optional[str] = None):
        """
        刷新缓存
        
        Args:
            name: 如果指定，只刷新该prompt的缓存；否则刷新所有
        """
        if name:
            if name in self._cache:
                del self._cache[name]
        else:
            self._cache.clear()
        logger.info(f"已刷新 Prompt 缓存: {name or 'all'}")
    
    def format_prompt(self, name: str, **kwargs) -> str:
        """
        获取并格式化 Prompt（支持变量替换）
        
        Args:
            name: Prompt 名称
            **kwargs: 格式化参数
        
        Returns:
            格式化后的 Prompt 内容
        """
        content = self.get_active_prompt_content(name)
        if not content:
            return ""
        
        try:
            return content.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Prompt {name} 格式化失败，缺少参数: {e}")
            return content









