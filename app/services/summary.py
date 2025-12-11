import json
import re
import sqlite3
from typing import List, Tuple

from app.config import LOGS_DB_PATH
from app.services.conversation_log import log_error
from vanna.integrations.openai import OpenAILlmService


def simplify_sse_message(raw: str) -> dict:
    """
    尝试把 SSE 流里的信息变成"可读摘要"：
    - 抽取主要回答文本（去重、过滤工具状态信息）
    - 抽取调用过的工具名
    - 粗略统计 chunk 数量
    """
    tools = set()
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip().startswith("data:")]
    text_parts: List[str] = []
    seen_texts = set()  # 用于去重

    # 需要过滤的工具状态关键词
    tool_status_keywords = [
        "Tool failed:",
        "Tool completed successfully",
        "Error executing query:",
        "Executing tools...",
        "Processing your request...",
        "Analyzing query",
        "Query executed successfully",
        "Results saved to file:",
        "**IMPORTANT: FOR VISUALIZE_DATA USE FILENAME:",
        "(Results truncated to",
        "FOR LARGE RESULTS YOU DO NOT NEED TO SUMMARIZE",
        "No rows returned",
        "row(s) affected",
        "Created visualization from",
        # 注意：不要过滤所有包含这些词的文本，只过滤纯状态消息
        # "我来帮您" - 保留，这是有用的开头
        # "让我" - 保留，可能是有用的
        # "现在让我" - 可以过滤
        "现在让我",
        # "首先" - 保留
        # "接下来" - 保留
        # "然后" - 保留
        # "最后" - 保留
        # "检查" - 保留，可能是有用的
        # "查询" - 保留
        # "确认" - 保留
        # "发现" - 保留
        # "包含" - 保留
        # "表结构" - 过滤技术细节
        "表结构",
        # "数据库" - 过滤技术细节
        "数据库",
        # "表名" - 过滤技术细节
        "表名",
        # "字段" - 过滤技术细节
        "字段",
        # "列名" - 过滤技术细节
        "列名",
        # "执行查询" - 过滤过程描述
        "执行查询",
        # "生成可视化" - 过滤过程描述
        "生成可视化",
        # "创建可视化" - 过滤过程描述
        "创建可视化",
        # "Tool limit reached" - 过滤工具限制提示
        "Tool limit reached",
        "Task may be incomplete",
    ]

    def should_include_text(text: str) -> bool:
        """判断文本是否应该包含在最终输出中"""
        if not text or not text.strip():
            return False
        
        # 过滤工具状态信息
        text_lower = text.lower()
        for keyword in tool_status_keywords:
            if keyword.lower() in text_lower:
                return False
        
        # 过滤纯状态消息
        if text.startswith("data:") or text.startswith("{"):
            return False
        
        # 过滤技术细节：包含"表"、"字段"、"列"等但主要是技术描述的短句
        if len(text.strip()) < 100:
            tech_patterns = [
                r"表\s*[名]?\s*[为是]",
                r"字段\s*[名为]",
                r"列\s*[名为]",
                r"包含\s*\d+\s*[行列]",
                r"结构\s*[如下]",
                r"event_key\s*[是为]",
            ]
            for pattern in tech_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    # 如果主要是技术描述，过滤掉
                    if any(word in text_lower for word in ["表", "字段", "列", "结构", "event_key", "database", "table"]):
                        return False
        
        return True

    for ln in lines:
        payload = ln[len("data:"):].strip()
        if not payload or payload == "[DONE]":
            continue

        try:
            obj = json.loads(payload)
        except Exception:
            # 如果不是 JSON，检查是否是纯文本
            if should_include_text(payload):
                if payload not in seen_texts:
                    text_parts.append(payload)
                    seen_texts.add(payload)
            continue

        # 提取文本内容（优先 simple.text，然后是 rich.data.content）
        # 但跳过 dataframe 和 chart 类型（这些是结构化数据，不是文本）
        text = None
        rich_type = obj.get("rich", {}).get("type")
        simple = obj.get("simple", {})
        
        # 跳过 dataframe 和 chart 类型（这些是结构化数据）
        if rich_type in ("dataframe", "chart"):
            # 从 dataframe 类型推断工具
            if rich_type == "dataframe":
                tools.add("RunSqlTool")
            elif rich_type == "chart":
                tools.add("VisualizeDataTool")
            continue
        
        if simple and isinstance(simple, dict) and simple.get("text"):
            text = simple["text"]
        elif obj.get("rich", {}).get("data", {}).get("content"):
            text = obj["rich"]["data"]["content"]
        elif obj.get("rich", {}).get("data", {}).get("message"):
            # 只包含有意义的 message，过滤状态栏消息
            message = obj["rich"]["data"]["message"]
            if rich_type not in ("status_bar_update", "task_tracker_update", "status_card"):
                text = message
        
        # 只添加有效的、未重复的文本
        if text and should_include_text(text) and text not in seen_texts:
            text_parts.append(text)
            seen_texts.add(text)

        # 提取工具名称
        rich_data = obj.get("rich", {}).get("data", {})
        if isinstance(rich_data, dict):
            tool_name = rich_data.get("tool_name") or rich_data.get("name")
            if tool_name:
                tools.add(tool_name)
        
        # 从 tool_call 相关类型中提取工具名
        if rich_type in ("tool_call", "tool_call_started", "tool_call_finished"):
            if isinstance(rich_data, dict):
                tool_name = rich_data.get("tool_name") or rich_data.get("name")
                if tool_name:
                    tools.add(tool_name)

    # 最终去重：合并相邻的重复行，过滤空行和CSV数据
    final_parts = []
    seen_texts = set()  # 全局去重集合
    prev_text = None
    
    # 过滤 CSV 数据行的正则
    csv_data_pattern = re.compile(r'^[\d\s,\-:\.\$]+$')
    timestamp_pattern = re.compile(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}')
    
    for text in text_parts:
        text_stripped = text.strip()
        # 跳过空行
        if not text_stripped:
            continue
        
        # 过滤 CSV 数据行
        if ',' in text_stripped and text_stripped.count(',') >= 2:
            # 如果主要是数字、逗号、时间戳，很可能是数据行
            if csv_data_pattern.match(text_stripped) or timestamp_pattern.search(text_stripped):
                continue
            # 如果包含 $ 符号且主要是数据格式，也跳过（如 $visit,2025-11-16...）
            if text_stripped.startswith('$') and text_stripped.count(',') >= 5:
                continue
        
        # 跳过与上一行相同的文本（相邻重复）
        if text_stripped == prev_text:
            continue
        
        # 跳过已见过的文本（全局去重）
        # 对于较短的文本（可能是重复的状态信息），严格去重
        if text_stripped in seen_texts:
            # 如果文本较短（可能是重复的状态信息），跳过
            if len(text_stripped) < 100:
                continue
            # 如果文本较长但完全相同，也跳过（避免重复的长文本）
            continue
        
        final_parts.append(text)
        prev_text = text_stripped
        seen_texts.add(text_stripped)
    
    display_text = "\n".join(final_parts).strip()
    if not display_text:
        display_text = raw[:500]

    return {
        "display_text": display_text,
        "tools": sorted(tools),
        "chunk_count": len(lines) or None,
    }


def prepare_summary_context(
    messages: List[Tuple[str, str, str]],
    max_len_per_msg: int = 400,
    max_total_len: int = 6000,
) -> str:
    """
    将一轮对话精简为适合 LLM 生成摘要的上下文：
    - 只保留 role + 简化后的内容
    - 对每条消息和整体长度都做截断
    """
    cleaned_blocks: List[str] = []

    for role, content, created_at in messages:
        if not content:
            continue

        content = content or ""

        if role == "assistant" and content.lstrip().startswith("data:"):
            simp = simplify_sse_message(content)
            short = simp["display_text"]
        else:
            short = content

        if len(short) > max_len_per_msg:
            short = short[:max_len_per_msg] + " ...（内容较长，已截断）"

        cleaned_blocks.append(f"[{role} {created_at}] {short}")

    full_text = "\n".join(cleaned_blocks)

    if len(full_text) > max_total_len:
        full_text = (
            full_text[: max_total_len // 2]
            + "\n...（中间多轮对话已省略）...\n"
            + full_text[-max_total_len // 2 :]
        )

    return full_text


def generate_summary_for_conversation(conv_id: str, llm: OpenAILlmService) -> str | None:
    """
    自动生成对话摘要：
    - 读取 logs/logs.db 中的对话记录
    - 精简上下文
    - 调用 LLM 生成摘要
    - 写回 conversation.summary
    """
    db_path = LOGS_DB_PATH
    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role, content, created_at
        FROM conversation_message
        WHERE conversation_id = ?
        ORDER BY created_at
        """,
        (conv_id,),
    )
    rows = cursor.fetchall()
    if not rows:
        conn.close()
        return None

    context_text = prepare_summary_context(rows)

    prompt = f"""
你是一个数据分析平台的对话日志助手。

下面是一轮用户与数据分析 Agent 的对话（已做精简）：
------------------------
{context_text}
------------------------

请用不超过 120 字总结这轮对话：
1）用户主要需求（如访问量统计、渠道分析、经销商对比）
2）Agent 查询的数据方向（时间范围 / 维度 / 指标）
3）最终结论（如哪个省份访问量最高等）
4）若出现错误，请总结错误

只输出一段简洁的中文摘要。
"""

    try:
        # 使用正确的 API 调用方式 - OpenAILlmService 使用 generate 方法
        if hasattr(llm, 'generate'):
            result = llm.generate(prompt=prompt)
        elif hasattr(llm, 'chat_completion'):
            result = llm.chat_completion(messages=[{"role": "user", "content": prompt}])
        elif hasattr(llm, 'chat'):
            result = llm.chat(messages=[{"role": "user", "content": prompt}])
        else:
            # 如果都没有，返回 None
            conn.close()
            return None
            
        # 提取结果文本
        if hasattr(result, "message"):
            summary = result.message
        elif hasattr(result, "content"):
            summary = result.content
        elif isinstance(result, str):
            summary = result
        else:
            summary = str(result)
    except Exception as e:
        conn.close()
        log_error(
            conversation_id=conv_id,
            error_message=f"generate_summary_for_conversation error: {e}",
        )
        return None

    cursor.execute(
        "UPDATE conversation SET summary = ? WHERE id = ?",
        (summary, conv_id),
    )
    conn.commit()
    conn.close()
    return summary

