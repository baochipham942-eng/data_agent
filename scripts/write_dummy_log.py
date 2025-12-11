import json
import sqlite3
from datetime import datetime

from app.config import LOGS_DB_PATH


def write_dummy_conversation():
    conn = sqlite3.connect(str(LOGS_DB_PATH))
    cur = conn.cursor()

    conversation_id = "test_conv_001"
    user_id = "mike@test"
    now = datetime.now().isoformat(timespec="seconds")

    # 1）插入一条会话记录
    cur.execute(
        """
        INSERT OR REPLACE INTO conversation
        (id, user_id, started_at, ended_at, source, has_error, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            user_id,
            now,
            now,
            "web",                     # 来源先写死
            0,                         # 没有错误
            "测试对话：用户问埋点数据，Agent 给出回答",  # 简单摘要
        ),
    )

    # 2）插入两条消息：一条 user，一条 assistant
    cur.execute(
        """
        INSERT INTO conversation_message
        (conversation_id, role, content, extra_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            "user",
            "最近7天按省份统计访问量",
            json.dumps({"note": "dummy user question"}, ensure_ascii=False),
            now,
        ),
    )

    cur.execute(
        """
        INSERT INTO conversation_message
        (conversation_id, role, content, extra_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            "assistant",
            "最近7天访问量最高的是江苏省，其次是浙江省和广东省。",
            json.dumps(
                {
                    "note": "dummy assistant answer",
                    "sql_example": "SELECT province, COUNT(DISTINCT gio_id) AS uv FROM gio_event WHERE dt >= date('now','-7 day') GROUP BY province"
                },
                ensure_ascii=False,
            ),
            now,
        ),
    )

    conn.commit()
    conn.close()
    print(f"已写入测试对话：{conversation_id}")


if __name__ == "__main__":
    write_dummy_conversation()
