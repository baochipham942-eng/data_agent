import sqlite3
import json
import logging
from datetime import datetime

from app.config import LOGS_DB_PATH

logger = logging.getLogger(__name__)


def _get_conn():
    """内部小工具：打开一个到 logs.db 的连接"""
    return sqlite3.connect(str(LOGS_DB_PATH))


def log_conversation_start(conversation_id: str, user_id: str, source: str = "web", user_nickname: str | None = None):
    """
    开始一轮新的对话时调用：
    - 如果不存在，就插入一条 conversation 记录
    - 如果已经存在，可以更新 started_at
    - 自动保存用户昵称（如果提供）
    """
    now = datetime.now().isoformat(timespec="seconds")

    conn = _get_conn()
    cur = conn.cursor()
    
    # 确保 user_nickname 列存在
    try:
        cur.execute("ALTER TABLE conversation ADD COLUMN user_nickname TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        # 列已存在，忽略
        pass
    
    cur.execute(
        """
        INSERT OR IGNORE INTO conversation
        (id, user_id, user_nickname, started_at, source, has_error)
        VALUES (?, ?, ?, ?, ?, 0)
        """,
        (conversation_id, user_id, user_nickname, now, source),
    )

    # 如果已经存在，更新 started_at 和 user_nickname（如果提供）
    if user_nickname:
        cur.execute(
            """
            UPDATE conversation
            SET started_at = COALESCE(started_at, ?),
                user_nickname = COALESCE(?, user_nickname)
            WHERE id = ?
            """,
            (now, user_nickname, conversation_id),
        )
    else:
        cur.execute(
            """
            UPDATE conversation
            SET started_at = COALESCE(started_at, ?)
            WHERE id = ?
            """,
            (now, conversation_id),
        )

    conn.commit()
    conn.close()


def log_conversation_end(conversation_id: str, has_error: bool = False, summary: str | None = None):
    """
    一轮对话结束时调用：
    - 更新 ended_at
    - 标记是否有错误
    - 可以写一个简单摘要（后续也可以让大模型自动生成）
    """
    now = datetime.now().isoformat(timespec="seconds")

    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE conversation
        SET ended_at = ?,
            has_error = CASE WHEN ? THEN 1 ELSE has_error END,
            summary = COALESCE(?, summary)
        WHERE id = ?
        """,
        (now, has_error, summary, conversation_id),
    )
    conn.commit()
    conn.close()


def log_message(
    conversation_id: str,
    role: str,
    content: str,
    extra: dict | None = None,
):
    """
    每产生一条消息（user / assistant / tool），调用一次：
    - role: 'user' / 'assistant' / 'tool' / 'system'
    - content: 展示给前端的文本
    - extra: 任意附加信息，会以 JSON 字符串形式存储
    """
    now = datetime.now().isoformat(timespec="seconds")
    extra_json = json.dumps(extra or {}, ensure_ascii=False)

    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO conversation_message
        (conversation_id, role, content, extra_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (conversation_id, role, content, extra_json, now),
    )
    conn.commit()
    conn.close()


def update_message_extra(
    conversation_id: str,
    role: str,
    extra: dict,
):
    """
    更新最近一条指定角色的消息的 extra_json 字段
    用于在流式完成后保存完整的推理步骤等数据
    
    Args:
        conversation_id: 会话ID
        role: 消息角色（通常是 'assistant'）
        extra: 要更新的额外数据字典（会与现有数据合并）
    """
    conn = _get_conn()
    cur = conn.cursor()
    
    # 查找最近一条指定角色的消息
    msg = cur.execute(
        """
        SELECT id, extra_json
        FROM conversation_message
        WHERE conversation_id = ? AND role = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (conversation_id, role),
    ).fetchone()
    
    if not msg:
        logger.warning(f"未找到会话 {conversation_id} 的角色 {role} 的消息，无法更新")
        conn.close()
        return
    
    # 合并现有的 extra_json 和新数据
    existing_extra = {}
    if msg[1]:  # msg[1] 是 extra_json
        try:
            existing_extra = json.loads(msg[1])
        except (json.JSONDecodeError, TypeError):
            existing_extra = {}
    
    # 合并数据（新数据覆盖旧数据）
    merged_extra = {**existing_extra, **extra}
    merged_extra_json = json.dumps(merged_extra, ensure_ascii=False)
    
    # 更新消息
    cur.execute(
        """
        UPDATE conversation_message
        SET extra_json = ?
        WHERE id = ?
        """,
        (merged_extra_json, msg[0]),  # msg[0] 是 id
    )
    
    conn.commit()
    conn.close()


def log_error(conversation_id: str, error_message: str, extra: dict | None = None):
    """
    统一的错误记录入口：
    - 在 message 表里插一条 role='system' 的错误信息
    - 把 conversation.has_error 标记为 1
    """
    merged_extra = extra.copy() if extra else {}
    merged_extra["error_message"] = error_message

    # 写一条 system 消息
    log_message(
        conversation_id=conversation_id,
        role="system",
        content=f"[ERROR] {error_message}",
        extra=merged_extra,
    )

    # 标记会话有错误
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE conversation SET has_error = 1 WHERE id = ?",
        (conversation_id,),
    )
    conn.commit()
    conn.close()
