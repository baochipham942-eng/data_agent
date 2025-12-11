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
    注册拦截 Vanna SSE 聊天接口的日志中间件。
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

        if hasattr(response, "body_iterator") and response.body_iterator is not None:
            original_iter = response.body_iterator

            async def logging_iterator():
                assistant_chunks: List[str] = []
                table_data = None
                chart_data = None
                extracted_sql = None
                try:
                    async for chunk in original_iter:
                        # 先yield chunk，确保流不会被阻塞
                        yield chunk
                        
                        # 然后尝试解析和提取数据（不影响流的传递）
                        try:
                            text = chunk.decode("utf-8")
                        except Exception as decode_error:
                            logger.debug(f"[logging_middleware] 解码chunk失败: {decode_error}")
                            text = ""
                        
                        if text:
                            assistant_chunks.append(text)
                            # 尝试从 SSE 流中提取图表和表格数据
                            if text.strip().startswith("data: "):
                                try:
                                    data_str = text.strip()[6:].strip()  # 移除 "data: " 前缀
                                    if data_str and data_str != "[DONE]":
                                        # 调试：打印原始数据（前200字符）
                                        if "tool_calls" in data_str or "run_sql" in data_str or "SELECT" in data_str.upper():
                                            logger.info(f"[logging_middleware] 🔍 发现可能包含 SQL 的数据: {data_str[:200]}")
                                        try:
                                            data_obj = json.loads(data_str)
                                        except json.JSONDecodeError as json_error:
                                            logger.debug(f"[logging_middleware] JSON解析失败: {json_error}, 数据: {data_str[:100]}")
                                            # JSON解析失败时，跳过后续处理，但chunk已经yield
                                            continue
                                        
                                        # 提取 tool_calls 中的 SQL
                                        try:
                                            if "tool_calls" in data_obj and isinstance(data_obj["tool_calls"], list):
                                                logger.info(f"[logging_middleware] 🔍 发现 tool_calls: {len(data_obj['tool_calls'])} 个")
                                                for tool_call in data_obj["tool_calls"]:
                                                    try:
                                                        func_name = tool_call.get("function", {}).get("name")
                                                        logger.info(f"[logging_middleware] 🔍 tool_call function: {func_name}")
                                                        if func_name == "run_sql":
                                                            args = tool_call.get("function", {}).get("arguments")
                                                            if args:
                                                                if isinstance(args, str):
                                                                    try:
                                                                        args = json.loads(args)
                                                                    except json.JSONDecodeError:
                                                                        logger.warning(f"[logging_middleware] tool_call arguments JSON解析失败")
                                                                        continue
                                                                if args.get("sql"):
                                                                    sql_str = args["sql"].strip()
                                                                    if sql_str.upper().startswith("SELECT"):
                                                                        extracted_sql = sql_str
                                                                        logger.info(f"[logging_middleware] ✅ 从 tool_calls 提取到 SQL: {sql_str[:80]}...")
                                                                        break
                                                    except Exception as tool_call_error:
                                                        logger.warning(f"[logging_middleware] 处理tool_call时出错: {tool_call_error}")
                                                        continue
                                            
                                            rich = data_obj.get("rich", {})
                                            rich_type = rich.get("type") if isinstance(rich, dict) else None
                                            rich_data = rich.get("data", {}) if isinstance(rich, dict) else {}
                                            
                                            # 从 dataframe metadata 提取 SQL
                                            if rich_type == "dataframe" and isinstance(rich_data, dict):
                                                try:
                                                    if "data" in rich_data and isinstance(rich_data["data"], list):
                                                        # 转换 dataframe 数据为对象数组
                                                        columns = rich_data.get("columns", [])
                                                        data_rows = rich_data["data"]
                                                        if columns and data_rows:
                                                            if len(data_rows) > 0 and isinstance(data_rows[0], list):
                                                                # 二维数组格式
                                                                table_data = [
                                                                    {col: row[i] if i < len(row) else None 
                                                                     for i, col in enumerate(columns)}
                                                                    for row in data_rows
                                                                ]
                                                            elif len(data_rows) > 0 and isinstance(data_rows[0], dict):
                                                                # 已经是对象数组
                                                                table_data = data_rows
                                                except Exception as table_error:
                                                    logger.warning(f"[logging_middleware] 处理table_data时出错: {table_error}")
                                                
                                                # 从 metadata 提取 SQL
                                                if not extracted_sql and rich_data.get("metadata"):
                                                    metadata = rich_data["metadata"]
                                                    if isinstance(metadata, dict) and metadata.get("sql"):
                                                        sql_str = metadata["sql"]
                                                        if isinstance(sql_str, str) and sql_str.upper().strip().startswith("SELECT"):
                                                            extracted_sql = sql_str.strip()
                                            
                                            # 从 status_card 提取 SQL
                                            if not extracted_sql and rich_type == "status_card" and isinstance(rich_data, dict):
                                                metadata = rich_data.get("metadata")
                                                if isinstance(metadata, dict) and metadata.get("sql"):
                                                    sql_str = metadata["sql"]
                                                    if isinstance(sql_str, str) and sql_str.upper().strip().startswith("SELECT"):
                                                        extracted_sql = sql_str.strip()
                                            
                                            # 提取图表数据（chart 类型）
                                            if rich_type == "chart" and isinstance(rich_data, dict):
                                                # 保存图表规格
                                                if "spec" in rich_data:
                                                    chart_data = rich_data["spec"]
                                                elif "chart" in rich_data:
                                                    chart_data = rich_data["chart"]
                                                elif "data" in rich_data:
                                                    chart_data = rich_data["data"]
                                        except (KeyError, TypeError, AttributeError) as parse_error:
                                            # 忽略解析错误，继续处理，但记录日志
                                            logger.debug(f"[logging_middleware] 解析SSE数据时出错: {parse_error}")
                                        except Exception as unexpected_error:
                                            # 捕获其他未预期的错误，记录但继续处理
                                            logger.error(f"[logging_middleware] 处理SSE数据时出现未预期错误: {unexpected_error}", exc_info=True)
                                except Exception as text_parse_error:
                                    # 即使文本解析出错，也不影响流的传递（chunk已经yield）
                                    logger.debug(f"[logging_middleware] 解析文本时出错: {text_parse_error}")
                except GeneratorExit:
                    # 生成器被关闭是正常的（客户端断开连接等），不需要记录错误
                    logger.debug(f"[logging_middleware] 生成器被关闭（可能是客户端断开连接）")
                    raise  # 重新抛出，让生成器正常关闭
                except Exception as stream_error:
                    # 如果迭代流时出错，记录错误
                    error_happened = True
                    logger.error(f"[logging_middleware] SSE流迭代时出错: {stream_error}", exc_info=True)
                    # 不要重新抛出异常，让流正常结束
                finally:
                    try:
                        if assistant_chunks:
                            full_text = "".join(assistant_chunks)
                            # 准备 extra 数据
                            extra = {}
                            if table_data:
                                extra["table_data"] = table_data
                            if chart_data:
                                extra["chart_data"] = chart_data
                            if extracted_sql:
                                extra["sql"] = extracted_sql
                                logger.info(f"[logging_middleware] ✅ 保存 SQL 到 extra_json: {extracted_sql[:80]}...")
                            else:
                                logger.warning(f"[logging_middleware] ⚠️ 未提取到 SQL，extra_json 将不包含 sql 字段")
                            
                            log_message(
                                conversation_id=conv_id,
                                role="assistant",
                                content=full_text,
                                extra=extra if extra else None,
                            )
                        log_conversation_end(
                            conversation_id=conv_id,
                            has_error=error_happened,
                        )
                    except Exception as log_error:
                        # 即使日志记录失败，也不影响响应
                        logger.error(f"[logging_middleware] 记录日志时出错: {log_error}", exc_info=True)

            response.body_iterator = logging_iterator()

        return response

