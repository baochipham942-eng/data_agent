"""
Vercel Serverless Function 入口点
使用 Vercel Serverless Functions API 格式
"""
import sys
import os
import json
import traceback
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入主应用
try:
    from main import app
    from mangum import Mangum
    
    # 创建 Mangum 适配器
    mangum_app = Mangum(app, lifespan="off")
    
    # Vercel Serverless Functions API 格式
    def handler(request):
        """
        Vercel Serverless Functions handler
        
        Args:
            request: Vercel request object with method, path, headers, body, etc.
        
        Returns:
            Response dict with statusCode, headers, body
        """
        try:
            # 调用 Mangum 处理请求
            # Mangum 期望 AWS Lambda 格式的事件，我们需要转换
            event = {
                "httpMethod": request.get("method", "GET"),
                "path": request.get("path", "/"),
                "headers": request.get("headers", {}),
                "queryStringParameters": request.get("query", {}),
                "body": json.dumps(request.get("body", {})) if request.get("body") else None,
                "isBase64Encoded": False,
            }
            
            context = {}
            
            # 调用 Mangum
            response = mangum_app(event, context)
            
            return {
                "statusCode": response.get("statusCode", 200),
                "headers": response.get("headers", {}),
                "body": response.get("body", ""),
            }
        except Exception as e:
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Handler Error",
                    "message": str(e),
                    "traceback": traceback.format_exc() if os.getenv("VERCEL_ENV") == "development" else None
                })
            }
            
except Exception as e:
    # 如果导入失败，创建一个简单的错误 handler
    def handler(request):
        error_msg = str(e)
        if "DEEPSEEK_API_KEY" in error_msg or "缺少必要配置" in error_msg:
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Configuration Error",
                    "message": "DEEPSEEK_API_KEY 未配置",
                    "hint": "请在 Vercel 项目设置中添加环境变量 DEEPSEEK_API_KEY"
                })
            }
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Application initialization failed",
                "message": error_msg,
                "type": type(e).__name__,
                "traceback": traceback.format_exc() if os.getenv("VERCEL_ENV") == "development" else None
            })
        }
