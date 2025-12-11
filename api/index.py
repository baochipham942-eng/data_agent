"""
Vercel Serverless Function 入口点
Updated: Trigger redeployment
"""
import sys
import os
import traceback
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入主应用
try:
    from main import app
    
    # Vercel 的 Python runtime 需要将 ASGI 应用转换为兼容格式
    # 使用 mangum 适配器（专为 AWS Lambda/Vercel 设计）
    from mangum import Mangum
    
    # 创建 Mangum 适配器，禁用 lifespan 事件（Vercel 不支持）
    handler = Mangum(app, lifespan="off")
    
except ImportError as import_error:
    # 如果 mangum 导入失败，创建一个错误应用
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    error_app = FastAPI(title="Import Error")
    
    @error_app.get("/{path:path}")
    async def import_error_handler(path: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Import Error",
                "message": f"Failed to import mangum: {str(import_error)}",
                "hint": "mangum package is required for Vercel deployment",
                "path": path
            }
        )
    
    handler = error_app
        
except Exception as e:
    # 如果导入失败，创建一个友好的错误应用
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse, HTMLResponse
    
    error_app = FastAPI(title="Configuration Error")
    
    error_details = {
        "error": "Application initialization failed",
        "message": str(e),
        "type": type(e).__name__,
        "traceback": traceback.format_exc() if os.getenv("VERCEL_ENV") == "development" else None
    }
    
    @error_app.get("/{path:path}")
    async def error_handler(path: str):
        # 检查是否是配置错误
        if "DEEPSEEK_API_KEY" in str(e) or "缺少必要配置" in str(e):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Configuration Error",
                    "message": "DEEPSEEK_API_KEY 未配置",
                    "hint": "请在 Vercel 项目设置中添加环境变量 DEEPSEEK_API_KEY",
                    "path": path,
                    "how_to_fix": {
                        "step1": "访问 Vercel 项目设置",
                        "step2": "进入 Environment Variables",
                        "step3": "添加 DEEPSEEK_API_KEY 变量",
                        "step4": "重新部署项目"
                    }
                }
            )
        
        return JSONResponse(
            status_code=500,
            content=error_details
        )
    
    handler = error_app

