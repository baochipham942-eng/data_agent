"""
Agent 包装器 - 支持动态配置和用户级别的个性化
"""
import logging
from typing import Optional, Dict, Any
from vanna import Agent, AgentConfig
from vanna.core.user import User

from app.services.dynamic_prompt_builder import DynamicPromptBuilder
from app.services.prompt_manager import PromptManager
from app.services.agent_memory import UserProfileService

logger = logging.getLogger(__name__)


class EnhancedAgentWrapper:
    """
    增强的 Agent 包装器，支持：
    - 动态 System Prompt（根据用户画像）
    - 用户级别的配置覆盖
    - 工具权限控制
    """
    
    def __init__(
        self,
        base_agent: Agent,
        dynamic_prompt_builder: DynamicPromptBuilder,
        user_profile_service: Optional[UserProfileService] = None,
    ):
        """
        初始化 Agent 包装器。
        
        Args:
            base_agent: 基础 Agent 实例
            dynamic_prompt_builder: 动态 Prompt 构建器
            user_profile_service: 用户画像服务
        """
        self.base_agent = base_agent
        self.dynamic_prompt_builder = dynamic_prompt_builder
        self.user_profile_service = user_profile_service
    
    async def get_user_specific_prompt(self, user: User) -> str:
        """获取用户特定的 System Prompt"""
        return await self.dynamic_prompt_builder.build_system_prompt(user)
    
    def get_user_tool_access(self, user: User) -> Dict[str, bool]:
        """
        获取用户的工具访问权限。
        
        Returns:
            工具名 -> 是否可访问的映射
        """
        group = user.group_memberships[0] if user.group_memberships else "user"
        
        # 默认权限配置
        permissions = {
            "RunSqlTool": True,  # 所有用户都可以执行 SQL
            "VisualizeDataTool": True,  # 所有用户都可以可视化
        }
        
        # Admin 有所有权限
        if group == "admin":
            permissions.update({
                "all_tools": True,
            })
        
        # Expert 可能有特殊权限（如果需要）
        elif group == "expert":
            permissions.update({
                "advanced_sql": True,
            })
        
        return permissions









