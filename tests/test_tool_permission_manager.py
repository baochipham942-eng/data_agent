"""
ToolPermissionManager 测试
"""
import pytest
from vanna.core.user import User

from app.services.tool_permission_manager import ToolPermissionManager, get_tool_permission_manager


@pytest.fixture
def permission_manager():
    """创建工具权限管理器"""
    return ToolPermissionManager()


@pytest.mark.service
class TestToolPermissionManager:
    """ToolPermissionManager 服务测试"""
    
    def test_init(self, permission_manager):
        """测试初始化"""
        assert permission_manager is not None
        assert hasattr(permission_manager, "_permissions")
    
    def test_check_tool_access_admin(self, permission_manager):
        """测试管理员工具访问"""
        admin_user = User(
            id="admin",
            email="admin@example.com",
            group_memberships=["admin"],
        )
        
        # 管理员应该有所有工具的访问权限
        assert permission_manager.check_tool_access(admin_user, "RunSqlTool") is True
        assert permission_manager.check_tool_access(admin_user, "VisualizeDataTool") is True
        assert permission_manager.check_tool_access(admin_user, "AnyTool") is True
    
    def test_check_tool_access_user(self, permission_manager):
        """测试普通用户工具访问"""
        user = User(
            id="user",
            email="user@example.com",
            group_memberships=["user"],
        )
        
        # 普通用户应该有基础工具的访问权限
        assert permission_manager.check_tool_access(user, "RunSqlTool") is True
        assert permission_manager.check_tool_access(user, "VisualizeDataTool") is True
        
        # 不应该有未授权的工具访问权限
        assert permission_manager.check_tool_access(user, "RestrictedTool") is False
    
    def test_check_tool_access_expert(self, permission_manager):
        """测试专家用户工具访问"""
        expert_user = User(
            id="expert",
            email="expert@example.com",
            group_memberships=["expert"],
        )
        
        # 专家用户应该有基础工具的访问权限
        assert permission_manager.check_tool_access(expert_user, "RunSqlTool") is True
        assert permission_manager.check_tool_access(expert_user, "VisualizeDataTool") is True
    
    def test_check_tool_access_guest(self, permission_manager):
        """测试访客工具访问"""
        guest_user = User(
            id="guest",
            email="guest@example.com",
            group_memberships=["guest"],
        )
        
        # 访客应该有基础工具的访问权限
        assert permission_manager.check_tool_access(guest_user, "RunSqlTool") is True
        assert permission_manager.check_tool_access(guest_user, "VisualizeDataTool") is True
    
    def test_check_restricted_tool(self, permission_manager):
        """测试受限工具访问"""
        # 设置受限工具
        permission_manager.set_group_permissions(
            group="user",
            allowed_tools=["RunSqlTool"],
            restricted_tools=["RestrictedTool"],
        )
        
        user = User(
            id="user",
            email="user@example.com",
            group_memberships=["user"],
        )
        
        # 即使工具在 allowed_tools 中，如果也在 restricted_tools 中，应该被拒绝
        assert permission_manager.check_tool_access(user, "RestrictedTool") is False
    
    def test_get_allowed_tools_admin(self, permission_manager):
        """测试获取管理员允许的工具"""
        admin_user = User(
            id="admin",
            email="admin@example.com",
            group_memberships=["admin"],
        )
        
        allowed_tools = permission_manager.get_allowed_tools(admin_user)
        
        # 管理员应该返回所有已知工具
        assert "RunSqlTool" in allowed_tools
        assert "VisualizeDataTool" in allowed_tools
    
    def test_get_allowed_tools_user(self, permission_manager):
        """测试获取普通用户允许的工具"""
        user = User(
            id="user",
            email="user@example.com",
            group_memberships=["user"],
        )
        
        allowed_tools = permission_manager.get_allowed_tools(user)
        
        assert "RunSqlTool" in allowed_tools
        assert "VisualizeDataTool" in allowed_tools
    
    def test_set_group_permissions(self, permission_manager):
        """测试设置用户组权限"""
        permission_manager.set_group_permissions(
            group="test_group",
            allowed_tools=["Tool1", "Tool2"],
            restricted_tools=["Tool3"],
        )
        
        assert "test_group" in permission_manager._permissions
        assert "Tool1" in permission_manager._permissions["test_group"]["allowed_tools"]
        assert "Tool3" in permission_manager._permissions["test_group"]["restricted_tools"]
    
    def test_get_tool_permission_manager_singleton(self):
        """测试单例模式"""
        manager1 = get_tool_permission_manager()
        manager2 = get_tool_permission_manager()
        
        # 应该返回同一个实例
        assert manager1 is manager2
    
    def test_check_tool_access_no_group(self, permission_manager):
        """测试没有用户组时的工具访问"""
        user = User(
            id="no_group_user",
            email="no@example.com",
            group_memberships=[],  # 没有用户组
        )
        
        # 应该使用默认的 user 权限
        assert permission_manager.check_tool_access(user, "RunSqlTool") is True









