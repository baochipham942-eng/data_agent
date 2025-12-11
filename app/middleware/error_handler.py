"""
统一错误处理中间件。

提供：
- 统一的错误响应格式
- 错误日志记录
- 异常捕获和转换
"""

import logging
import traceback
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """统一错误处理中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并捕获异常"""
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            return await self._handle_exception(request, e)
    
    async def _handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """处理异常并返回统一格式的错误响应"""
        
        # 记录错误日志
        error_msg = str(exc)
        error_trace = traceback.format_exc()
        
        logger.error(
            f"请求处理失败: {request.method} {request.url.path}\n"
            f"错误: {error_msg}\n"
            f"堆栈: {error_trace}"
        )
        
        # 根据异常类型返回不同的状态码
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_type = "InternalServerError"
        
        if isinstance(exc, ValueError):
            status_code = status.HTTP_400_BAD_REQUEST
            error_type = "BadRequest"
        elif isinstance(exc, KeyError):
            status_code = status.HTTP_400_BAD_REQUEST
            error_type = "BadRequest"
        elif isinstance(exc, FileNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
            error_type = "NotFound"
        elif isinstance(exc, PermissionError):
            status_code = status.HTTP_403_FORBIDDEN
            error_type = "Forbidden"
        
        # 返回统一格式的错误响应
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "error": {
                    "type": error_type,
                    "message": error_msg,
                    "path": str(request.url.path),
                }
            }
        )


def register_error_handler_middleware(app):
    """注册错误处理中间件"""
    app.add_middleware(ErrorHandlerMiddleware)
    logger.info("已注册统一错误处理中间件")









