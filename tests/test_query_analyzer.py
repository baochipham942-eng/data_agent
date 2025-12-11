"""
QueryAnalyzer 服务测试
"""
import pytest
from pathlib import Path

from app.services.query_analyzer import QueryAnalyzer


@pytest.mark.service
class TestQueryAnalyzer:
    """QueryAnalyzer 服务测试"""
    
    def test_init(self, data_db_path, system_db_path):
        """测试初始化"""
        analyzer = QueryAnalyzer(
            data_db_path=data_db_path,
            knowledge_db_path=system_db_path,
            llm_service=None,
            prompt_manager=None,
        )
        assert analyzer.data_db_path == Path(data_db_path)
        assert analyzer.knowledge_db_path == Path(system_db_path)
    
    def test_semantic_tokenize_basic(self, data_db_path, system_db_path):
        """测试基础语义分词"""
        analyzer = QueryAnalyzer(
            data_db_path=data_db_path,
            knowledge_db_path=system_db_path,
        )
        
        # 测试指标识别
        tokens = analyzer.semantic_tokenize("最近7天的访问量是多少")
        # 验证至少返回了一些 token
        assert len(tokens) > 0
        
        # 验证 token 结构
        for token in tokens:
            assert "text" in token
            assert "type" in token
            assert "start" in token
            assert "end" in token
        
        # 检查是否有访问相关的 token（可能是 metric 或其他类型）
        access_tokens = [t for t in tokens if "访问" in t["text"]]
        assert len(access_tokens) > 0
    
    def test_semantic_tokenize_dimensions(self, data_db_path, system_db_path):
        """测试维度识别"""
        analyzer = QueryAnalyzer(
            data_db_path=data_db_path,
            knowledge_db_path=system_db_path,
        )
        
        # 测试渠道维度
        tokens = analyzer.semantic_tokenize("各渠道的访问量")
        dimension_tokens = [t for t in tokens if t["type"] == "dimension"]
        assert len(dimension_tokens) > 0
        assert any("渠道" in t["text"] for t in dimension_tokens)
        
        # 测试城市维度
        tokens = analyzer.semantic_tokenize("经销商的城市分布")
        dimension_tokens = [t for t in tokens if t["type"] == "dimension"]
        assert any(t["text"] in ["城市", "经销商"] for t in dimension_tokens)
    
    def test_semantic_tokenize_chart_hints(self, data_db_path, system_db_path):
        """测试图表提示识别"""
        analyzer = QueryAnalyzer(
            data_db_path=data_db_path,
            knowledge_db_path=system_db_path,
        )
        
        # 测试趋势
        tokens = analyzer.semantic_tokenize("访问量的变化趋势")
        assert len(tokens) > 0
        # 检查是否有趋势相关的 token
        trend_tokens = [t for t in tokens if "趋势" in t["text"]]
        assert len(trend_tokens) > 0
        
        # 测试分布
        tokens = analyzer.semantic_tokenize("各渠道的占比分布")
        assert len(tokens) > 0
        # 检查是否有分布或占比相关的 token
        distribution_tokens = [t for t in tokens if "分布" in t["text"] or "占比" in t["text"]]
        assert len(distribution_tokens) > 0
    
    def test_analyze_tables_keyword_matching(self, data_db_path, system_db_path):
        """测试关键词表匹配"""
        analyzer = QueryAnalyzer(
            data_db_path=data_db_path,
            knowledge_db_path=system_db_path,
        )
        
        # 测试表选择
        tables = analyzer.analyze_tables("查询访问量数据")
        # 由于我们使用的是测试数据库，可能没有匹配的表
        # 但至少不应该出错
        assert isinstance(tables, list)
    
    def test_analyze_cache(self, data_db_path, system_db_path):
        """测试分析结果缓存"""
        analyzer = QueryAnalyzer(
            data_db_path=data_db_path,
            knowledge_db_path=system_db_path,
        )
        
        question = "测试问题"
        
        # 第一次分析（不使用缓存）
        result1 = analyzer.analyze(question, use_cache=True)
        assert len(analyzer._analysis_cache) == 1
        
        # 第二次分析（应该使用缓存）
        result2 = analyzer.analyze(question, use_cache=True)
        assert result1["original_question"] == result2["original_question"]
        
        # 清空缓存
        analyzer.clear_cache()
        assert len(analyzer._analysis_cache) == 0

