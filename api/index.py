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
    
    # Vercel 的 Python runtime 期望 WSGI 应用，但 FastAPI 是 ASGI
    # 尝试使用 asgiref 将 ASGI 转换为 WSGI
    try:
        from asgiref.wsgi import WsgiToAsgi
        # 将 ASGI 应用包装为 WSGI 兼容格式
        handler = WsgiToAsgi(app)
    except (ImportError, AttributeError):
        # 如果转换失败，尝试直接导出（可能不工作）
        # 或者使用 mangum（如果可用）
        try:
            from mangum import Mangum
            handler = Mangum(app, lifespan="off")
        except ImportError:
            # 最后尝试直接导出
            handler = app
        
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

