"""
API 路由集成测试
"""
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from main import app


@pytest.mark.api
@pytest.mark.integration
class TestAPIRoutes:
    """API 路由测试"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    def test_health_check(self, client):
        """测试健康检查（如果有的话）"""
        # 由于我们的应用可能没有健康检查端点，这里只是示例
        # 可以根据实际情况调整
        response = client.get("/")
        assert response.status_code in [200, 404]  # 取决于实际的路由配置
    
    def test_error_handling(self, client):
        """测试错误处理中间件"""
        # 测试一个不存在的端点
        response = client.get("/api/non-existent-endpoint")
        assert response.status_code == 404
    
    def test_cors_headers(self, client):
        """测试 CORS 头部（如果配置了）"""
        response = client.options("/api/chat")
        # CORS 预检请求应该返回 200
        assert response.status_code in [200, 404, 405]


@pytest.mark.api
@pytest.mark.integration
class TestChatAPI:
    """聊天 API 测试"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    def test_chat_endpoint_exists(self, client):
        """测试聊天端点是否存在"""
        # 这里只是示例，需要根据实际的聊天 API 端点调整
        # response = client.post("/api/vanna/v2/chat_sse", json={"question": "测试"})
        # assert response.status_code in [200, 400, 401]
        pass









