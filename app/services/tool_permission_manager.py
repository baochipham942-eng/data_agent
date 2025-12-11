"""
工具权限管理器 - 管理用户对工具的访问权限
"""
import logging
from typing import Dict, List, Optional, Set
from vanna.core.user import User

logger = logging.getLogger(__name__)


class ToolPermissionManager:
    """工具权限管理器"""
    
    # 默认权限配置
    DEFAULT_PERMISSIONS = {
        "admin": {
            "allowed_tools": ["*"],  # 所有工具
            "restricted_tools": [],
        },
        "expert": {
            "allowed_tools": ["RunSqlTool", "VisualizeDataTool"],
            "restricted_tools": [],
        },
        "user": {
            "allowed_tools": ["RunSqlTool", "VisualizeDataTool"],
            "restricted_tools": [],
        },
        "guest": {
            "allowed_tools": ["RunSqlTool", "VisualizeDataTool"],
            "restricted_tools": [],
        },
    }
    
    def __init__(self):
        """初始化权限管理器"""
        self._permissions = self.DEFAULT_PERMISSIONS.copy()
    
    def check_tool_access(self, user: User, tool_name: str) -> bool:
        """
        检查用户是否有权限访问指定工具。
        
        Args:
            user: 用户对象
            tool_name: 工具名称
        
        Returns:
            True 如果有权限，False 如果没有权限
        """
        # 获取用户组
        groups = user.group_memberships or ["user"]
        primary_group = groups[0] if groups else "user"
        
        # 获取用户权限配置
        user_perms = self._permissions.get(primary_group, self._permissions["user"])
        
        # 检查受限工具
        if tool_name in user_perms.get("restricted_tools", []):
            logger.warning(f"用户 {user.id} 尝试访问受限工具: {tool_name}")
            return False
        
        # 检查允许的工具
        allowed_tools = user_perms.get("allowed_tools", [])
        
        # 如果允许所有工具
        if "*" in allowed_tools:
            return True
        
        # 检查特定工具
        if tool_name in allowed_tools:
            return True
        
        logger.warning(f"用户 {user.id} 尝试访问未授权的工具: {tool_name}")
        return False
    
    def get_allowed_tools(self, user: User) -> List[str]:
        """
        获取用户允许访问的工具列表。
        
        Args:
            user: 用户对象
        
        Returns:
            允许的工具名称列表
        """
        groups = user.group_memberships or ["user"]
        primary_group = groups[0] if groups else "user"
        
        user_perms = self._permissions.get(primary_group, self._permissions["user"])
        allowed_tools = user_perms.get("allowed_tools", [])
        
        if "*" in allowed_tools:
            # 返回所有已知工具
            return ["RunSqlTool", "VisualizeDataTool"]
        
        return allowed_tools
    
    def set_group_permissions(self, group: str, allowed_tools: List[str], restricted_tools: List[str] = None):
        """
        设置用户组的权限配置。
        
        Args:
            group: 用户组名称
            allowed_tools: 允许的工具列表
            restricted_tools: 受限的工具列表
        """
        self._permissions[group] = {
            "allowed_tools": allowed_tools,
            "restricted_tools": restricted_tools or [],
        }
        logger.info(f"已更新用户组 {group} 的权限配置")


# 全局权限管理器实例
_tool_permission_manager: Optional[ToolPermissionManager] = None


def get_tool_permission_manager() -> ToolPermissionManager:
    """获取全局工具权限管理器实例"""
    global _tool_permission_manager
    if _tool_permission_manager is None:
        _tool_permission_manager = ToolPermissionManager()
    return _tool_permission_manager









