from app.services.conversation_log import (
    log_conversation_start,
    log_message,
    log_conversation_end,
)

def main():
    cid = "test_conv_002"
    user_id = "test_user_002"

    log_conversation_start(cid, user_id=user_id, source="manual_test_script")
    log_message(cid, "user", "这是用户通过脚本写入的测试消息", extra={"from": "test_script"})
    log_message(cid, "assistant", "这是助手的测试回复（通过脚本写入）")
    log_conversation_end(cid, has_error=False, summary="这是一轮通过脚本写入的测试对话")

    print(f"已写入测试对话：{cid}")

if __name__ == "__main__":
    main()
