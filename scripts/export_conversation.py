import argparse
import json
import sqlite3
from datetime import datetime
from app.config import LOGS_DB_PATH, PROJECT_ROOT

EXPORT_DIR = PROJECT_ROOT / "outputs" / "exports"


def export_conversation(conv_id, to="json"):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(LOGS_DB_PATH))
    conn.row_factory = sqlite3.Row

    # 查对话主体
    conv = conn.execute("""
        SELECT * FROM conversation WHERE id=?
    """, (conv_id,)).fetchone()

    if not conv:
        print(f"❌ 没找到对话：{conv_id}")
        return

    # 查 message 列表
    messages = conn.execute("""
        SELECT role, content, extra_json, created_at
        FROM conversation_message
        WHERE conversation_id=?
        ORDER BY created_at
    """, (conv_id,)).fetchall()

    conn.close()

    # 结构化输出
    conv_dict = {
        "conversation_id": conv["id"],
        "user_id": conv["user_id"],
        "started_at": conv["started_at"],
        "ended_at": conv["ended_at"],
        "source": conv["source"],
        "has_error": bool(conv["has_error"]),
        "summary": conv["summary"],
        "messages": []
    }

    for m in messages:
        conv_dict["messages"].append({
            "role": m["role"],
            "content": m["content"],
            "extra": json.loads(m["extra_json"]) if m["extra_json"] else None,
            "created_at": m["created_at"]
        })

    # 输出文件名
    filename = (
        EXPORT_DIR / f"export_{conv_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{to}"
    )

    if to == "json":
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(conv_dict, f, ensure_ascii=False, indent=2)
    else:
        print("暂时只支持 JSON 导出")
        return

    print(f"✅ 导出成功：{filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="导出对话日志")
    parser.add_argument("--id", required=True, help="对话 ID")
    parser.add_argument("--format", default="json", help="导出格式（默认 json）")
    args = parser.parse_args()

    export_conversation(args.id, args.format)
