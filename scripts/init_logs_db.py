import os
import sqlite3
from pathlib import Path

from app.config import LOGS_DB_PATH

LOGS_DIR = Path(LOGS_DB_PATH).parent


def init_db():
    # 确保 logs 目录存在
    os.makedirs(LOGS_DIR, exist_ok=True)

    conn = sqlite3.connect(str(LOGS_DB_PATH))
    cur = conn.cursor()

    # 1）会话表：一轮对话一条记录
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation (
            id TEXT PRIMARY KEY,      -- 会话ID，例如前端传的 conversation_id
            user_id TEXT,             -- 用户ID或邮箱
            started_at TEXT,          -- 会话开始时间（ISO 字符串）
            ended_at TEXT,            -- 会话结束时间（可以先留空）
            source TEXT,              -- 来源：web / api / internal 等
            has_error INTEGER,        -- 是否出现错误：0/1
            summary TEXT              -- 可选：对话摘要（后面可以让模型生成）
        )
        """
    )

    # 2）消息表：一条问答 / tool 调用对应一条记录
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,     -- 归属会话
            role TEXT,                -- 'user' / 'assistant' / 'tool' / 'system'
            content TEXT,             -- 展示给人的内容
            extra_json TEXT,          -- 附加信息：SQL、tool 参数、错误信息等（JSON 字符串）
            created_at TEXT           -- 消息时间（ISO 字符串）
        )
        """
    )

    conn.commit()
    conn.close()
    print(f"日志数据库初始化完成：{LOGS_DB_PATH}")


if __name__ == "__main__":
    init_db()
