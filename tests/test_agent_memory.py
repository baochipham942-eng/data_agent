"""
AgentMemory 服务测试
"""
import pytest
from pathlib import Path

from app.services.agent_memory import SqliteAgentMemory
from vanna.core.tool import ToolContext
from vanna.core.user import User


@pytest.mark.service
class TestAgentMemory:
    """AgentMemory 服务测试"""
    
    @pytest.fixture
    def memory(self, system_db_path):
        """创建 AgentMemory 实例"""
        return SqliteAgentMemory(db_path=system_db_path, max_items=100)
    
    @pytest.fixture
    def tool_context(self, memory):
        """创建 ToolContext 用于测试"""
        return ToolContext(
            user=User(id="test_user", email="test@test.com"),
            conversation_id="test_conv",
            request_id="test_req",
            agent_memory=memory,
        )
    
    def test_init(self, system_db_path):
        """测试初始化"""
        memory = SqliteAgentMemory(db_path=system_db_path)
        assert memory.db_path == Path(system_db_path)
        assert memory._max_items == 10000  # 默认值
    
    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_save_tool_usage(self, memory, tool_context):
        """测试保存工具使用记录"""
        await memory.save_tool_usage(
            question="测试问题",
            tool_name="RunSqlTool",
            args={"sql": "SELECT * FROM test"},
            context=tool_context,
            success=True,
            user_id="test_user",
        )
        
        # 搜索记忆
        search_results = await memory.search_similar_usage(
            question="测试",
            context=tool_context,
            limit=5,
            user_id="test_user",
        )
        assert len(search_results) > 0
        assert any("测试" in r.memory.question for r in search_results)
    
    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_save_text_memory(self, memory, tool_context):
        """测试保存文本记忆"""
        result = await memory.save_text_memory(
            content="这是一段测试文本",
            context=tool_context,
            user_id="test_user",
        )
        
        assert result.memory_id is not None
        assert result.content == "这是一段测试文本"
        
        # 搜索记忆（降低相似度阈值以确保能找到结果）
        search_results = await memory.search_text_memories(
            query="测试",
            context=tool_context,
            limit=5,
            user_id="test_user",
            similarity_threshold=0.1,  # 降低阈值
        )
        assert len(search_results) > 0
        assert any("测试" in r.memory.content for r in search_results)
    
    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_user_isolation(self, memory):
        """测试用户隔离"""
        # 创建两个不同用户的 context
        context1 = ToolContext(
            user=User(id="user1", email="user1@test.com"),
            conversation_id="conv1",
            request_id="req1",
            agent_memory=memory,
        )
        
        context2 = ToolContext(
            user=User(id="user2", email="user2@test.com"),
            conversation_id="conv2",
            request_id="req2",
            agent_memory=memory,
        )
        
        # 为用户1添加记忆
        await memory.save_text_memory(
            content="用户1的测试内容",
            context=context1,
            user_id="user1",
        )
        
        # 为用户2添加记忆
        await memory.save_text_memory(
            content="用户2的测试内容",
            context=context2,
            user_id="user2",
        )
        
        # 搜索用户1的记忆（不包含系统记忆，降低相似度阈值）
        results = await memory.search_text_memories(
            query="用户1",
            context=context1,
            limit=10,
            user_id="user1",
            include_system=False,
            similarity_threshold=0.1,  # 降低阈值
        )
        assert len(results) > 0
        assert all("用户1" in r.memory.content for r in results)
        
        # 搜索用户2的记忆
        results = await memory.search_text_memories(
            query="用户2",
            context=context2,
            limit=10,
            user_id="user2",
            include_system=False,
            similarity_threshold=0.1,  # 降低阈值
        )
        assert len(results) > 0
        assert all("用户2" in r.memory.content for r in results)

