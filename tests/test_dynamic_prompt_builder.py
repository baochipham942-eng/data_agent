"""
DynamicPromptBuilder 测试
"""
import pytest
from vanna.core.user import User

from app.services.dynamic_prompt_builder import DynamicPromptBuilder
from app.services.prompt_config import PromptConfig
from app.services.prompt_manager import PromptManager
from app.services.agent_memory import UserProfileService, SqliteAgentMemory


@pytest.fixture
def system_db_path(tmp_path):
    """创建临时系统数据库路径"""
    db_path = tmp_path / "system.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


@pytest.fixture
def prompt_manager(system_db_path):
    """创建 Prompt 管理器"""
    prompt_config = PromptConfig(db_path=system_db_path)
    return PromptManager(prompt_config)


@pytest.fixture
def user_profile_service(system_db_path):
    """创建用户画像服务"""
    memory = SqliteAgentMemory(db_path=system_db_path)
    return UserProfileService(memory)


@pytest.fixture
def dynamic_prompt_builder(prompt_manager, user_profile_service):
    """创建动态 Prompt 构建器"""
    return DynamicPromptBuilder(
        prompt_manager=prompt_manager,
        user_profile_service=user_profile_service,
    )


@pytest.mark.service
class TestDynamicPromptBuilder:
    """DynamicPromptBuilder 服务测试"""
    
    @pytest.mark.asyncio
    async def test_init(self, dynamic_prompt_builder):
        """测试初始化"""
        assert dynamic_prompt_builder.prompt_manager is not None
        assert dynamic_prompt_builder.user_profile_service is not None
    
    @pytest.mark.asyncio
    async def test_build_system_prompt_basic(self, dynamic_prompt_builder):
        """测试构建基础 System Prompt"""
        user = User(
            id="test_user",
            email="test@example.com",
            group_memberships=["user"],
        )
        
        prompt = await dynamic_prompt_builder.build_system_prompt(user)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # 应该包含基础提示内容
        assert "数据分析助手" in prompt or "数据分析" in prompt.lower()
    
    @pytest.mark.asyncio
    async def test_build_prompt_with_beginner_user(self, dynamic_prompt_builder, user_profile_service, system_db_path):
        """测试为初级用户构建 Prompt"""
        # 创建初级用户画像
        await user_profile_service.create_or_update_profile(
            user_id="beginner_user",
            expertise_level="beginner",
        )
        
        user = User(
            id="beginner_user",
            email="beginner@example.com",
            group_memberships=["user"],
            metadata={
                "expertise_level": "beginner",
            },
        )
        
        prompt = await dynamic_prompt_builder.build_system_prompt(user)
        
        assert "初级用户" in prompt or "详细" in prompt or "通俗" in prompt.lower()
    
    @pytest.mark.asyncio
    async def test_build_prompt_with_expert_user(self, dynamic_prompt_builder, user_profile_service, system_db_path):
        """测试为专家用户构建 Prompt"""
        # 创建专家用户画像
        await user_profile_service.create_or_update_profile(
            user_id="expert_user",
            expertise_level="expert",
        )
        
        user = User(
            id="expert_user",
            email="expert@example.com",
            group_memberships=["expert"],
            metadata={
                "expertise_level": "expert",
            },
        )
        
        prompt = await dynamic_prompt_builder.build_system_prompt(user)
        
        assert "专家用户" in prompt or "专业" in prompt or "深入" in prompt.lower()
    
    @pytest.mark.asyncio
    async def test_build_prompt_with_chart_preference(self, dynamic_prompt_builder, user_profile_service, system_db_path):
        """测试包含图表偏好的 Prompt"""
        # 创建带图表偏好的用户画像
        await user_profile_service.create_or_update_profile(
            user_id="pref_user",
            preferences={"preferred_chart_type": "pie"},
        )
        
        user = User(
            id="pref_user",
            email="pref@example.com",
            group_memberships=["user"],
            metadata={
                "preferences": {"preferred_chart_type": "pie"},
            },
        )
        
        prompt = await dynamic_prompt_builder.build_system_prompt(user)
        
        assert "pie" in prompt.lower() or "饼图" in prompt
    
    @pytest.mark.asyncio
    async def test_build_prompt_with_focus_dimensions(self, dynamic_prompt_builder, user_profile_service, system_db_path):
        """测试包含关注维度的 Prompt"""
        # 创建带关注维度的用户画像
        await user_profile_service.create_or_update_profile(
            user_id="dim_user",
            focus_dimensions=["时间", "渠道", "城市"],
        )
        
        user = User(
            id="dim_user",
            email="dim@example.com",
            group_memberships=["user"],
            metadata={
                "focus_dimensions": ["时间", "渠道", "城市"],
            },
        )
        
        prompt = await dynamic_prompt_builder.build_system_prompt(user)
        
        # 应该提到关注的维度
        assert "时间" in prompt or "渠道" in prompt or "维度" in prompt
    
    @pytest.mark.asyncio
    async def test_build_contextual_prompt(self, dynamic_prompt_builder):
        """测试构建上下文 Prompt"""
        user = User(
            id="test_user",
            email="test@example.com",
            group_memberships=["user"],
        )
        
        base_prompt = "Base prompt content"
        contextual_prompt = dynamic_prompt_builder.build_contextual_prompt(
            base_prompt=base_prompt,
            user=user,
        )
        
        assert contextual_prompt == base_prompt  # 目前返回基础 Prompt
    
    @pytest.mark.asyncio
    async def test_build_prompt_without_profile(self, dynamic_prompt_builder):
        """测试没有用户画像时的 Prompt 构建"""
        user = User(
            id="no_profile_user",
            email="no@example.com",
            group_memberships=["user"],
            metadata=None,  # 没有元数据
        )
        
        prompt = await dynamic_prompt_builder.build_system_prompt(user)
        
        # 应该返回基础 Prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 0









