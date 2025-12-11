import json
import re
import sqlite3
import csv
import socket
import subprocess
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import LOGS_DB_PATH, VANNA_DATA_DIR
from app.config import PROJECT_ROOT
from app.utils.html import html_escape
from app.services.summary import simplify_sse_message


def extract_sql_from_message(content: str) -> str | None:
    """从消息内容中提取 SQL 查询"""
    if not content:
        return None
    
    # 尝试匹配 SQL 代码块
    sql_patterns = [
        r"```sql\s*(.*?)```",
        r"```\s*(SELECT.*?);?\s*```",
        r"(SELECT[\s\S]{10,}?);",
        # 匹配没有代码块的 SELECT 语句（至少包含 FROM）
        r"(SELECT\s+[\s\S]{10,}?FROM[\s\S]{5,}?)(?:;|$|\n)",
    ]
    for pattern in sql_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            sql = match.group(1).strip()
            # 清理 SQL：移除可能的代码块标记
            sql = re.sub(r'^```sql\s*', '', sql, flags=re.IGNORECASE)
            sql = re.sub(r'```\s*$', '', sql, flags=re.IGNORECASE)
            sql = sql.strip()
            if sql.upper().startswith("SELECT") and len(sql) > 20:
                return sql
    return None


def parse_reasoning_steps(content: str) -> list[dict]:
    """解析 AI 推理步骤"""
    steps = []
    
    # 尝试从 SSE 消息中提取推理信息
    if content.lstrip().startswith("data:"):
        simp = simplify_sse_message(content)
        content = simp["display_text"]
    
    # 查找步骤标记
    step_patterns = [
        r"(?:步骤|Step)\s*(\d+)[:：]\s*(.*?)(?=(?:步骤|Step)\s*\d+|$)",
        r"(\d+)\.\s*(.*?)(?=\d+\.|$)",
    ]
    
    for pattern in step_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)
        for match in matches:
            step_num = match.group(1)
            step_text = match.group(2).strip()
            if step_text:
                steps.append({
                    "number": int(step_num),
                    "text": step_text,
                })
    
    # 如果没有找到步骤，尝试从工具调用中推断
    if not steps:
        if "RunSqlTool" in content or "SQL" in content:
            sql = extract_sql_from_message(content)
            if sql:
                steps = [
                    {"number": 1, "text": "理解用户需求"},
                    {"number": 2, "text": "生成 SQL 查询"},
                    {"number": 3, "text": "执行查询并获取数据"},
                    {"number": 4, "text": "生成可视化图表"},
                ]
    
    return steps


def create_chat_router() -> APIRouter:
    router = APIRouter()

    @router.get("/favicon.ico")
    async def favicon():
        """返回空 favicon 避免 404 错误"""
        from fastapi.responses import Response
        return Response(content=b"", media_type="image/x-icon")

    @router.get("/classic", response_class=HTMLResponse)
    async def chat_interface():
        """经典版数据 Agent 聊天界面"""
        
        # 获取最近的对话列表
        recent_conversations = []
        if LOGS_DB_PATH.exists():
            conn = sqlite3.connect(str(LOGS_DB_PATH))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            # 检查是否有 deleted 列，如果没有则添加
            try:
                cur.execute("ALTER TABLE conversation ADD COLUMN deleted INTEGER DEFAULT 0")
                conn.commit()
            except sqlite3.OperationalError:
                # 列已存在，忽略
                pass
            
            rows = cur.execute(
                """
                SELECT id, user_id, started_at, summary
                FROM conversation
                WHERE deleted = 0 OR deleted IS NULL
                ORDER BY started_at DESC
                LIMIT 10
                """
            ).fetchall()
            
            from datetime import datetime
            for r in rows:
                # 获取第一条用户消息作为标题
                first_user_msg = cur.execute(
                    """
                    SELECT content
                    FROM conversation_message
                    WHERE conversation_id = ? AND role = 'user'
                    ORDER BY created_at
                    LIMIT 1
                    """,
                    (r["id"],),
                ).fetchone()
                
                # 使用用户问题作为标题，如果没有则使用摘要
                title = "（无标题）"
                if first_user_msg and first_user_msg["content"]:
                    title = first_user_msg["content"].strip()
                    # 如果标题过长，截断并添加省略号
                    if len(title) > 50:
                        title = title[:47] + "..."
                elif r["summary"]:
                    title = r["summary"].strip()
                    if len(title) > 50:
                        title = title[:47] + "..."
                
                # 格式化日期：将 ISO 格式转换为更简洁的显示格式
                try:
                    dt = datetime.fromisoformat(r["started_at"].replace('T', ' ').split('.')[0])
                    now = datetime.now()
                    diff = now - dt
                    
                    if diff.days == 0:
                        # 今天：显示时间
                        time_str = dt.strftime("%H:%M")
                    elif diff.days == 1:
                        # 昨天
                        time_str = "昨天 " + dt.strftime("%H:%M")
                    elif diff.days < 7:
                        # 一周内：显示星期
                        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                        time_str = weekdays[dt.weekday()] + " " + dt.strftime("%H:%M")
                    elif diff.days < 365:
                        # 一年内：显示月日
                        time_str = dt.strftime("%m-%d %H:%M")
                    else:
                        # 更早：显示年月日
                        time_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    # 如果解析失败，使用原始值
                    time_str = r["started_at"]
                
                recent_conversations.append({
                    "id": r["id"],
                    "summary": title,
                    "time": time_str,
                })
            
            conn.close()

        html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Data Agent - 智能数据分析助手</title>
    <style>
        :root {
            --color-bg: #f8fafc;
            --color-surface: #ffffff;
            --color-border: #e2e8f0;
            --color-text: #1e293b;
            --color-text-muted: #64748b;
            --color-accent: #3b82f6;
            --color-accent-hover: #2563eb;
            --color-success: #10b981;
            --color-error: #ef4444;
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            --radius: 8px;
            --radius-lg: 12px;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--color-bg);
            color: var(--color-text);
            line-height: 1.6;
        }

        .app-container {
            display: flex;
            height: 100vh;
            overflow: hidden;
        }

        /* 侧边栏 */
        .sidebar {
            width: 280px;
            background: var(--color-surface);
            border-right: 1px solid var(--color-border);
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }

        .sidebar-header {
            padding: 20px;
            border-bottom: 1px solid var(--color-border);
        }

        .sidebar-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 4px;
        }

        .sidebar-subtitle {
            font-size: 12px;
            color: var(--color-text-muted);
        }

        .sidebar-section {
            padding: 16px;
        }

        .sidebar-section-title {
            font-size: 12px;
            font-weight: 600;
            color: var(--color-text-muted);
            text-transform: uppercase;
            margin-bottom: 12px;
        }

        .conversation-item {
            padding: 10px 12px;
            border-radius: var(--radius);
            margin-bottom: 4px;
            transition: background 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
            position: relative;
        }

        .conversation-item:hover {
            background: var(--color-bg);
        }

        .conversation-item.active {
            background: #eff6ff;
            border-left: 3px solid var(--color-accent);
        }

        .conversation-delete-btn {
            width: 24px;
            height: 24px;
            border: none;
            background: transparent;
            color: var(--color-text-muted);
            font-size: 18px;
            line-height: 1;
            cursor: pointer;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: all 0.2s;
            padding: 0;
            flex-shrink: 0;
            z-index: 10;
        }

        .conversation-item:hover .conversation-delete-btn {
            opacity: 1;
            background: rgba(239, 68, 68, 0.1);
        }
        
        .conversation-delete-btn:hover {
            background: rgba(239, 68, 68, 0.2) !important;
            color: var(--color-error) !important;
        }

        .conversation-summary {
            font-size: 13px;
            color: var(--color-text);
            margin-bottom: 4px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .conversation-time {
            font-size: 11px;
            color: var(--color-text-muted);
        }

        /* 主内容区 */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .header {
            padding: 16px 24px;
            background: var(--color-surface);
            border-bottom: 1px solid var(--color-border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .header-title {
            font-size: 20px;
            font-weight: 600;
        }

        .header-tagline {
            font-size: 13px;
            color: var(--color-text-muted);
            margin-left: 12px;
        }

        .new-chat-btn {
            padding: 10px 20px;
            background: linear-gradient(135deg, var(--color-accent) 0%, var(--color-accent-hover) 100%);
            color: white;
            border: none;
            border-radius: var(--radius-lg);
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: var(--shadow-sm);
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .new-chat-btn::before {
            content: '💬';
            font-size: 16px;
        }

        .new-chat-btn:hover {
            background: linear-gradient(135deg, var(--color-accent-hover) 0%, var(--color-accent) 100%);
            box-shadow: var(--shadow-md);
            transform: translateY(-1px);
        }

        .new-chat-btn:active {
            transform: translateY(0);
            box-shadow: var(--shadow-sm);
        }

        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .example-questions {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }

        .example-card {
            padding: 16px;
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: var(--shadow-sm);
        }

        .example-card:hover {
            border-color: var(--color-accent);
            box-shadow: var(--shadow-md);
            transform: translateY(-2px);
        }

        .example-text {
            font-size: 14px;
            color: var(--color-text);
        }

        /* 消息气泡 */
        .message {
            display: flex;
            gap: 12px;
            max-width: 85%;
        }

        .message.user {
            align-self: flex-end;
            margin-left: auto;
        }

        .message-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 14px;
            flex-shrink: 0;
        }

        .message.user .message-avatar {
            background: var(--color-accent);
            color: white;
        }

        .message.assistant .message-avatar {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .message-content {
            flex: 1;
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            padding: 16px;
            box-shadow: var(--shadow-sm);
        }

        .message.user .message-content {
            background: #eff6ff;
            border-color: #bfdbfe;
        }

        .message-text {
            font-size: 14px;
            line-height: 1.6;
            white-space: pre-wrap;
            word-break: break-word;
        }

        /* 推理步骤面板 */
        .reasoning-panel {
            margin-top: 12px;
            padding: 12px;
            background: #f8fafc;
            border-radius: var(--radius);
            border-left: 3px solid var(--color-accent);
        }

        .reasoning-title {
            font-size: 12px;
            font-weight: 600;
            color: var(--color-text-muted);
            margin-bottom: 8px;
            text-transform: uppercase;
        }

        .reasoning-steps {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .reasoning-step {
            display: flex;
            gap: 8px;
            font-size: 13px;
        }

        .step-number {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: var(--color-accent);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            font-weight: 600;
            flex-shrink: 0;
        }

        .step-text {
            flex: 1;
            color: var(--color-text);
        }

        /* SQL 代码块 */
        .sql-block {
            margin-top: 12px;
            background: #1e293b;
            border-radius: var(--radius);
            overflow: hidden;
            position: relative;
        }

        .sql-block-header {
            padding: 8px 12px;
            background: #0f172a;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
        }

        .sql-block-title {
            font-size: 11px;
            font-weight: 600;
            color: #94a3b8;
            text-transform: uppercase;
        }

        .sql-copy-btn {
            padding: 4px 8px;
            font-size: 11px;
            background: transparent;
            border: 1px solid #475569;
            color: #cbd5e1;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .sql-copy-btn:hover {
            background: #334155;
            border-color: #64748b;
            color: #f1f5f9;
        }

        .sql-code {
            padding: 12px;
            font-family: "Monaco", "Menlo", "Consolas", monospace;
            font-size: 12px;
            color: #e2e8f0;
            line-height: 1.5;
            overflow-x: auto;
        }

        /* 结果卡片 */
        .result-card {
            margin-top: 12px;
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            overflow: hidden;
        }

        .result-header {
            padding: 12px 16px;
            background: #f8fafc;
            border-bottom: 1px solid var(--color-border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .result-title {
            font-size: 13px;
            font-weight: 600;
        }

        .result-actions {
            display: flex;
            gap: 8px;
        }

        .action-btn {
            padding: 4px 8px;
            font-size: 12px;
            border: 1px solid var(--color-border);
            background: var(--color-surface);
            border-radius: var(--radius);
            cursor: pointer;
            transition: all 0.2s;
        }

        .action-btn:hover {
            background: var(--color-bg);
            border-color: var(--color-accent);
        }

        .result-body {
            padding: 16px;
        }

        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }

        .data-table th,
        .data-table td {
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid var(--color-border);
        }

        .data-table th {
            background: #f8fafc;
            font-weight: 600;
            color: var(--color-text-muted);
        }

        .data-table tr:hover {
            background: #f8fafc;
        }

        .chart-toggle {
            margin-top: 12px;
            padding: 8px 16px;
            background: var(--color-accent);
            color: white;
            border: none;
            border-radius: var(--radius);
            cursor: pointer;
            font-size: 13px;
            transition: background 0.2s;
        }

        .chart-toggle:hover {
            background: var(--color-accent-hover);
        }

        /* 输入区 */
        .input-area {
            padding: 16px 24px;
            background: var(--color-surface);
            border-top: 1px solid var(--color-border);
        }

        .input-container {
            display: flex;
            gap: 12px;
            align-items: flex-end;
        }

        .input-wrapper {
            flex: 1;
            position: relative;
        }

        .chat-input {
            width: 100%;
            padding: 12px 16px;
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            font-size: 14px;
            font-family: inherit;
            resize: none;
            min-height: 44px;
            max-height: 120px;
        }

        .chat-input:focus {
            outline: none;
            border-color: var(--color-accent);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }

        .send-btn {
            padding: 12px 24px;
            background: var(--color-accent);
            color: white;
            border: none;
            border-radius: var(--radius-lg);
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }

        .send-btn:hover {
            background: var(--color-accent-hover);
        }

        .send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* 工具标签 */
        .tool-badge {
            display: inline-block;
            padding: 2px 8px;
            background: #fef3c7;
            color: #92400e;
            border-radius: 12px;
            font-size: 11px;
            margin-right: 6px;
        }

        /* Toast 通知 */
        .toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            padding: 12px 20px;
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-lg);
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        /* 图表容器 */
        .chart-container {
            margin-top: 16px;
            padding: 16px;
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius);
            display: none;
        }

        .chart-container.active {
            display: block;
        }

        /* 操作按钮样式 */
        .action-btn.primary {
            background: var(--color-accent);
            color: white;
            border-color: var(--color-accent);
        }

        .action-btn.primary:hover {
            background: var(--color-accent-hover);
        }

        .action-btn.like.active {
            background: var(--color-success);
            color: white;
            border-color: var(--color-success);
        }

        .action-btn.dislike.active {
            background: var(--color-error);
            color: white;
            border-color: var(--color-error);
        }

        /* 服务状态按钮 */
        .server-status-btn {
            position: fixed;
            bottom: 20px;
            left: 20px;
            padding: 10px 16px;
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            font-size: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: var(--shadow-md);
            z-index: 100;
            transition: all 0.2s;
        }

        .server-status-btn:hover {
            box-shadow: var(--shadow-lg);
            transform: translateY(-2px);
        }

        .server-status-btn.running {
            background: #f0fdf4;
            border-color: var(--color-success);
            color: var(--color-success);
        }

        .server-status-btn.stopped {
            background: #fef2f2;
            border-color: var(--color-error);
            color: var(--color-error);
        }

        .server-status-btn.starting {
            background: #fef3c7;
            border-color: #f59e0b;
            color: #92400e;
        }

        .server-status-btn.running::after {
            content: " | 点击停止";
            font-size: 10px;
            opacity: 0.7;
            margin-left: 4px;
        }

        .server-status-btn.running::after {
            content: " | 点击停止";
            font-size: 10px;
            opacity: 0.7;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }

        .status-dot.running {
            background: var(--color-success);
            animation: pulse 2s infinite;
        }

        .status-dot.stopped {
            background: var(--color-error);
        }

        .status-dot.starting {
            background: #f59e0b;
            animation: pulse 1s infinite;
        }

        @keyframes pulse {
            0%, 100% {
                opacity: 1;
            }
            50% {
                opacity: 0.5;
            }
        }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- 侧边栏 -->
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-title">Data Agent</div>
                <div class="sidebar-subtitle">智能数据分析助手</div>
            </div>
            <div class="sidebar-section">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div class="sidebar-section-title">最近对话</div>
                    <a href="/logs" style="font-size: 11px; color: var(--color-accent); text-decoration: none;">评测对话日志</a>
                </div>
                <div id="recent-conversations">
                    """ + "".join([
                        f"""
                        <div class="conversation-item" data-conv-id="{html_escape(c["id"])}">
                            <div style="flex: 1; cursor: pointer;" onclick='loadConversation({json.dumps(c["id"])})'>
                                <div class="conversation-summary">{html_escape(c["summary"])}</div>
                                <div class="conversation-time">{html_escape(c["time"])}</div>
                            </div>
                            <button class="conversation-delete-btn" data-conv-id="{html_escape(c["id"])}" title="删除">×</button>
                        </div>
                        """
                        for c in recent_conversations
                    ]) + """
                </div>
            </div>
        </div>

        <!-- 主内容区 -->
        <div class="main-content">
            <div class="header">
                <div></div>
                <button class="new-chat-btn" id="new-chat-btn" onclick="startNewConversation()" title="开始新会话" style="display: none;">新会话</button>
            </div>

            <div class="chat-container" id="chat-container">
                <div class="example-questions" id="example-questions">
                    <div class="example-card" data-question="最近7天按省份统计访问量" onclick="askQuestion(this.dataset.question)">
                        <div class="example-text">最近7天按省份统计访问量</div>
                    </div>
                    <div class="example-card" data-question="显示各渠道的转化率对比" onclick="askQuestion(this.dataset.question)">
                        <div class="example-text">显示各渠道的转化率对比</div>
                    </div>
                    <div class="example-card" data-question="Top 10 访问量最高的页面" onclick="askQuestion(this.dataset.question)">
                        <div class="example-text">Top 10 访问量最高的页面</div>
                    </div>
                    <div class="example-card" data-question="最近一个月的访问趋势" onclick="askQuestion(this.dataset.question)">
                        <div class="example-text">最近一个月的访问趋势</div>
                    </div>
                </div>
            </div>

            <div class="input-area">
                <div class="input-container">
                    <div class="input-wrapper">
                        <textarea
                            id="chat-input"
                            class="chat-input"
                            placeholder="输入你的数据问题..."
                            rows="1"
                        ></textarea>
                    </div>
                    <button class="send-btn" id="send-btn" onclick="sendMessage()">发送</button>
                </div>
            </div>
        </div>

        <!-- 服务状态按钮 -->
        <div class="server-status-btn" id="server-status-btn">
            <span class="status-dot" id="status-dot"></span>
            <span id="status-text">检查服务状态...</span>
        </div>
    </div>

    <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
    <script>
        // 立即将函数暴露到全局作用域，避免 HTML 中的 onclick 调用时函数未定义
        // 先声明函数，然后立即赋值到 window
        
        // 删除会话函数（提前定义，确保在 HTML 中可用）
        function deleteConversation(convId) {
            if (!confirm('确定要删除这个会话吗？日志将保留，但会话将从列表中移除。')) {
                return;
            }
            
            // 显示加载状态
            let item = document.querySelector(`[data-conv-id='${convId}']`);
            if (!item) {
                const allItems = document.querySelectorAll('.conversation-item');
                for (let el of allItems) {
                    if (el.getAttribute('data-conv-id') === convId) {
                        item = el;
                        break;
                    }
                }
            }
            if (item) {
                item.style.opacity = '0.5';
                item.style.pointerEvents = 'none';
            }
            
            const deleteUrl = `/api/chat/conversation/${encodeURIComponent(convId)}`;
            
            fetch(deleteUrl, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                },
            })
            .then(res => {
                if (!res.ok) {
                    return res.text().then(text => {
                        console.error('Delete API error response:', text);
                        throw new Error(`HTTP ${res.status}: ${text}`);
                    });
                }
                return res.json();
            })
            .then(data => {
                // 检查返回的数据格式
                if (data && (data.success === true || data.success === 'true')) {
                    // 使用 showToast 函数（如果已定义），否则使用 alert
                    if (typeof showToast === 'function') {
                        showToast('会话已删除');
                    } else {
                        alert('会话已删除');
                    }
                    // 直接刷新页面，避免元素查找问题
                    setTimeout(() => {
                        window.location.reload();
                    }, 300);
                } else {
                    const errorMsg = data?.message || data?.error || '删除失败';
                    if (typeof showToast === 'function') {
                        showToast(errorMsg);
                    } else {
                        alert(errorMsg);
                    }
                }
            })
            .catch(err => {
                console.error('Delete conversation error:', err);
                console.error('Error details:', err.message, err.stack);
                const errorMsg = '删除失败: ' + err.message;
                if (typeof showToast === 'function') {
                    showToast(errorMsg);
                } else {
                    alert(errorMsg);
                }
                // 恢复元素状态
                let item = document.querySelector(`[data-conv-id='${convId}']`);
                if (!item) {
                    const allItems = document.querySelectorAll('.conversation-item');
                    for (let el of allItems) {
                        if (el.getAttribute('data-conv-id') === convId) {
                            item = el;
                            break;
                        }
                    }
                }
                if (item) {
                    item.style.opacity = '1';
                    item.style.pointerEvents = 'auto';
                }
            });
        }
        
        function askQuestion(text) {
            // 开始新会话
            currentConversationId = null;
            messageHistory = [];
            
            // 清空当前聊天内容
            const chatContainer = document.getElementById('chat-container');
            if (chatContainer) {
                chatContainer.innerHTML = '';
            }
            
            // 显示示例问题
            const exampleQuestions = document.getElementById('example-questions');
            if (exampleQuestions) {
                exampleQuestions.style.display = 'grid';
            }
            
            const chatInput = document.getElementById('chat-input');
            if (chatInput) {
                chatInput.value = text;
                sendMessage();
            }
        }
        
        function sendMessage() {
            const chatInput = document.getElementById('chat-input');
            const text = chatInput ? chatInput.value.trim() : '';
            if (!text) return;

            const exampleQuestions = document.getElementById('example-questions');
            if (exampleQuestions) {
                exampleQuestions.style.display = 'none';
            }

            // 添加用户消息
            addUserMessage(text);
            chatInput.value = '';
            chatInput.style.height = 'auto';

            // 更新新会话按钮显示状态（发送消息后应该显示按钮）
            updateNewChatButtonVisibility();

            // 发送到后端
            sendToBackend(text);
        }
        
        // 立即暴露到全局作用域（确保在 HTML 渲染前可用）
        window.askQuestion = askQuestion;
        window.sendMessage = sendMessage;
        window.deleteConversation = deleteConversation;
        
        // 使用事件委托处理删除按钮点击（避免 onclick 属性中的引号问题）
        function bindDeleteButtons() {
            document.querySelectorAll('.conversation-delete-btn').forEach(btn => {
                // 检查是否已经绑定过事件
                if (!btn.hasAttribute('data-bound')) {
                    btn.setAttribute('data-bound', 'true');
                    btn.addEventListener('click', function(e) {
                        e.stopPropagation();
                        e.preventDefault();
                        const convId = this.getAttribute('data-conv-id');
                        if (convId && typeof deleteConversation === 'function') {
                            deleteConversation(convId);
                        }
                        return false;
                    });
                }
            });
        }
        
        // 使用事件委托：在父元素上监听点击事件（更可靠）
        // 使用 document 作为委托目标，这样即使 innerHTML 更新也不会丢失事件监听器
        document.addEventListener('click', function(e) {
            // 检查是否点击了删除按钮或其子元素
            // 先检查目标元素本身，再检查父元素
            let deleteBtn = null;
            if (e.target && e.target.classList && e.target.classList.contains('conversation-delete-btn')) {
                deleteBtn = e.target;
            } else if (e.target && e.target.closest) {
                deleteBtn = e.target.closest('.conversation-delete-btn');
            }
            
            if (deleteBtn) {
                e.stopPropagation();
                e.preventDefault();
                const convId = deleteBtn.getAttribute('data-conv-id');
                console.log('Delete button clicked, convId:', convId, 'button:', deleteBtn);
                if (convId) {
                    if (typeof deleteConversation === 'function') {
                        console.log('Calling deleteConversation function');
                        deleteConversation(convId);
                    } else {
                        console.error('deleteConversation function not found, type:', typeof deleteConversation);
                        alert('删除功能未初始化，请刷新页面重试');
                    }
                } else {
                    console.error('No convId found on delete button');
                }
                return false;
            }
        });
        
        // 页面加载完成后也绑定删除按钮事件（作为备用）
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', bindDeleteButtons);
        } else {
            // DOM 已经加载完成，立即绑定
            setTimeout(bindDeleteButtons, 100);
        }

        function addUserMessage(text) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message user';
            messageDiv.innerHTML = '<div class="message-avatar">U</div>' +
                '<div class="message-content">' +
                '<div class="message-text">' + escapeHtml(text) + '</div>' +
                '</div>';
            chatContainer.appendChild(messageDiv);
            scrollToBottom();
        }

        function addAssistantMessage(content, reasoningSteps = [], sql = null, tools = [], tableData = null, chartData = null) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message assistant';
            const messageId = 'msg-' + Date.now();
            
            let reasoningHtml = '';
            if (reasoningSteps.length > 0) {
                const stepsHtml = reasoningSteps.map(step => {
                    return '<div class="reasoning-step">' +
                        '<div class="step-number">' + escapeHtml(String(step.number)) + '</div>' +
                        '<div class="step-text">' + escapeHtml(step.text) + '</div>' +
                        '</div>';
                }).join('');
                reasoningHtml = '<div class="reasoning-panel">' +
                    '<div class="reasoning-title">AI 推理过程</div>' +
                    '<div class="reasoning-steps">' + stepsHtml + '</div>' +
                    '</div>';
            }

            let sqlHtml = '';
            if (sql && sql.trim()) {
                sqlHtml = '<div class="sql-block">' +
                    '<div class="sql-block-header">' +
                        '<span class="sql-block-title">SQL 查询</span>' +
                        '<button class="sql-copy-btn" onclick=\\"copySql(\\'\\' + messageId + \\'\\')\\" title=\\"复制 SQL\\">📋 复制</button>' +
                    '</div>' +
                    '<div class="sql-code" id="sql-' + messageId + '">' + escapeHtml(sql) + '</div>' +
                    '</div>';
            }

            let toolsHtml = '';
            if (tools.length > 0) {
                toolsHtml = tools.map(t => '<span class="tool-badge">' + escapeHtml(t) + '</span>').join('');
            }

            // 表格 HTML
            let tableHtml = '';
            if (tableData && tableData.length > 0) {
                const headers = Object.keys(tableData[0]);
                const headerRow = headers.map(h => '<th>' + escapeHtml(h) + '</th>').join('');
                const bodyRows = tableData.map(row => {
                    const cells = headers.map(h => '<td>' + escapeHtml(String(row[h] ?? '')) + '</td>').join('');
                    return '<tr>' + cells + '</tr>';
                }).join('');
                const chartSection = chartData ? 
                    '<button class="chart-toggle" onclick=\\"toggleChart(\\'\\' + messageId + \\'\\')\\" >📊 查看图表</button>' +
                    '<div class="chart-container" id="chart-' + messageId + '"></div>' : '';
                
                tableHtml = 
                    '<div class="result-card" id="result-' + messageId + '">' +
                        '<div class="result-header">' +
                            '<div class="result-title">查询结果</div>' +
                            '<div class="result-actions">' +
                                '<button class="action-btn" onclick=\\"exportData(\\'\\' + messageId + \\'\\')\\" title=\\"导出\\">📥 导出</button>' +
                                '<button class="action-btn" onclick=\\"copyData(\\'\\' + messageId + \\'\\')\\" title=\\"复制\\">📋 复制</button>' +
                                '<button class="action-btn like" id="like-' + messageId + '" onclick=\\"toggleLike(\\'\\' + messageId + \\'\\')\\" title=\\"点赞\\">👍</button>' +
                                '<button class="action-btn dislike" id="dislike-' + messageId + '" onclick=\\"toggleDislike(\\'\\' + messageId + \\'\\')\\" title=\\"点踩\\">👎</button>' +
                                '<button class="action-btn" onclick=\\"askHuman(\\'\\' + messageId + \\'\\')\\" title=\\"询问人类\\">💬 询问人类</button>' +
                            '</div>' +
                        '</div>' +
                        '<div class="result-body">' +
                            '<table class="data-table">' +
                                '<thead><tr>' + headerRow + '</tr></thead>' +
                                '<tbody>' + bodyRows + '</tbody>' +
                            '</table>' +
                            chartSection +
                        '</div>' +
                    '</div>';
            }

            const contentHtml = '<div class="message-avatar">AI</div>' +
                '<div class="message-content">' +
                (toolsHtml ? '<div style="margin-bottom: 8px;">' + toolsHtml + '</div>' : '') +
                '<div class="message-text">' + escapeHtml(content) + '</div>' +
                reasoningHtml +
                sqlHtml +
                tableHtml +
                '</div>';
            messageDiv.innerHTML = contentHtml;
            chatContainer.appendChild(messageDiv);
            
            // 如果有图表数据，初始化图表
            if (chartData && tableData) {
                setTimeout(() => {
                    renderChart(messageId, chartData, tableData);
                }, 100);
            }
            
            scrollToBottom();
        }

        let currentConversationId = null;
        let messageHistory = [];

        function sendToBackend(text) {
            messageHistory.push({ role: "user", content: text });
            
            // 创建或使用现有会话 ID
            const isNewConversation = !currentConversationId;
            if (!currentConversationId) {
                currentConversationId = Date.now() + '-' + Math.random().toString(36).substr(2, 8);
                // 如果是新会话，立即刷新左侧列表（延迟一点以确保数据库已保存用户消息）
                if (isNewConversation) {
                    setTimeout(() => {
                        refreshConversationList();
                    }, 300);
                }
            }

            // 创建消息 ID
            const messageId = 'msg-' + Date.now();

            // 显示加载状态
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'message assistant';
            loadingDiv.id = 'loading-message';
            loadingDiv.innerHTML = '<div class="message-avatar">AI</div><div class="message-content"><div class="message-text">正在为您分析问题，请稍候...</div></div>';
            chatContainer.appendChild(loadingDiv);
            scrollToBottom();

            let assistantText = '';
            let seenTexts = new Set(); // 用于去重
            let lastText = ''; // 记录上一个文本，用于检测相邻重复
            let tools = new Set();
            let tableData = null;
            let chartData = null;
            let extractedSql = null; // 从SSE流中提取的SQL
            
            // 文本相似度检测函数（简单版本）
            function isSimilarText(text1, text2) {
                if (!text1 || !text2) return false;
                // 如果两个文本完全相同，返回 true
                if (text1 === text2) return true;
                // 如果文本长度差异很大，不相似
                if (Math.abs(text1.length - text2.length) > text1.length * 0.3) return false;
                // 计算相似度（简单版本：计算共同字符比例）
                const longer = text1.length > text2.length ? text1 : text2;
                const shorter = text1.length > text2.length ? text2 : text1;
                let matches = 0;
                for (let i = 0; i < shorter.length; i++) {
                    if (longer.includes(shorter[i])) matches++;
                }
                const similarity = matches / longer.length;
                // 如果相似度超过 80%，认为是相似的
                return similarity > 0.8;
            }

            // 使用 fetch 读取 SSE 流
            // Vanna API 需要 message 字段（字符串），而不是 messages 数组
            const lastUserMessage = messageHistory.filter(m => m.role === 'user').pop();
            const userMessageText = lastUserMessage ? lastUserMessage.content : text;
            
            const requestBody = {
                conversation_id: currentConversationId,
                message: userMessageText,
            };
            
            console.log('Sending request:', requestBody);
            
            fetch('/api/vanna/v2/chat_sse', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody),
            })
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        console.error('API Error:', response.status, text);
                        throw new Error(`请求失败 (${response.status}): ${text.substring(0, 100)}`);
                    });
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                function readStream() {
                    reader.read().then(({ done, value }) => {
                        if (done) {
                            // 确保只渲染一次消息
                            const loadingMsg = document.getElementById('loading-message');
                            if (loadingMsg) loadingMsg.remove();
                            
                            // 清理和简化文本
                            let cleanedText = assistantText.trim();
                            
                            // 在清理文本之前，先尝试从原始 assistantText 中提取 SQL（保留换行和格式）
                            // 优先使用从SSE流中提取的SQL，如果没有则从原始文本中提取
                            let sql = extractedSql;
                            if (!sql && assistantText) {
                                // 从原始 assistantText 中提取（可能包含换行和代码块）
                                sql = extractSQLFromText(assistantText);
                            }
                            if (!sql && assistantText) {
                                // 如果原始文本中没有找到，尝试从清理后的文本中提取
                                // 移除重复的空格和换行
                                cleanedText = cleanedText.replace(/\\s+/g, ' ').trim();
                                sql = extractSQLFromText(cleanedText);
                            } else {
                                // 如果已经找到 SQL，仍然清理文本用于显示
                                cleanedText = cleanedText.replace(/\\s+/g, ' ').trim();
                            }
                            
                            // SQL 提取完成（移除调试日志以减少控制台输出）
                            
                            // 如果文本为空，使用默认提示
                            if (!cleanedText) {
                                cleanedText = '正在处理您的请求...';
                            }
                            
                            const reasoningSteps = parseReasoningFromText(cleanedText);
                            
                            // 如果还没有表格数据，尝试从 vanna_data 目录加载最新的查询结果
                            if (!tableData && Array.from(tools).includes('RunSqlTool')) {
                                loadLatestQueryResult().then(data => {
                                    if (data) {
                                        tableData = data;
                                    }
                                    addAssistantMessage(cleanedText, reasoningSteps, sql, Array.from(tools), tableData, chartData);
                                    messageHistory.push({ role: 'assistant', content: cleanedText });
                                    // 延迟刷新左侧会话列表，确保数据库已保存
                                    setTimeout(() => {
                                        refreshConversationList();
                                    }, 500);
                                }).catch(() => {
                                    // 如果加载失败，仍然显示消息
                                    addAssistantMessage(cleanedText, reasoningSteps, sql, Array.from(tools), tableData, chartData);
                                    messageHistory.push({ role: 'assistant', content: cleanedText });
                                    // 延迟刷新左侧会话列表，确保数据库已保存
                                    setTimeout(() => {
                                        refreshConversationList();
                                    }, 500);
                                });
                            } else {
                                addAssistantMessage(cleanedText, reasoningSteps, sql, Array.from(tools), tableData, chartData);
                                messageHistory.push({ role: 'assistant', content: cleanedText });
                                // 延迟刷新左侧会话列表，确保数据库已保存
                                setTimeout(() => {
                                    refreshConversationList();
                                }, 500);
                            }
                            return;
                        }

                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\\n');
                        buffer = lines.pop() || '';

                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                const data = line.slice(6).trim();
                                if (data === '[DONE]' || !data) continue;

                                try {
                                    const json = JSON.parse(data);
                                    
                                    // Vanna 返回格式: {rich: {...}, simple: {...}}
                                    // 优先使用 simple.text，如果没有则从 rich.data.content 提取
                                    let text = null;
                                    let type = null;
                                    
                                    if (json.simple && json.simple.text) {
                                        text = json.simple.text;
                                        type = json.simple.type || json.rich?.type;
                                    } else if (json.rich) {
                                        type = json.rich.type;
                                        if (json.rich.data) {
                                            if (json.rich.data.content) {
                                                text = json.rich.data.content;
                                            } else if (json.rich.data.message) {
                                                text = json.rich.data.message;
                                            } else if (typeof json.rich.data === 'string') {
                                                text = json.rich.data;
                                            }
                                        }
                                    }
                                    
                                    // 尝试从文本中提取 SQL（在过滤之前，从原始文本中提取）
                                    if (text && !extractedSql) {
                                        // 先尝试从原始文本中提取（可能包含换行和代码块）
                                        const sqlFromRaw = extractSQLFromText(text);
                                        if (sqlFromRaw) {
                                            extractedSql = sqlFromRaw;
                                        }
                                    }
                                    
                                    // 如果还没找到，尝试从整个原始行中提取（可能包含完整的 SQL 代码块）
                                    if (!extractedSql && line.includes('SELECT')) {
                                        const sqlFromLine = extractSQLFromText(line);
                                        if (sqlFromLine) {
                                            extractedSql = sqlFromLine;
                                        }
                                    }
                                    
                                    // 过滤掉状态更新类型（这些不应该显示为文本）
                                    if (type && ['status_bar_update', 'task_tracker_update', 'status_card'].includes(type)) {
                                        // 这些类型不添加到文本中
                                        continue;
                                    }
                                    
                                    // 再次尝试从文本中提取 SQL（如果之前没找到）
                                    if (text && !extractedSql) {
                                        const sqlPatterns = [
                                            /```sql\\s*([\\s\\S]*?)```/i,
                                            /```\\s*(SELECT[\\s\\S]*?);?\\s*```/i,
                                            /(SELECT[\\s\\S]{20,}?);/i,
                                            // 匹配没有代码块的 SELECT 语句（至少包含 FROM）
                                            /(SELECT\\s+[\\s\\S]{{20,}}?FROM[\\s\\S]{{5,}}?)(?:;|$|\\n)/i,
                                        ];
                                        for (const pattern of sqlPatterns) {
                                            const match = text.match(pattern);
                                            if (match && match[1]) {
                                                let sql = match[1].trim();
                                                // 清理 SQL：移除可能的代码块标记
                                                sql = sql.replace(/^```sql\\s*/i, '').replace(/```\\s*$/i, '').trim();
                                                if (sql.toUpperCase().startsWith('SELECT') && sql.length > 20) {
                                                    extractedSql = sql;
                                                    break;
                                                }
                                            }
                                        }
                                    }
                                    
                                    // 如果是文本类型，添加到响应中（过滤掉数据和技术信息）
                                    if (text && type !== 'status_bar_update' && type !== 'task_tracker_update' && type !== 'status_card') {
                                        const textTrimmed = text.trim();
                                        
                                        // 跳过空文本
                                        if (!textTrimmed) {
                                            continue;
                                        }
                                        
                                        // 去重：跳过已见过的文本（精确匹配）
                                        if (seenTexts.has(textTrimmed)) {
                                            continue;
                                        }
                                        
                                        // 检测相邻重复：如果与上一个文本相似，跳过
                                        if (lastText && isSimilarText(textTrimmed, lastText)) {
                                            continue;
                                        }
                                        
                                        // 检测全局相似：检查是否与已添加的文本相似
                                        let isDuplicate = false;
                                        for (const seenText of seenTexts) {
                                            if (isSimilarText(textTrimmed, seenText)) {
                                                isDuplicate = true;
                                                break;
                                            }
                                        }
                                        if (isDuplicate) {
                                            continue;
                                        }
                                        
                                        // 过滤掉 CSV 数据行和技术性信息
                                        const shouldExclude = 
                                            // CSV 表头或数据行（包含多个逗号且主要是数据）
                                            (textTrimmed.includes(',') && textTrimmed.split(',').length >= 3 && /^[\\d\\s,\\-:\\.\\$]+$/.test(textTrimmed)) ||
                                            // 技术性提示信息
                                            textTrimmed.includes('Results saved to file:') ||
                                            textTrimmed.includes('**IMPORTANT: FOR VISUALIZE_DATA') ||
                                            textTrimmed.includes('Results truncated to') ||
                                            textTrimmed.includes('FOR LARGE RESULTS YOU DO NOT NEED TO SUMMARIZE') ||
                                            textTrimmed.includes('Tool completed successfully') ||
                                            textTrimmed.includes('Tool failed:') ||
                                            textTrimmed.includes('Error executing query:') ||
                                            textTrimmed.includes('Query executed successfully') ||
                                            textTrimmed.includes('Processing your request...') ||
                                            textTrimmed.includes('Analyzing query') ||
                                            textTrimmed.includes('Executing tools...') ||
                                            textTrimmed.includes('Created visualization from') ||
                                            textTrimmed.includes('Tool limit reached') ||
                                            // 纯数据行（只有数字、逗号、时间戳等）
                                            /^[\\d\\s,\\-:\\.]+$/.test(textTrimmed) ||
                                            // 过滤技术描述短句
                                            (textTrimmed.length < 100 && (
                                                /表\\s*[名]?\\s*[为是]/.test(textTrimmed) ||
                                                /字段\\s*[名为]/.test(textTrimmed) ||
                                                /列\\s*[名为]/.test(textTrimmed) ||
                                                /包含\s*\d+\s*[行列]/.test(textTrimmed) ||
                                                /结构\s*[如下]/.test(textTrimmed)
                                            ));
                                        
                                        if (!shouldExclude) {
                                            seenTexts.add(textTrimmed);
                                            lastText = textTrimmed;
                                            assistantText += textTrimmed + ' ';
                                            const loadingMsg = document.getElementById('loading-message');
                                            if (loadingMsg) {
                                                const msgText = assistantText.trim() || '正在为您分析问题...';
                                                const textEl = loadingMsg.querySelector('.message-text');
                                                if (textEl) {
                                                    textEl.textContent = msgText;
                                                }
                                            }
                                        }
                                    }
                                    
                                    // 处理工具调用（从 rich.data 中提取）
                                    if (json.rich && json.rich.data) {
                                        const data = json.rich.data;
                                        const richType = json.rich.type;
                                        
                                        // 提取工具名称（多种可能的位置）
                                        if (data.tool_name || data.name) {
                                            tools.add(data.tool_name || data.name);
                                        }
                                        
                                        // 从 dataframe 类型提取表格数据
                                        if (richType === 'dataframe') {
                                            tools.add('RunSqlTool');
                                            // 提取 dataframe 数据
                                            if (data.data && Array.isArray(data.data)) {
                                                // dataframe 的 data 可能是对象数组或二维数组
                                                if (data.data.length > 0) {
                                                    const firstRow = data.data[0];
                                                    if (typeof firstRow === 'object' && !Array.isArray(firstRow)) {
                                                        // 已经是对象数组，直接使用
                                                        tableData = data.data;
                                                    } else if (Array.isArray(firstRow)) {
                                                        // 是二维数组，需要转换
                                                        const columns = data.columns || [];
                                                        if (columns.length > 0) {
                                                            tableData = data.data.map(row => {
                                                                const obj = {};
                                                                columns.forEach((col, idx) => {
                                                                    obj[col] = row[idx] !== undefined ? row[idx] : '';
                                                                });
                                                                return obj;
                                                            });
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                        
                                        // 从 chart 类型推断工具（通常是 VisualizeDataTool 的结果）
                                        if (richType === 'chart') {
                                            tools.add('VisualizeDataTool');
                                            // 提取图表数据
                                            if (data.chart || data.data) {
                                                chartData = data.chart || data.data;
                                            }
                                        }
                                        
                                        // 从工具调用结果中提取 SQL（可能在 result 字段中）
                                        if (data.result && typeof data.result === 'string' && !extractedSql) {
                                            const sqlFromResult = extractSQLFromText(data.result);
                                            if (sqlFromResult) {
                                                extractedSql = sqlFromResult;
                                            }
                                        }
                                        
                                        if (data.result) {
                                            const parsed = parseToolResult(data.result, data.tool_name || data.name);
                                            if (parsed.table) tableData = parsed.table;
                                            if (parsed.chart) chartData = parsed.chart;
                                            
                                            // 如果结果是文件路径，尝试加载
                                            if (typeof data.result === 'string' && data.result.includes('query_results_')) {
                                                const currentMessageId = messageId; // 保存 messageId 到闭包
                                                loadQueryResultFromFile(data.result).then(resultData => {
                                                    if (resultData) {
                                                        tableData = resultData;
                                                        // 更新已显示的消息
                                                        updateMessageWithTable(currentMessageId, tableData);
                                                    }
                                                });
                                            }
                                        }
                                    }
                                } catch (e) {
                                    console.error('Parse error:', e, data);
                                }
                            }
                        }

                        readStream();
                    }).catch(err => {
                        console.error('Stream error:', err);
                        document.getElementById('loading-message')?.remove();
                        addAssistantMessage('读取响应时出错，请重试。', [], null, []);
                    });
                }

                readStream();
            })
            .catch(err => {
                console.error('Request error:', err);
                document.getElementById('loading-message')?.remove();
                const errorMsg = err.message || '网络错误，请检查连接后重试。';
                addAssistantMessage(errorMsg, null, null, [], null, null);
                showToast('请求失败: ' + errorMsg);
            });
        }

        function parseToolResult(result, toolName) {
            const parsed = { table: null, chart: null };
            
            try {
                if (typeof result === 'string') {
                    // 尝试解析 JSON
                    try {
                        result = JSON.parse(result);
                    } catch (e) {
                        // 不是 JSON，可能是 CSV 或其他格式
                        if (result.includes(',')) {
                            parsed.table = parseCSV(result);
                        }
                        return parsed;
                    }
                }
                
                if (Array.isArray(result)) {
                    parsed.table = result;
                } else if (result && typeof result === 'object') {
                    if (result.data && Array.isArray(result.data)) {
                        parsed.table = result.data;
                    } else if (result.rows) {
                        parsed.table = result.rows;
                    } else if (result.table) {
                        parsed.table = result.table;
                    }
                    
                    if (result.chart || result.visualization) {
                        parsed.chart = result.chart || result.visualization;
                    }
                }
            } catch (e) {
                console.error('Parse tool result error:', e);
            }
            
            return parsed;
        }

        function parseCSV(csvText) {
            const lines = csvText.trim().split('\\n');
            if (lines.length < 2) return null;
            
            const headers = lines[0].split(',').map(h => h.trim());
            const rows = [];
            
            for (let i = 1; i < lines.length; i++) {
                const values = lines[i].split(',').map(v => v.trim());
                const row = {};
                headers.forEach((h, idx) => {
                    row[h] = values[idx] || '';
                });
                rows.push(row);
            }
            
            return rows;
        }

        function extractTableFromResponse(text) {
            // 尝试从文本中提取表格数据
            // 这里可以扩展更复杂的解析逻辑
            return null;
        }

        async function loadQueryResultFromFile(filePath) {
            try {
                // 从文件路径中提取 hash
                const match = filePath.match(/([a-f0-9]+)\\/query_results_/);
                if (!match) return null;
                
                const hash = match[1];
                const response = await fetch(`/api/chat/query-result/${hash}`);
                if (response.ok) {
                    const data = await response.json();
                    return data.data;
                }
            } catch (e) {
                console.error('Load query result error:', e);
            }
            return null;
        }

        async function loadLatestQueryResult() {
            try {
                // 尝试从当前会话 ID 对应的目录加载
                if (currentConversationId) {
                    // 从会话 ID 中提取可能的 hash（如果格式匹配）
                    const parts = currentConversationId.split('-');
                    if (parts.length > 1) {
                        // 尝试多个可能的 hash 格式
                        const possibleHashes = [parts[1], parts[0].slice(-8)];
                        for (const hash of possibleHashes) {
                            if (hash && hash.length >= 8) {
                                const response = await fetch(`/api/chat/query-result/${hash}`);
                                if (response.ok) {
                                    const data = await response.json();
                                    if (data.data && data.data.length > 0) {
                                        return data.data;
                                    }
                                }
                            }
                        }
                    }
                }
                
                // 如果失败，尝试加载最新的查询结果文件
                const response = await fetch('/api/chat/latest-query-result');
                if (response.ok) {
                    const data = await response.json();
                    return data.data;
                }
            } catch (e) {
                console.error('Load latest query result error:', e);
            }
            return null;
        }

        function updateMessageWithTable(messageId, tableData) {
            const messageDiv = document.querySelector(`[id^='result-${messageId}']`)?.closest('.message');
            if (!messageDiv || !tableData) return;
            
            // 重新渲染消息内容，包含表格
            const content = messageDiv.querySelector('.message-text').textContent;
            const tools = Array.from(messageDiv.querySelectorAll('.tool-badge')).map(b => b.textContent);
            const sql = messageDiv.querySelector('.sql-code')?.textContent;
            const reasoningSteps = [];
            
            // 重新创建消息
            const newMessageDiv = document.createElement('div');
            newMessageDiv.className = 'message assistant';
            addAssistantMessage(content, reasoningSteps, sql, tools, tableData, null);
            
            // 移除旧消息
            messageDiv.remove();
        }

        function parseReasoningFromText(text) {
            const steps = [];
            
            // 先过滤掉明显的数据行
            const lines = text.split('\\n');
            const filteredLines = lines.filter(line => {
                const trimmed = line.trim();
                // 过滤掉 CSV 表头或数据行
                if (trimmed.includes(',') && trimmed.split(',').length >= 3) {
                    // 如果主要是数字、时间戳、逗号，很可能是数据行
                    if (/^[\\d\\s,\\-:\\.]+$/.test(trimmed)) {
                        return false;
                    }
                    // 如果包含时间戳格式，也很可能是数据行
                    if (/\\d{4}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}/.test(trimmed)) {
                        return false;
                    }
                }
                return true;
            });
            const filteredText = filteredLines.join('\\n');
            
            const patterns = [
                /(?:步骤|Step)\s*(\d+)[:：]\s*(.*?)(?=(?:步骤|Step)\s*\d+|$)/gi,
                /(\d+)\.\s+(.+?)(?=\d+\.|$)/g,
            ];
            
            for (const pattern of patterns) {
                const matches = [...filteredText.matchAll(pattern)];
                if (matches.length > 0) {
                    matches.forEach(match => {
                        const stepText = match[2].trim();
                        // 再次验证：如果步骤文本看起来像数据行，跳过
                        if (stepText.length > 0) {
                            // 检查是否包含时间戳格式
                            const hasTimestamp = /\\d{4}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}/.test(stepText);
                            // 检查是否是纯数据行
                            const isDataLine = stepText.includes(',') && stepText.split(',').length >= 3 && 
                                             /^[\\d\\s,\\-:\\.]+$/.test(stepText);
                            
                            if (!hasTimestamp && !isDataLine && stepText.length > 5) {
                                steps.push({
                                    number: parseInt(match[1]),
                                    text: stepText,
                                });
                            }
                        }
                    });
                    if (steps.length > 0) {
                        break;
                    }
                }
            }
            
            // 如果没有找到明确的步骤，且包含查询相关关键词，生成默认步骤
            if (steps.length === 0 && (text.includes('SQL') || text.includes('查询') || text.includes('可视化'))) {
                steps.push(
                    { number: 1, text: '理解用户需求' },
                    { number: 2, text: '生成 SQL 查询' },
                    { number: 3, text: '执行查询获取数据' },
                    { number: 4, text: '生成可视化结果' },
                );
            }
            
            return steps;
        }

        function extractSQLFromText(text) {
            if (!text) return null;
            
            const sqlPatterns = [
                /```sql\\s*([\\s\\S]*?)```/i,
                /```\\s*(SELECT[\\s\\S]*?);?\\s*```/i,
                /(SELECT[\\s\\S]{20,}?);/i,
                // 匹配没有代码块的 SELECT 语句（至少包含 FROM）
                /(SELECT\\s+[\\s\\S]{20,}?FROM[\\s\\S]{5,}?)(?:;|$|\\n)/i,
            ];
            
            for (const pattern of sqlPatterns) {
                const match = text.match(pattern);
                if (match && match[1]) {
                    let sql = match[1].trim();
                    // 清理 SQL：移除可能的代码块标记
                    sql = sql.replace(/^```sql\\s*/i, '').replace(/```\\s*$/i, '').trim();
                    if (sql.toUpperCase().startsWith('SELECT') && sql.length > 20) {
                        return sql;
                    }
                }
            }
            return null;
        }

        // 立即暴露到全局作用域
        window.askQuestion = askQuestion;
        window.sendMessage = sendMessage;
        
        // 继续定义其他变量和函数
        const chatContainer = document.getElementById('chat-container');
        const chatInput = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-btn');
        const exampleQuestions = document.getElementById('example-questions');

        // 自动调整输入框高度
        if (chatInput) {
            chatInput.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = Math.min(this.scrollHeight, 120) + 'px';
            });

            // Enter 发送，Shift+Enter 换行
            chatInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
        }

        function loadConversation(convId) {
            // 加载历史对话
            fetch(`/api/chat/conversation/${convId}`)
                .then(res => {
                    if (!res.ok) {
                        // 如果响应不是 OK，尝试解析错误消息
                        return res.json().then(err => {
                            throw new Error(err.error || `HTTP ${res.status}`);
                        }).catch(() => {
                            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
                        });
                    }
                    return res.json();
                })
                .then(data => {
                    chatContainer.innerHTML = '';
                    exampleQuestions.style.display = 'none';
                    // 设置当前会话 ID
                    currentConversationId = convId;
                    // 恢复消息历史
                    messageHistory = [];
                    // 渲染消息
                    if (data.messages && Array.isArray(data.messages)) {
                        data.messages.forEach(msg => {
                            if (msg.role === 'user') {
                                addUserMessage(msg.content);
                                messageHistory.push({ role: 'user', content: msg.content });
                            } else {
                                // 处理长内容，如果超过 5000 字符则截断并添加省略号
                                let content = msg.content || '';
                                const maxLength = 5000;
                                if (content.length > maxLength) {
                                    content = content.substring(0, maxLength) + '...';
                                }
                                // 传递图表数据和表格数据
                                addAssistantMessage(
                                    content, 
                                    msg.reasoning_steps || [], 
                                    msg.sql || null, 
                                    msg.tools || [], 
                                    msg.table_data || null,
                                    msg.chart_data || null
                                );
                                messageHistory.push({ role: 'assistant', content: content });
                            }
                        });
                        scrollToBottom();
                        // 更新新会话按钮显示状态
                        updateNewChatButtonVisibility();
                    } else {
                        console.error('Invalid response format:', data);
                        showToast('加载对话失败：数据格式错误');
                    }
                })
                .catch(err => {
                    console.error('Load conversation error:', err);
                    showToast('加载对话失败：' + err.message);
                });
        }

        function scrollToBottom() {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // 操作按钮功能
        function exportData(messageId) {
            const resultCard = document.getElementById('result-' + messageId);
            if (!resultCard) return;
            
            const table = resultCard.querySelector('.data-table');
            if (!table) return;
            
            const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent);
            const rows = Array.from(table.querySelectorAll('tbody tr')).map(tr => 
                Array.from(tr.querySelectorAll('td')).map(td => td.textContent)
            );
            
            const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\\n');
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'query_result_' + Date.now() + '.csv';
            link.click();
            
            showToast('导出成功');
        }

        function copyData(messageId) {
            const resultCard = document.getElementById('result-' + messageId);
            if (!resultCard) return;
            
            const table = resultCard.querySelector('.data-table');
            if (!table) return;
            
            const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent);
            const rows = Array.from(table.querySelectorAll('tbody tr')).map(tr => 
                Array.from(tr.querySelectorAll('td')).map(td => td.textContent)
            );
            
            const text = [headers.join('\\t'), ...rows.map(r => r.join('\\t'))].join('\\n');
            
            navigator.clipboard.writeText(text).then(() => {
                showToast('已复制到剪贴板');
            }).catch(() => {
                showToast('复制失败');
            });
        }

        function copySql(messageId) {
            const sqlCode = document.getElementById('sql-' + messageId);
            if (!sqlCode) return;
            
            const sql = sqlCode.textContent.trim();
            navigator.clipboard.writeText(sql).then(() => {
                showToast('SQL 已复制到剪贴板');
            }).catch(() => {
                showToast('复制失败');
            });
        }

        function toggleLike(messageId) {
            const btn = document.getElementById('like-' + messageId);
            const dislikeBtn = document.getElementById('dislike-' + messageId);
            
            if (btn.classList.contains('active')) {
                btn.classList.remove('active');
                showToast('已取消点赞');
            } else {
                btn.classList.add('active');
                if (dislikeBtn) dislikeBtn.classList.remove('active');
                showToast('已点赞');
            }
        }

        function toggleDislike(messageId) {
            const btn = document.getElementById('dislike-' + messageId);
            const likeBtn = document.getElementById('like-' + messageId);
            
            if (btn.classList.contains('active')) {
                btn.classList.remove('active');
                showToast('已取消点踩');
            } else {
                btn.classList.add('active');
                if (likeBtn) likeBtn.classList.remove('active');
                showToast('已点踩');
            }
        }

        function askHuman(messageId) {
            showToast('暂未实现');
        }

        function toggleChart(messageId) {
            const chartContainer = document.getElementById('chart-' + messageId);
            if (!chartContainer) return;
            
            chartContainer.classList.toggle('active');
            const btn = chartContainer.previousElementSibling;
            if (chartContainer.classList.contains('active')) {
                btn.textContent = '📊 隐藏图表';
            } else {
                btn.textContent = '📊 查看图表';
            }
        }

        function renderChart(messageId, chartData, tableData) {
            const chartContainer = document.getElementById('chart-' + messageId);
            if (!chartContainer || !tableData || tableData.length === 0) return;
            
            const headers = Object.keys(tableData[0]);
            if (headers.length < 2) return;
            
            // 自动判断图表类型
            const xKey = headers[0];
            const yKey = headers[1];
            
            const xData = tableData.map(row => row[xKey]);
            const yData = tableData.map(row => {
                const val = row[yKey];
                return typeof val === 'string' ? parseFloat(val) || 0 : val;
            });
            
            // 根据数据特征选择图表类型
            let chartType = 'bar';
            if (headers.length === 2 && tableData.length <= 10) {
                chartType = 'pie';
            } else if (xData.some(x => typeof x === 'string' && x.match(/\\d{4}-\\d{2}-\\d{2}/))) {
                chartType = 'scatter';
            }
            
            let trace;
            if (chartType === 'pie') {
                trace = {
                    type: 'pie',
                    labels: xData,
                    values: yData,
                };
            } else if (chartType === 'scatter') {
                trace = {
                    type: 'scatter',
                    mode: 'lines+markers',
                    x: xData,
                    y: yData,
                    name: yKey,
                };
            } else {
                trace = {
                    type: 'bar',
                    x: xData,
                    y: yData,
                    name: yKey,
                };
            }
            
            const layout = {
                title: yKey,
                xaxis: { title: xKey },
                yaxis: { title: yKey },
                margin: { l: 60, r: 30, t: 40, b: 60 },
            };
            
            Plotly.newPlot(chartContainer, [trace], layout, { responsive: true });
        }

        function showToast(message) {
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.textContent = message;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }, 2000);
        }

        // 服务状态管理
        let serverStatus = null;
        let statusCheckInterval = null;

        function checkServerStatus() {
            // 减少日志输出，只在调试时启用
            // console.log('Checking server status...');
            fetch('/api/server/status')
                .then(res => {
                    // console.log('Status response:', res.status);
                    if (!res.ok) {
                        throw new Error('HTTP ' + res.status);
                    }
                    return res.json();
                })
                .then(data => {
                    // console.log('Server status data:', data);
                    serverStatus = data.running;
                    updateServerStatusUI(data.running, false);
                })
                .catch(err => {
                    console.error('Check server status error:', err);
                    serverStatus = false;
                    updateServerStatusUI(false, false);
                });
        }

        function updateServerStatusUI(isRunning, isStarting) {
            // 减少日志输出，只在调试时启用
            // console.log('updateServerStatusUI called:', { isRunning, isStarting });
            const btn = document.getElementById('server-status-btn');
            const dot = document.getElementById('status-dot');
            const text = document.getElementById('status-text');

            // console.log('UI elements:', { btn: !!btn, dot: !!dot, text: !!text });

            if (!btn || !dot || !text) {
                console.error('Server status UI elements not found');
                // 如果元素不存在，等待一下再试
                setTimeout(() => {
                    const btn2 = document.getElementById('server-status-btn');
                    const dot2 = document.getElementById('status-dot');
                    const text2 = document.getElementById('status-text');
                    if (btn2 && dot2 && text2) {
                        updateServerStatusUI(isRunning, isStarting);
                    }
                }, 500);
                return;
            }

            btn.className = 'server-status-btn';
            dot.className = 'status-dot';

            if (isStarting) {
                btn.classList.add('starting');
                dot.classList.add('starting');
                text.textContent = '正在启动...';
                console.log('Status updated to: 正在启动...');
            } else if (isRunning) {
                btn.classList.add('running');
                dot.classList.add('running');
                text.textContent = '服务运行中';
                // console.log('Status updated to: 服务运行中');
            } else {
                btn.classList.add('stopped');
                dot.classList.add('stopped');
                text.textContent = '点击启动服务';
                console.log('Status updated to: 点击启动服务');
            }
        }

        function handleServerAction() {
            // 先检查当前状态
            checkServerStatus();
            
            // 等待状态检查完成后再判断
            setTimeout(() => {
                if (serverStatus) {
                    // 如果服务正在运行，则停止服务
                    if (confirm('确定要停止服务吗？')) {
                        stopServer();
                    }
                    return;
                }

                // 启动服务
                updateServerStatusUI(false, true);
                
                fetch('/api/server/start', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                })
                .then(res => {
                    if (!res.ok) {
                        throw new Error('HTTP ' + res.status);
                    }
                    return res.json();
                })
                .then(data => {
                    if (data.success) {
                        showToast('正在启动服务，请稍候...');
                        // 等待几秒后检查状态
                        setTimeout(() => {
                            checkServerStatus();
                            // 开始定期检查
                            if (!statusCheckInterval) {
                                statusCheckInterval = setInterval(checkServerStatus, 3000);
                            }
                        }, 3000);
                    } else {
                        updateServerStatusUI(false, false);
                        showToast(data.message || '启动失败');
                    }
                })
                .catch(err => {
                    console.error('Start server error:', err);
                    updateServerStatusUI(false, false);
                    showToast('启动失败: ' + err.message + '。请手动运行 ./start.sh');
                });
            }, 500);
        }

        function stopServer() {
            updateServerStatusUI(false, true);
            fetch('/api/server/stop', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            })
            .then(res => {
                if (!res.ok) {
                    throw new Error('HTTP ' + res.status);
                }
                return res.json();
            })
            .then(data => {
                if (data.success) {
                    showToast('服务已停止');
                    updateServerStatusUI(false, false);
                    serverStatus = false;
                } else {
                    showToast(data.message || '停止失败');
                    updateServerStatusUI(true, false);
                }
            })
            .catch(err => {
                console.error('Stop server error:', err);
                showToast('停止失败: ' + err.message);
                updateServerStatusUI(true, false);
            });
        }

        // 更新新会话按钮的显示状态
        function updateNewChatButtonVisibility() {
            const newChatBtn = document.getElementById('new-chat-btn');
            if (!newChatBtn) return;
            
            const chatContainer = document.getElementById('chat-container');
            const hasMessages = chatContainer && chatContainer.querySelectorAll('.message').length > 0;
            const hasConversationId = currentConversationId !== null;
            const hasMessageHistory = messageHistory && messageHistory.length > 0;
            
            // 如果有会话内容，显示按钮；如果没有，隐藏按钮
            if (hasMessages || hasConversationId || hasMessageHistory) {
                newChatBtn.style.display = 'flex';
            } else {
                newChatBtn.style.display = 'none';
            }
        }
        
        function startNewConversation() {
            // 检查是否有会话内容
            const chatContainer = document.getElementById('chat-container');
            const hasMessages = chatContainer && chatContainer.querySelectorAll('.message').length > 0;
            const hasConversationId = currentConversationId !== null;
            const hasMessageHistory = messageHistory && messageHistory.length > 0;
            
            // 如果没有会话内容，直接开始新会话
            if (!hasMessages && !hasConversationId && !hasMessageHistory) {
                // 确保示例问题显示
                const exampleQuestions = document.getElementById('example-questions');
                if (exampleQuestions) {
                    exampleQuestions.style.display = 'grid';
                }
                // 隐藏新会话按钮
                updateNewChatButtonVisibility();
                showToast('已开始新会话');
                return;
            }
            
            // 如果有会话内容，显示确认对话框
            if (confirm('确定要开始新会话吗？当前会话将被保存。')) {
                currentConversationId = null;
                messageHistory = [];
                
                // 先获取示例问题元素
                const exampleQuestions = document.getElementById('example-questions');
                
                // 清空聊天容器（但保留示例问题）
                if (chatContainer) {
                    // 只移除消息，保留示例问题
                    const messages = chatContainer.querySelectorAll('.message');
                    messages.forEach(msg => msg.remove());
                    
                    // 确保示例问题元素存在且显示
                    if (exampleQuestions) {
                        // 如果示例问题不在容器中，重新添加
                        if (!chatContainer.contains(exampleQuestions)) {
                            chatContainer.insertBefore(exampleQuestions, chatContainer.firstChild);
                        }
                        exampleQuestions.style.display = 'grid';
                    } else {
                        // 如果示例问题元素不存在，重新创建
                        const newExampleQuestions = document.createElement('div');
                        newExampleQuestions.id = 'example-questions';
                        newExampleQuestions.className = 'example-questions';
                        newExampleQuestions.style.display = 'grid';
                        newExampleQuestions.innerHTML = `
                            <div class="example-card" data-question="最近7天按省份统计访问量" onclick="askQuestion(this.dataset.question)">
                                <div class="example-text">最近7天按省份统计访问量</div>
                            </div>
                            <div class="example-card" data-question="显示各渠道的转化率对比" onclick="askQuestion(this.dataset.question)">
                                <div class="example-text">显示各渠道的转化率对比</div>
                            </div>
                            <div class="example-card" data-question="Top 10 访问量最高的页面" onclick="askQuestion(this.dataset.question)">
                                <div class="example-text">Top 10 访问量最高的页面</div>
                            </div>
                            <div class="example-card" data-question="最近一个月的访问趋势" onclick="askQuestion(this.dataset.question)">
                                <div class="example-text">最近一个月的访问趋势</div>
                            </div>
                        `;
                        chatContainer.insertBefore(newExampleQuestions, chatContainer.firstChild);
                    }
                } else {
                    // 如果容器不存在，至少确保示例问题显示
                    if (exampleQuestions) {
                        exampleQuestions.style.display = 'grid';
                    }
                }
                
                // 更新按钮显示状态
                updateNewChatButtonVisibility();
                showToast('已开始新会话');
            }
        }

        // deleteConversation 函数已在上面定义，这里不再重复定义

        // 确保所有函数在全局作用域（函数声明会提升，所以可以在这里赋值）
        // askQuestion 和 sendMessage 已经在上面赋值了
        window.loadConversation = loadConversation;
        window.handleServerAction = handleServerAction;
        window.stopServer = stopServer;
        window.startNewConversation = startNewConversation;
        window.updateNewChatButtonVisibility = updateNewChatButtonVisibility;
        window.deleteConversation = deleteConversation;
        window.exportData = exportData;
        window.copyData = copyData;
        window.copySql = copySql;
        window.toggleLike = toggleLike;
        window.toggleDislike = toggleDislike;
        window.askHuman = askHuman;
        window.toggleChart = toggleChart;
        
        // 刷新左侧会话列表
        function refreshConversationList() {
            fetch('/api/chat/conversations')
                .then(res => res.json())
                .then(data => {
                    if (data && data.conversations) {
                        const container = document.getElementById('recent-conversations');
                        if (container) {
                            container.innerHTML = data.conversations.map(c => {
                                return `
                                    <div class="conversation-item" data-conv-id="${escapeHtml(c.id)}">
                                        <div style="flex: 1; cursor: pointer;" onclick='loadConversation(${JSON.stringify(c.id)})'>
                                            <div class="conversation-summary">${escapeHtml(c.summary)}</div>
                                            <div class="conversation-time">${escapeHtml(c.time)}</div>
                                        </div>
                                        <button class="conversation-delete-btn" data-conv-id="${escapeHtml(c.id)}" title="删除">×</button>
                                    </div>
                                `;
                            }).join('');
                        }
                        // 为新添加的删除按钮绑定事件（事件委托已经处理，这里作为备用）
                        if (typeof bindDeleteButtons === 'function') {
                            setTimeout(bindDeleteButtons, 50);
                        }
                    }
                })
                .catch(err => {
                    console.error('Failed to refresh conversation list:', err);
                });
        }
        
        // 绑定服务状态按钮点击事件
        const serverStatusBtn = document.getElementById('server-status-btn');
        if (serverStatusBtn) {
            serverStatusBtn.addEventListener('click', handleServerAction);
        }

        // 页面加载时检查服务状态
        // 确保在DOM完全加载后再检查
        let statusCheckInitialized = false;
        function initServerStatusCheck() {
            // 防止重复初始化
            if (statusCheckInitialized) {
                return;
            }
            
            const btn = document.getElementById('server-status-btn');
            if (!btn) {
                // 如果按钮还不存在，等待一下再试（最多重试10次）
                if (typeof initServerStatusCheck.retryCount === 'undefined') {
                    initServerStatusCheck.retryCount = 0;
                }
                if (initServerStatusCheck.retryCount < 10) {
                    initServerStatusCheck.retryCount++;
                    setTimeout(initServerStatusCheck, 100);
                }
                return;
            }
            
            // 标记为已初始化
            statusCheckInitialized = true;
            
            // 立即检查一次
            checkServerStatus();
            
            // 每5秒检查一次服务状态（只设置一次）
            if (!statusCheckInterval) {
                statusCheckInterval = setInterval(checkServerStatus, 5000);
            }
        }
        
        // 等待DOM加载完成
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(initServerStatusCheck, 200);
                // 初始化示例问题显示
                initExampleQuestions();
            });
        } else {
            setTimeout(initServerStatusCheck, 200);
            // 初始化示例问题显示
            initExampleQuestions();
        }
        
        // 页面加载时，如果 chatContainer 为空，显示示例问题
        function initExampleQuestions() {
            const chatContainer = document.getElementById('chat-container');
            const exampleQuestions = document.getElementById('example-questions');
            if (chatContainer && exampleQuestions) {
                // 检查是否有消息（不包括示例问题本身）
                const hasMessages = chatContainer.querySelectorAll('.message').length > 0;
                if (!hasMessages) {
                    exampleQuestions.style.display = 'grid';
                } else {
                    exampleQuestions.style.display = 'none';
                }
            }
            // 初始化新会话按钮显示状态
            updateNewChatButtonVisibility();
        }
        
    </script>
</body>
</html>
        """
        return HTMLResponse(content=html_content)

    @router.get("/api/chat/conversations")
    async def get_conversations():
        """获取最近的会话列表"""
        try:
            if not LOGS_DB_PATH.exists():
                return JSONResponse({"conversations": []})

            conn = sqlite3.connect(str(LOGS_DB_PATH))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            # 检查是否有 deleted 列
            try:
                cur.execute("ALTER TABLE conversation ADD COLUMN deleted INTEGER DEFAULT 0")
                conn.commit()
            except sqlite3.OperationalError:
                pass
            
            # 检查是否有 user_nickname 列
            try:
                cur.execute("ALTER TABLE conversation ADD COLUMN user_nickname TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                pass
            
            rows = cur.execute(
                """
                SELECT id, user_id, user_nickname, started_at, summary
                FROM conversation
                WHERE deleted = 0 OR deleted IS NULL
                ORDER BY started_at DESC
                LIMIT 100
                """
            ).fetchall()
            
            from datetime import datetime
            conversations = []
            for r in rows:
                # 获取第一条用户消息作为标题
                first_user_msg = cur.execute(
                    """
                    SELECT content
                    FROM conversation_message
                    WHERE conversation_id = ? AND role = 'user'
                    ORDER BY created_at
                    LIMIT 1
                    """,
                    (r["id"],),
                ).fetchone()
                
                title = "（无标题）"
                if first_user_msg and first_user_msg["content"]:
                    title = first_user_msg["content"].strip()
                    if len(title) > 50:
                        title = title[:47] + "..."
                elif r["summary"]:
                    title = r["summary"].strip()
                    if len(title) > 50:
                        title = title[:47] + "..."
                
                # 格式化日期
                try:
                    dt = datetime.fromisoformat(r["started_at"].replace('T', ' ').split('.')[0])
                    now = datetime.now()
                    diff = now - dt
                    
                    if diff.days == 0:
                        time_str = dt.strftime("%H:%M")
                    elif diff.days == 1:
                        time_str = "昨天 " + dt.strftime("%H:%M")
                    elif diff.days < 7:
                        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                        time_str = weekdays[dt.weekday()] + " " + dt.strftime("%H:%M")
                    elif diff.days < 365:
                        time_str = dt.strftime("%m-%d %H:%M")
                    else:
                        time_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    time_str = r["started_at"]
                
                conversations.append({
                    "id": r["id"],
                    "summary": title,
                    "time": time_str,
                    "user_id": r["user_id"] or "guest",
                    "user_nickname": r["user_nickname"] or r["user_id"] or "guest",
                })
            
            conn.close()
            return JSONResponse({"conversations": conversations})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JSONResponse({"conversations": [], "error": str(e)})

    @router.get("/api/chat/conversation/{conversation_id}")
    async def get_conversation(conversation_id: str):
        """获取对话详情（JSON API）"""
        try:
            if not LOGS_DB_PATH.exists():
                return JSONResponse({"error": "数据库不存在"}, status_code=404)

            conn = sqlite3.connect(str(LOGS_DB_PATH))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            messages = cur.execute(
                """
                SELECT role, content, created_at, extra_json
                FROM conversation_message
                WHERE conversation_id = ?
                ORDER BY created_at
                """,
                (conversation_id,),
            ).fetchall()

            conn.close()

            result_messages = []
            for m in messages:
                role = m["role"]
                content = m["content"] or ""
                # sqlite3.Row 不支持 .get()，使用 try-except 或直接访问
                extra_json = None
                try:
                    extra_json = m["extra_json"]
                except (KeyError, IndexError):
                    pass
                
                msg_data = {
                    "role": role,
                    "content": content,
                    "created_at": m["created_at"],
                }

                if role == "assistant":
                    try:
                        # 解析推理步骤和 SQL
                        reasoning_steps = parse_reasoning_steps(content)
                        sql = extract_sql_from_message(content)
                        
                        if content and content.lstrip().startswith("data:"):
                            simp = simplify_sse_message(content)
                            msg_data["content"] = simp["display_text"]
                            msg_data["tools"] = simp["tools"]
                        
                        if reasoning_steps:
                            msg_data["reasoning_steps"] = reasoning_steps
                        if sql:
                            msg_data["sql"] = sql
                        
                        # 尝试从 extra_json 中提取表格和图表数据
                        if extra_json:
                            try:
                                # extra_json 可能是字符串或已经是 dict
                                if isinstance(extra_json, str):
                                    extra = json.loads(extra_json)
                                else:
                                    extra = extra_json
                                if isinstance(extra, dict):
                                    # 优先使用 extra_json 中保存的 SQL
                                    if "sql" in extra and extra["sql"]:
                                        msg_data["sql"] = extra["sql"]
                                    # 优先使用 extra_json 中的 reasoning_steps
                                    if "reasoning_steps" in extra and extra["reasoning_steps"]:
                                        msg_data["reasoning_steps"] = extra["reasoning_steps"]
                                    # 提取表格数据
                                    if "table_data" in extra:
                                        msg_data["table_data"] = extra["table_data"]
                                    elif "query_result" in extra:
                                        msg_data["table_data"] = extra["query_result"]
                                    # 提取图表数据
                                    if "chart_data" in extra:
                                        msg_data["chart_data"] = extra["chart_data"]
                            except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
                                # 忽略 extra_json 解析错误，不影响主要功能
                                pass
                    except Exception as e:
                        # 如果处理 assistant 消息时出错，至少返回原始内容
                        import traceback
                        traceback.print_exc()
                        # 不抛出异常，继续处理其他消息

                result_messages.append(msg_data)

            return {"messages": result_messages}
        except Exception as e:
            import traceback
            error_msg = f"获取对话详情失败: {str(e)}"
            traceback.print_exc()
            return JSONResponse({"error": error_msg}, status_code=500)

    @router.get("/api/chat/query-result/{file_hash}")
    async def get_query_result(file_hash: str):
        """从 vanna_data 目录获取查询结果 CSV 文件"""
        try:
            # 查找对应的 CSV 文件
            csv_files = list(VANNA_DATA_DIR.glob(f"{file_hash}/query_results_*.csv"))
            if not csv_files:
                return JSONResponse({"error": "文件未找到"}, status_code=404)
            
            # 读取最新的 CSV 文件
            latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
            
            with open(latest_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            return {"data": rows, "columns": list(rows[0].keys()) if rows else []}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @router.get("/api/chat/latest-query-result")
    async def get_latest_query_result():
        """获取最新的查询结果 CSV 文件"""
        try:
            # 查找所有 CSV 文件
            csv_files = list(VANNA_DATA_DIR.glob("*/query_results_*.csv"))
            if not csv_files:
                return JSONResponse({"error": "没有找到查询结果文件"}, status_code=404)
            
            # 获取最新的文件
            latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
            
            with open(latest_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            return {"data": rows, "columns": list(rows[0].keys()) if rows else []}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @router.get("/api/server/status")
    async def get_server_status():
        """检查后端服务状态"""
        port = 8000
        is_running = False
        
        try:
            # 尝试连接端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            is_running = result == 0
        except Exception:
            pass
        
        return {
            "running": is_running,
            "port": port,
            "message": "服务运行中" if is_running else "服务未运行"
        }

    @router.post("/api/server/start")
    async def start_server():
        """启动后端服务（后台进程）"""
        try:
            # 检查服务是否已运行
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', 8000))
            sock.close()
            
            if result == 0:
                return JSONResponse({
                    "success": False,
                    "message": "服务已在运行中"
                })
            
            # 启动服务（后台进程）
            import os
            venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
            if not venv_python.exists():
                venv_python = "python"
            
            script_path = PROJECT_ROOT / "start.sh"
            if script_path.exists():
                # 使用启动脚本
                subprocess.Popen(
                    ["/bin/bash", str(script_path)],
                    cwd=str(PROJECT_ROOT),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            else:
                # 直接启动 uvicorn
                subprocess.Popen(
                    [str(venv_python), "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
                    cwd=str(PROJECT_ROOT),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            
            return {
                "success": True,
                "message": "正在启动服务，请稍候..."
            }
        except Exception as e:
            return JSONResponse({
                "success": False,
                "message": f"启动失败: {str(e)}"
            }, status_code=500)

    @router.post("/api/server/stop")
    async def stop_server():
        """停止后端服务"""
        try:
            # 查找运行在 8000 端口的进程
            try:
                import psutil
                port = 8000
                killed = False
                
                for proc in psutil.process_iter(['pid', 'name', 'connections']):
                    try:
                        connections = proc.info.get('connections')
                        if connections:
                            for conn in connections:
                                if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
                                    proc.kill()
                                    killed = True
                                    break
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                if killed:
                    return {
                        "success": True,
                        "message": "服务已停止"
                    }
            except ImportError:
                # 如果没有 psutil，尝试使用 lsof 命令
                result = subprocess.run(
                    ["lsof", "-ti", f":8000"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        try:
                            subprocess.run(["kill", pid], check=True)
                        except Exception:
                            pass
                    return {
                        "success": True,
                        "message": "服务已停止"
                    }
            
            return JSONResponse({
                "success": False,
                "message": "未找到运行中的服务"
            }, status_code=404)
        except Exception as e:
            return JSONResponse({
                "success": False,
                "message": f"停止失败: {str(e)}。请手动停止服务。"
            }, status_code=500)

    @router.get("/api/chat/conversation/{conversation_id}/get-sql")
    async def get_conversation_sql(conversation_id: str):
        """获取会话的 SQL 查询"""
        try:
            if not LOGS_DB_PATH.exists():
                return JSONResponse({"success": False, "sql": None, "source": "none"})
            
            conn = sqlite3.connect(str(LOGS_DB_PATH))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            # 从 assistant 消息的 extra_json 中查找 SQL
            messages = cur.execute("""
                SELECT content, extra_json 
                FROM conversation_message 
                WHERE conversation_id = ? AND role = 'assistant'
                ORDER BY created_at DESC
            """, (conversation_id,)).fetchall()
            
            for msg in messages:
                # 优先从 extra_json 中提取
                if msg['extra_json']:
                    try:
                        extra = json.loads(msg['extra_json'])
                        if extra.get('sql'):
                            conn.close()
                            return JSONResponse({
                                "success": True, 
                                "sql": extra['sql'], 
                                "source": "extra_json"
                            })
                    except:
                        pass
                
                # 从消息内容中提取
                if msg['content']:
                    sql = extract_sql_from_message(msg['content'])
                    if sql:
                        conn.close()
                        return JSONResponse({
                            "success": True, 
                            "sql": sql, 
                            "source": "content"
                        })
            
            # 【新增】如果都没有，尝试从 Agent Memory 中获取（Vanna 会保存 tool_usage）
            try:
                from app.config import MEMORY_DB_PATH
                if MEMORY_DB_PATH.exists():
                    memory_conn = sqlite3.connect(str(MEMORY_DB_PATH))
                    memory_conn.row_factory = sqlite3.Row
                    memory_cur = memory_conn.cursor()
                    
                    # 从 tool_memory 中查找最近的 RunSqlTool 调用
                    # 注意：这里需要根据 conversation_id 匹配，但 tool_memory 可能没有 conversation_id
                    # 所以我们需要根据时间戳来匹配（假设最近的 tool_usage 就是当前会话的）
                    tool_records = memory_cur.execute("""
                        SELECT args, timestamp, question
                        FROM tool_memory
                        WHERE tool_name = 'RunSqlTool'
                        ORDER BY timestamp DESC
                        LIMIT 10
                    """).fetchall()
                    
                    memory_conn.close()
                    
                    # 尝试从最近的 tool_usage 中提取 SQL（排除系统查询）
                    for tool_record in tool_records:
                        try:
                            args = json.loads(tool_record['args'])
                            if args.get('sql'):
                                sql_str = args['sql'].strip()
                                sql_upper = sql_str.upper()
                                # 只返回用户查询的 SQL，排除系统查询
                                if (sql_upper.startswith('SELECT') and 
                                    'FROM' in sql_upper and
                                    'sqlite_master' not in sql_upper and
                                    'PRAGMA' not in sql_upper and
                                    len(sql_str) > 30):  # 排除太短的查询
                                    conn.close()
                                    return JSONResponse({
                                        "success": True,
                                        "sql": sql_str,
                                        "source": "agent_memory"
                                    })
                        except:
                            pass
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"从 Agent Memory 获取 SQL 失败: {e}")
            
            conn.close()
            return JSONResponse({"success": True, "sql": None, "source": "none"})
        except Exception as e:
            return JSONResponse({"success": False, "sql": None, "error": str(e)})

    @router.delete("/api/chat/conversation/{conversation_id}")
    async def delete_conversation(conversation_id: str):
        """删除会话（软删除，保留日志）"""
        try:
            if not LOGS_DB_PATH.exists():
                return JSONResponse({"error": "数据库不存在"}, status_code=404)

            conn = sqlite3.connect(str(LOGS_DB_PATH))
            cur = conn.cursor()
            
            # 检查会话是否存在
            conv = cur.execute(
                "SELECT id FROM conversation WHERE id = ?",
                (conversation_id,)
            ).fetchone()
            
            if not conv:
                conn.close()
                return JSONResponse({"error": "会话不存在"}, status_code=404)
            
            # 软删除：在 conversation 表中添加 deleted 标记
            # 如果表没有 deleted 列，先添加
            try:
                cur.execute("ALTER TABLE conversation ADD COLUMN deleted INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                # 列已存在，忽略
                pass
            
            # 标记为已删除
            cur.execute(
                "UPDATE conversation SET deleted = 1 WHERE id = ?",
                (conversation_id,)
            )
            conn.commit()
            conn.close()
            
            return JSONResponse({"success": True, "message": "会话已删除"})
        except Exception as e:
            import traceback
            error_msg = f"删除会话失败: {str(e)}"
            traceback.print_exc()
            return JSONResponse({"success": False, "error": error_msg}, status_code=500)

    return router

