"""
Agent 优化组件集成测试
"""
import pytest
from unittest.mock import MagicMock
from vanna.core.user import User, RequestContext

from app.services.enhanced_user_resolver import EnhancedUserResolver
from app.services.dynamic_prompt_builder import DynamicPromptBuilder
from app.services.tool_permission_manager import ToolPermissionManager
from app.services.prompt_config import PromptConfig
from app.services.prompt_manager import PromptManager
from app.services.agent_memory import SqliteAgentMemory, UserProfileService


@pytest.fixture
def system_db_path(tmp_path):
    """创建临时系统数据库路径"""
    db_path = tmp_path / "system.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


@pytest.fixture
def user_profile_service(system_db_path):
    """创建用户画像服务"""
    memory = SqliteAgentMemory(db_path=system_db_path)
    return UserProfileService(memory)


@pytest.fixture
def prompt_manager(system_db_path):
    """创建 Prompt 管理器"""
    prompt_config = PromptConfig(db_path=system_db_path)
    return PromptManager(prompt_config)


@pytest.mark.integration
class TestAgentOptimizationIntegration:
    """Agent 优化组件集成测试"""
    
    @pytest.mark.asyncio
    async def test_user_resolver_with_profile_and_prompt_builder(
        self, system_db_path, user_profile_service, prompt_manager
    ):
        """测试用户解析器与动态 Prompt 构建器集成"""
        # 创建用户画像
        await user_profile_service.create_or_update_profile(
            user_id="test_user",
            nickname="Test User",
            expertise_level="expert",
            preferences={"preferred_chart_type": "line"},
            focus_dimensions=["时间", "渠道"],
        )
        
        # 创建用户解析器
        resolver = EnhancedUserResolver(user_profile_service=user_profile_service)
        
        # 模拟请求上下文
        request_context = MagicMock(spec=RequestContext)
        request_context.get_header = MagicMock(side_effect=lambda key: {
            "X-User-ID": "test_user"
        }.get(key) if key == "X-User-ID" else None)
        request_context.get_cookie = MagicMock(return_value=None)
        
        # 解析用户
        user = await resolver.resolve_user(request_context)
        
        assert user.id == "test_user"
        assert user.metadata is not None
        assert user.metadata["expertise_level"] == "expert"
        
        # 创建动态 Prompt 构建器
        prompt_builder = DynamicPromptBuilder(
            prompt_manager=prompt_manager,
            user_profile_service=user_profile_service,
        )
        
        # 构建个性化 Prompt
        prompt = await prompt_builder.build_system_prompt(user)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # 应该包含个性化内容
        assert "专家用户" in prompt or "expert" in prompt.lower() or "line" in prompt.lower()
    
    @pytest.mark.asyncio
    async def test_permission_manager_with_user_groups(
        self, system_db_path, user_profile_service
    ):
        """测试权限管理器与用户组集成"""
        # 创建不同级别的用户画像
        await user_profile_service.create_or_update_profile(
            user_id="admin_user",
            expertise_level="admin",
        )
        
        await user_profile_service.create_or_update_profile(
            user_id="expert_user",
            expertise_level="expert",
        )
        
        await user_profile_service.create_or_update_profile(
            user_id="regular_user",
            expertise_level="beginner",
        )
        
        # 创建用户解析器
        resolver = EnhancedUserResolver(user_profile_service=user_profile_service)
        
        # 创建权限管理器
        permission_manager = ToolPermissionManager()
        
        # 测试不同用户的权限
        test_cases = [
            ("admin_user", ["admin"], True),  # 管理员有所有权限
            ("expert_user", ["expert"], True),  # 专家有基础工具权限
            ("regular_user", ["user"], True),  # 普通用户有基础工具权限
        ]
        
        for user_id, groups, should_have_access in test_cases:
            user = User(
                id=user_id,
                email=f"{user_id}@example.com",
                group_memberships=groups,
            )
            
            # 所有用户都应该能访问基础工具
            assert permission_manager.check_tool_access(user, "RunSqlTool") == should_have_access
            assert permission_manager.check_tool_access(user, "VisualizeDataTool") == should_have_access
    
    @pytest.mark.asyncio
    async def test_full_optimization_flow(
        self, system_db_path, user_profile_service, prompt_manager
    ):
        """测试完整的优化流程"""
        # 1. 创建用户画像
        await user_profile_service.create_or_update_profile(
            user_id="optimized_user",
            nickname="Optimized User",
            expertise_level="intermediate",
            preferences={"preferred_chart_type": "bar"},
            focus_dimensions=["渠道"],
        )
        
        # 2. 创建用户解析器
        resolver = EnhancedUserResolver(user_profile_service=user_profile_service)
        
        # 3. 模拟请求
        request_context = MagicMock(spec=RequestContext)
        request_context.get_header = MagicMock(side_effect=lambda key: {
            "X-User-ID": "optimized_user"
        }.get(key) if key == "X-User-ID" else None)
        request_context.get_cookie = MagicMock(return_value=None)
        
        user = await resolver.resolve_user(request_context)
        
        # 4. 验证用户信息
        assert user.id == "optimized_user"
        assert user.metadata["expertise_level"] == "intermediate"
        assert user.metadata["preferences"]["preferred_chart_type"] == "bar"
        
        # 5. 构建个性化 Prompt
        prompt_builder = DynamicPromptBuilder(
            prompt_manager=prompt_manager,
            user_profile_service=user_profile_service,
        )
        prompt = await prompt_builder.build_system_prompt(user)
        
        # 6. 检查权限
        permission_manager = ToolPermissionManager()
        assert permission_manager.check_tool_access(user, "RunSqlTool") is True
        assert permission_manager.check_tool_access(user, "VisualizeDataTool") is True
        
        # 7. 验证所有组件协同工作
        assert user.metadata is not None
        assert isinstance(prompt, str)
        assert len(prompt) > 0









