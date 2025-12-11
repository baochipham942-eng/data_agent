"""
中间件测试
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse


@pytest.mark.integration
class TestErrorHandlerMiddleware:
    """错误处理中间件测试"""
    
    @pytest.fixture
    def app_with_error_handler(self):
        """创建带有错误处理中间件的测试应用"""
        from app.middleware.error_handler import ErrorHandlerMiddleware
        
        app = FastAPI()
        app.add_middleware(ErrorHandlerMiddleware)
        
        @app.get("/test-normal")
        async def normal():
            return {"status": "ok"}
        
        @app.get("/test-error")
        async def error():
            raise ValueError("Test error")
        
        @app.get("/test-not-found")
        async def not_found():
            raise FileNotFoundError("File not found")
        
        return app
    
    def test_normal_request(self, app_with_error_handler):
        """测试正常请求"""
        client = TestClient(app_with_error_handler)
        response = client.get("/test-normal")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_error_handling(self, app_with_error_handler):
        """测试错误处理"""
        client = TestClient(app_with_error_handler)
        response = client.get("/test-error")
        assert response.status_code == 400  # ValueError 应该返回 400
        data = response.json()
        assert "success" in data
        assert data["success"] is False
        assert "error" in data
    
    def test_not_found_error(self, app_with_error_handler):
        """测试 NotFound 错误"""
        client = TestClient(app_with_error_handler)
        response = client.get("/test-not-found")
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["type"] == "NotFound"









