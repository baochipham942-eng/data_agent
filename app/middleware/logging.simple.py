import json
import logging
import time
import uuid
from typing import List

from fastapi import Request

from app.services.conversation_log import (
    log_conversation_start,
    log_message,
    log_error,
    log_conversation_end,
)

logger = logging.getLogger(__name__)


def register_logging_middleware(app):
    """
    简化版的日志中间件 - 只做最基本的数据传递和日志记录
    移除所有复杂的解析逻辑，确保SSE流不被中断
    """

    @app.middleware("http")
    async def vanna_logging_middleware(request: Request, call_next):
        path = request.url.path

        if path != "/api/vanna/v2/chat_sse":
            return await call_next(request)

        body_bytes = await request.body()
        try:
            body_json = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            body_json = {}

        conv_id = body_json.get("conversation_id")
        if not conv_id:
            conv_id = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"

        # 优先从请求体获取用户信息，fallback 到 cookie
        user_id = body_json.get("user_id") or request.cookies.get("vanna_email", "guest")
        user_nickname = body_json.get("user_nickname") or user_id

        # 获取用户消息：优先从 message 字段（字符串），然后从 messages 数组
        user_msg = ""
        if "message" in body_json and body_json["message"]:
            user_msg = body_json["message"]
        else:
            for msg in body_json.get("messages", []):
                if msg.get("role") == "user":
                    user_msg = msg.get("content") or ""
                    break

        log_conversation_start(
            conversation_id=conv_id,
            user_id=user_id,
            source="vanna_ui",
            user_nickname=user_nickname,
        )
        if user_msg:
            log_message(
                conversation_id=conv_id,
                role="user",
                content=user_msg,
            )

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        request = Request(request.scope, receive=receive)

        error_happened = False

        try:
            response = await call_next(request)
        except Exception as e:
            error_happened = True
            log_error(
                conversation_id=conv_id,
                error_message=f"Exception in chat_sse: {e}",
            )
            log_conversation_end(
                conversation_id=conv_id,
                has_error=True,
            )
            raise

        # 简化：只记录响应，不做任何解析，确保流能正常传递
        if hasattr(response, "body_iterator") and response.body_iterator is not None:
            original_iter = response.body_iterator

            async def logging_iterator():
                assistant_chunks: List[str] = []
                try:
                    # 直接传递所有chunk，不做任何解析
                    async for chunk in original_iter:
                        # 先yield，确保流不被阻塞
                        yield chunk
                        # 只做最基本的收集，用于日志记录
                        try:
                            text = chunk.decode("utf-8")
                            if text:
                                assistant_chunks.append(text)
                        except Exception:
                            pass
                except GeneratorExit:
                    # 正常关闭，不做处理
                    raise
                except Exception as stream_error:
                    error_happened = True
                    logger.error(f"[logging_middleware] SSE流迭代时出错: {stream_error}", exc_info=True)
                    # 不要重新抛出，让流正常结束
                finally:
                    # 记录日志（异步，不阻塞）
                    try:
                        if assistant_chunks:
                            full_text = "".join(assistant_chunks)
                            # 只在最后记录完整消息，不做SQL提取
                            log_message(
                                conversation_id=conv_id,
                                role="assistant",
                                content=full_text,
                            )
                        log_conversation_end(
                            conversation_id=conv_id,
                            has_error=error_happened,
                        )
                    except Exception as log_error:
                        logger.error(f"[logging_middleware] 记录日志时出错: {log_error}", exc_info=True)

            response.body_iterator = logging_iterator()

        return response








