"""
EnhancedUserResolver 测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from vanna.core.user import RequestContext, User

from app.services.enhanced_user_resolver import EnhancedUserResolver
from app.services.agent_memory import UserProfileService, SqliteAgentMemory


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
def resolver(user_profile_service):
    """创建增强用户解析器"""
    return EnhancedUserResolver(user_profile_service=user_profile_service)


@pytest.mark.service
class TestEnhancedUserResolver:
    """EnhancedUserResolver 服务测试"""
    
    @pytest.mark.asyncio
    async def test_resolve_user_from_header(self, resolver):
        """测试从请求头识别用户"""
        request_context = MagicMock(spec=RequestContext)
        request_context.get_header = MagicMock(side_effect=lambda key: {
            "X-User-ID": "user123",
            "X-Email": "user123@example.com"
        }.get(key))
        request_context.get_cookie = MagicMock(return_value=None)
        
        user = await resolver.resolve_user(request_context)
        
        assert user.id == "user123"
        assert user.email == "user123@example.com"
        assert "user" in user.group_memberships
    
    @pytest.mark.asyncio
    async def test_resolve_user_from_cookie(self, resolver):
        """测试从 Cookie 识别用户"""
        request_context = MagicMock(spec=RequestContext)
        request_context.get_header = MagicMock(return_value=None)
        request_context.get_cookie = MagicMock(side_effect=lambda key: {
            "vanna_email": "cookie@example.com",
            "user_id": None
        }.get(key))
        
        user = await resolver.resolve_user(request_context)
        
        assert user.id == "cookie@example.com"
        assert user.email == "cookie@example.com"
    
    @pytest.mark.asyncio
    async def test_resolve_user_default_guest(self, resolver):
        """测试默认访客用户"""
        request_context = MagicMock(spec=RequestContext)
        request_context.get_header = MagicMock(return_value=None)
        request_context.get_cookie = MagicMock(return_value=None)
        
        user = await resolver.resolve_user(request_context)
        
        assert user.id == "guest@example.com"
        assert user.email == "guest@example.com"
        assert "user" in user.group_memberships
    
    @pytest.mark.asyncio
    async def test_resolve_admin_user(self, resolver):
        """测试识别管理员用户"""
        request_context = MagicMock(spec=RequestContext)
        request_context.get_header = MagicMock(return_value=None)
        request_context.get_cookie = MagicMock(side_effect=lambda key: {
            "vanna_email": "admin@example.com"
        }.get(key))
        
        user = await resolver.resolve_user(request_context)
        
        assert user.id == "admin@example.com"
        assert "admin" in user.group_memberships
    
    @pytest.mark.asyncio
    async def test_resolve_user_with_profile(self, resolver, user_profile_service, system_db_path):
        """测试带用户画像的用户识别"""
        # 创建用户画像
        await user_profile_service.create_or_update_profile(
            user_id="expert_user",
            nickname="Expert User",
            expertise_level="expert",
        )
        
        request_context = MagicMock(spec=RequestContext)
        request_context.get_header = MagicMock(side_effect=lambda key: {
            "X-User-ID": "expert_user"
        }.get(key) if key == "X-User-ID" else None)
        request_context.get_cookie = MagicMock(return_value=None)
        
        user = await resolver.resolve_user(request_context)
        
        assert user.id == "expert_user"
        assert user.metadata is not None
        assert user.metadata.get("expertise_level") == "expert"
        assert "expert" in user.group_memberships
    
    @pytest.mark.asyncio
    async def test_get_user_metadata(self, resolver, user_profile_service, system_db_path):
        """测试获取用户元数据"""
        # 创建用户画像
        await user_profile_service.create_or_update_profile(
            user_id="test_user",
            nickname="Test User",
            preferences={"preferred_chart_type": "line"},
            focus_dimensions=["时间", "渠道"],
            expertise_level="intermediate",
        )
        
        metadata = await resolver._get_user_metadata("test_user")
        
        assert metadata["nickname"] == "Test User"
        assert metadata["expertise_level"] == "intermediate"
        assert metadata["preferences"]["preferred_chart_type"] == "line"
        assert "时间" in metadata["focus_dimensions"]
    
    @pytest.mark.asyncio
    async def test_determine_user_group_from_profile(self, resolver, user_profile_service, system_db_path):
        """测试从用户画像确定用户组"""
        # 创建专家用户画像
        await user_profile_service.create_or_update_profile(
            user_id="expert_user",
            expertise_level="expert",
        )
        
        group = await resolver._determine_user_group("expert_user")
        assert group == "expert"
        
        # 创建管理员用户画像
        await user_profile_service.create_or_update_profile(
            user_id="admin_user",
            expertise_level="admin",
        )
        
        group = await resolver._determine_user_group("admin_user")
        assert group == "admin"
        
        # 默认用户
        group = await resolver._determine_user_group("regular_user")
        assert group == "user"









