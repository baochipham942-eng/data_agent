"""
BusinessKnowledge 服务测试
"""
import pytest
from pathlib import Path
import json

from app.services.business_knowledge import BusinessKnowledge


@pytest.mark.service
class TestBusinessKnowledge:
    """BusinessKnowledge 服务测试"""
    
    def test_init(self, system_db_path):
        """测试初始化"""
        knowledge = BusinessKnowledge(db_path=system_db_path)
        assert knowledge.db_path == Path(system_db_path)
    
    def test_add_term(self, system_db_path):
        """测试添加业务术语"""
        knowledge = BusinessKnowledge(db_path=system_db_path)
        
        knowledge.add_term(
            term="DAU",
            definition="日活跃用户数",
            sql_expression="COUNT(DISTINCT user_id)",
            category="metric",
        )
        
        # 验证术语已添加
        terms = knowledge.search_terms("DAU")
        assert len(terms) > 0
        assert any(t["term"] == "DAU" for t in terms)
    
    def test_add_field_mapping(self, system_db_path):
        """测试添加字段映射"""
        knowledge = BusinessKnowledge(db_path=system_db_path)
        
        knowledge.add_field_mapping(
            display_name="北京",
            table_name="sales",
            field_name="city",
            field_value="beijing",
            description="北京城市",
        )
        
        # 验证映射已添加
        mappings = knowledge.search_field_mappings("北京")
        assert len(mappings) > 0
        assert any(m["display_name"] == "北京" for m in mappings)
    
    def test_parse_time_expression(self, system_db_path):
        """测试时间表达式解析"""
        knowledge = BusinessKnowledge(db_path=system_db_path)
        
        # 测试相对时间
        result = knowledge.parse_time_expression("最近7天")
        assert result is not None
        assert result["type"] == "relative" or result["type"] == "range"
        
        # 测试今天
        result = knowledge.parse_time_expression("今天的数据")
        assert result is not None
    
    def test_search_terms(self, system_db_path):
        """测试术语搜索"""
        knowledge = BusinessKnowledge(db_path=system_db_path)
        
        # 添加测试术语
        knowledge.add_term("测试术语", "这是一个测试术语", category="test")
        
        # 搜索
        results = knowledge.search_terms("测试")
        assert len(results) > 0
        assert any("测试" in t["term"] or "测试" in t["definition"] for t in results)
    
    def test_get_stats(self, system_db_path):
        """测试获取统计信息"""
        knowledge = BusinessKnowledge(db_path=system_db_path)
        
        stats = knowledge.get_stats()
        assert "terms_count" in stats
        assert "mappings_count" in stats
        assert "time_rules_count" in stats
        assert all(isinstance(v, int) for v in stats.values())

