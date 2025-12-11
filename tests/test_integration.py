"""
集成测试：测试多个组件协作
"""
import pytest
from pathlib import Path

from app.services.query_analyzer import QueryAnalyzer, init_query_analyzer
from app.services.prompt_config import PromptConfig
from app.services.prompt_manager import PromptManager
from app.services.business_knowledge import BusinessKnowledge


@pytest.mark.integration
class TestServiceIntegration:
    """服务集成测试"""
    
    def test_query_analyzer_with_knowledge(self, data_db_path, system_db_path):
        """测试 QueryAnalyzer 与 BusinessKnowledge 集成"""
        # 初始化业务知识库
        knowledge = BusinessKnowledge(db_path=system_db_path)
        knowledge.add_term("访问量", "页面访问次数", category="metric")
        
        # 初始化查询分析器
        analyzer = QueryAnalyzer(
            data_db_path=data_db_path,
            knowledge_db_path=system_db_path,
        )
        
        # 分析问题
        result = analyzer.analyze("最近7天的访问量")
        assert "original_question" in result
        assert "semantic_tokens" in result
    
    def test_prompt_manager_with_config(self, system_db_path):
        """测试 PromptManager 与 PromptConfig 集成"""
        # 初始化配置
        config = PromptConfig(db_path=system_db_path)
        
        # 创建测试 prompt
        config.create_prompt(
            name="test_prompt",
            version="v1.0",
            content="Test prompt content",
            category="test",
        )
        
        # 激活 prompt
        config.set_active_prompt("test_prompt", "v1.0")
        
        # 初始化管理器
        manager = PromptManager(config)
        
        # 刷新缓存
        manager.refresh_cache()
        
        # 获取 prompt
        content = manager.get_active_prompt_content("test_prompt", fallback="fallback")
        assert "Test prompt content" in content
    
    def test_full_analysis_flow(self, data_db_path, system_db_path):
        """测试完整分析流程"""
        # 1. 初始化知识库
        knowledge = BusinessKnowledge(db_path=system_db_path)
        knowledge.add_term("DAU", "日活跃用户数", category="metric")
        
        # 2. 初始化查询分析器
        analyzer = QueryAnalyzer(
            data_db_path=data_db_path,
            knowledge_db_path=system_db_path,
        )
        
        # 3. 执行分析
        question = "MPA最近的DAU如何"
        result = analyzer.analyze(question)
        
        # 验证结果
        assert result["original_question"] == question
        assert "semantic_tokens" in result
        assert "selected_tables" in result
        assert "relevant_knowledge" in result


@pytest.mark.e2e
class TestEndToEnd:
    """端到端测试"""
    
    def test_query_analysis_pipeline(self, data_db_path, system_db_path):
        """测试完整的查询分析管道"""
        # 初始化所有服务
        knowledge = BusinessKnowledge(db_path=system_db_path)
        prompt_config = PromptConfig(db_path=system_db_path)
        prompt_manager = PromptManager(prompt_config)
        
        analyzer = QueryAnalyzer(
            data_db_path=data_db_path,
            knowledge_db_path=system_db_path,
            prompt_manager=prompt_manager,
        )
        
        # 执行完整分析
        question = "各渠道来源的访问量占比分布"
        result = analyzer.analyze(question)
        
        # 验证各个组件都正常工作
        assert "original_question" in result
        assert "rewritten_question" in result
        assert "semantic_tokens" in result
        assert isinstance(result["semantic_tokens"], list)
        
        # 验证语义分词包含期望的类型
        token_types = [t["type"] for t in result["semantic_tokens"]]
        assert "dimension" in token_types or "metric" in token_types or "chart" in token_types

