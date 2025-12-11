import json
import sqlite3
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.config import LOGS_DB_PATH
from app.services.summary import (
    simplify_sse_message,
    generate_summary_for_conversation,
)
from app.utils.html import html_escape
from app.routes.chat import parse_reasoning_steps, extract_sql_from_message
from vanna.integrations.openai import OpenAILlmService


def create_logs_router(llm: OpenAILlmService) -> APIRouter:
    router = APIRouter()

    @router.get("/logs", response_class=HTMLResponse)
    async def list_logs():
        db_path = LOGS_DB_PATH
        if not db_path.exists():
            return HTMLResponse("<h1>日志数据库不存在，请先初始化 logs/logs.db</h1>", status_code=500)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        rows = cur.execute(
            """
            SELECT id, user_id, started_at, ended_at, source, has_error, summary
            FROM conversation
            ORDER BY started_at DESC
            LIMIT 200
            """
        ).fetchall()

        conn.close()

        tr_list = []
        for r in rows:
            cid = r["id"]
            tr_list.append(
                f"""
                <tr onclick="location.href='/logs/{html_escape(cid)}'" style="cursor:pointer;">
                  <td class="cell-id">{html_escape(cid)}</td>
                  <td>{html_escape(r['user_id'])}</td>
                  <td>{html_escape(r['source'])}</td>
                  <td>{html_escape(r['started_at'])}</td>
                  <td>{html_escape(r['ended_at'] or '')}</td>
                  <td>
                    {"<span class='tag error'>错误</span>" if r['has_error'] else "<span class='tag ok'>正常</span>"}
                  </td>
                  <td class="cell-summary">{html_escape(r['summary'] or '（暂无摘要）')}</td>
                </tr>
                """
            )

        html_page = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>对话日志列表 - Data Agent</title>
          <style>
            :root {{
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
            }}

            * {{
              box-sizing: border-box;
              margin: 0;
              padding: 0;
            }}

            body {{
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
              background: var(--color-bg);
              color: var(--color-text);
              line-height: 1.6;
            }}

            .page {{
              max-width: 1200px;
              margin: 0 auto;
              padding: 24px 20px;
            }}

            .header {{
              display: flex;
              align-items: center;
              justify-content: space-between;
              margin-bottom: 24px;
            }}

            .header-title {{
              font-size: 24px;
              font-weight: 600;
              color: var(--color-text);
            }}

            .header-actions {{
              display: flex;
              gap: 12px;
            }}

            .btn {{
              padding: 8px 16px;
              border: 1px solid var(--color-border);
              background: var(--color-surface);
              border-radius: var(--radius);
              font-size: 13px;
              cursor: pointer;
              transition: all 0.2s;
              text-decoration: none;
              color: var(--color-text);
              display: inline-flex;
              align-items: center;
              gap: 6px;
            }}

            .btn:hover {{
              background: var(--color-bg);
              border-color: var(--color-accent);
            }}

            .btn.primary {{
              background: var(--color-accent);
              color: white;
              border-color: var(--color-accent);
            }}

            .btn.primary:hover {{
              background: var(--color-accent-hover);
            }}

            .conversations-grid {{
              display: grid;
              grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
              gap: 16px;
            }}

            .conversation-card {{
              background: var(--color-surface);
              border: 1px solid var(--color-border);
              border-radius: var(--radius-lg);
              padding: 16px;
              cursor: pointer;
              transition: all 0.2s;
              box-shadow: var(--shadow-sm);
            }}

            .conversation-card:hover {{
              border-color: var(--color-accent);
              box-shadow: var(--shadow-md);
              transform: translateY(-2px);
            }}

            .card-header {{
              display: flex;
              align-items: flex-start;
              justify-content: space-between;
              margin-bottom: 12px;
            }}

            .card-id {{
              font-size: 11px;
              font-family: monospace;
              color: var(--color-text-muted);
              word-break: break-all;
              flex: 1;
              margin-right: 8px;
            }}

            .status-badge {{
              display: inline-flex;
              align-items: center;
              padding: 2px 8px;
              border-radius: 12px;
              font-size: 11px;
              font-weight: 500;
              white-space: nowrap;
            }}

            .status-badge.ok {{
              background: #f0fdf4;
              color: #15803d;
              border: 1px solid #bbf7d0;
            }}

            .status-badge.error {{
              background: #fef2f2;
              color: #b91c1c;
              border: 1px solid #fecaca;
            }}

            .card-meta {{
              display: flex;
              flex-direction: column;
              gap: 6px;
              margin-bottom: 12px;
              font-size: 12px;
              color: var(--color-text-muted);
            }}

            .card-meta-item {{
              display: flex;
              align-items: center;
              gap: 6px;
            }}

            .card-summary {{
              font-size: 13px;
              color: var(--color-text);
              line-height: 1.5;
              display: -webkit-box;
              -webkit-line-clamp: 3;
              -webkit-box-orient: vertical;
              overflow: hidden;
            }}

            .empty-state {{
              text-align: center;
              padding: 60px 20px;
              color: var(--color-text-muted);
            }}

            .empty-state-icon {{
              font-size: 48px;
              margin-bottom: 16px;
            }}

            .search-bar {{
              margin-bottom: 20px;
            }}

            .search-input {{
              width: 100%;
              padding: 10px 16px;
              border: 1px solid var(--color-border);
              border-radius: var(--radius);
              font-size: 14px;
              background: var(--color-surface);
            }}

            .search-input:focus {{
              outline: none;
              border-color: var(--color-accent);
              box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            }}
          </style>
        </head>
        <body>
          <div class="page">
            <div class="header">
              <h1 class="header-title">对话日志</h1>
              <div class="header-actions">
                <a href="/chat" class="btn primary">📋 返回对话列表</a>
              </div>
            </div>

            <div class="search-bar">
              <input type="text" class="search-input" id="search-input" placeholder="搜索对话摘要、用户ID或会话ID..." />
            </div>

            <div class="conversations-grid" id="conversations-grid">
              {''.join([
                f'''
                <div class="conversation-card" onclick="location.href='/logs/{html_escape(r["id"])}'" data-search="{html_escape((r["summary"] or "") + " " + r["user_id"] + " " + r["id"])}">
                  <div class="card-header">
                    <div class="card-id">{html_escape(r["id"][:40])}{"..." if len(r["id"]) > 40 else ""}</div>
                    <span class="status-badge {"error" if r["has_error"] else "ok"}">
                      {"错误" if r["has_error"] else "正常"}
                    </span>
                  </div>
                  <div class="card-meta">
                    <div class="card-meta-item">
                      <span>👤</span>
                      <span>{html_escape(r["user_id"])}</span>
                    </div>
                    <div class="card-meta-item">
                      <span>🕐</span>
                      <span>{html_escape(r["started_at"])}</span>
                    </div>
                    {f'<div class="card-meta-item"><span>📍</span><span>{html_escape(r["source"])}</span></div>' if r["source"] else ""}
                  </div>
                  <div class="card-summary">{html_escape(r["summary"] or "（暂无摘要）")}</div>
                </div>
                '''
                for r in rows
              ]) if rows else '<div class="empty-state"><div class="empty-state-icon">📭</div><div>暂无对话记录</div></div>'}
            </div>
          </div>

          <script>
            const searchInput = document.getElementById('search-input');
            const grid = document.getElementById('conversations-grid');
            const cards = Array.from(grid.querySelectorAll('.conversation-card'));

            searchInput.addEventListener('input', function(e) {{
              const query = e.target.value.toLowerCase().trim();
              
              cards.forEach(card => {{
                const searchText = card.getAttribute('data-search').toLowerCase();
                if (searchText.includes(query)) {{
                  card.style.display = '';
                }} else {{
                  card.style.display = 'none';
                }}
              }});

              // 显示空状态
              const visibleCards = cards.filter(c => c.style.display !== 'none');
              if (visibleCards.length === 0 && query) {{
                if (!grid.querySelector('.empty-state')) {{
                  const emptyState = document.createElement('div');
                  emptyState.className = 'empty-state';
                  emptyState.innerHTML = '<div class="empty-state-icon">🔍</div><div>未找到匹配的对话</div>';
                  grid.appendChild(emptyState);
                }}
              }} else {{
                const emptyState = grid.querySelector('.empty-state');
                if (emptyState && !emptyState.classList.contains('permanent')) {{
                  emptyState.remove();
                }}
              }}
            }});
          </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_page)

    @router.get("/logs/{conversation_id}", response_class=HTMLResponse)
    async def conversation_detail(conversation_id: str):
        db_path = LOGS_DB_PATH
        if not db_path.exists():
            return HTMLResponse("<h1>日志数据库不存在，请先初始化 logs/logs.db</h1>", status_code=500)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        conv = cur.execute(
            "SELECT * FROM conversation WHERE id = ?",
            (conversation_id,),
        ).fetchone()

        if not conv:
            conn.close()
            return HTMLResponse(
                content=f"<h1>未找到对话：{html_escape(conversation_id)}</h1>",
                status_code=404,
            )

        messages = cur.execute(
            """
            SELECT role, content, created_at
            FROM conversation_message
            WHERE conversation_id = ?
            ORDER BY created_at
            """,
            (conversation_id,),
        ).fetchall()

        summary = conv["summary"]
        if not summary:
            summary = generate_summary_for_conversation(conversation_id, llm) or ""
            conv = dict(conv)
            conv["summary"] = summary

        conn.close()

        processed_msgs = []
        for m in messages:
            role = m["role"]
            raw = m["content"] or ""
            created_at = m["created_at"] or ""

            display_text = raw
            tools = []
            chunk_count = None

            if role == "assistant" and raw.lstrip().startswith("data:"):
                simp = simplify_sse_message(raw)
                display_text = simp["display_text"]
                tools = simp["tools"]
                chunk_count = simp["chunk_count"]

            max_len = 800
            if len(display_text) > max_len:
                display_text = display_text[:max_len] + "\n\n（内容较长，已截断，详见原始流）"

            processed_msgs.append(
                {
                    "role": role,
                    "created_at": created_at,
                    "display_text": display_text,
                    "raw": raw,
                    "tools": tools,
                    "chunk_count": chunk_count,
                }
            )

        summary_html = f"""
        <div class="card">
          <div class="card-header">
            <div class="card-title">对话详情</div>
            <div>
              <span class="tag-pill">
                <span class="tag-dot {'green' if not conv['has_error'] else 'red'}"></span>
                {"正常" if not conv["has_error"] else "有错误"}
              </span>
            </div>
          </div>
          <div class="meta-list">
            <div><span class="meta-label">Conversation ID：</span>{html_escape(conv["id"])}</div>
            <div><span class="meta-label">用户：</span>{html_escape(conv["user_id"] or "")}</div>
            <div><span class="meta-label">来源：</span>{html_escape(conv["source"] or "")}</div>
            <div><span class="meta-label">开始时间：</span>{html_escape(conv["started_at"] or "")}</div>
            <div><span class="meta-label">结束时间：</span>{html_escape(conv["ended_at"] or "")}</div>
          </div>
          <div style="margin-top:10px; font-size:13px;">
            <span class="meta-label">摘要：</span>{html_escape(conv.get("summary") or "（暂无摘要）")}
          </div>
        </div>
        """

        msg_html_list = []
        for msg in processed_msgs:
            role = msg["role"]
            created_at = msg["created_at"]
            tools = msg["tools"]
            chunk_count = msg["chunk_count"]

            esc_display = html_escape(msg["display_text"]).replace("\n", "<br/>")
            esc_raw = html_escape(msg["raw"])

            if role == "user":
                row_class = "msg-row user"
                bubble_class = "msg-bubble user"
                label = "User"
            elif role == "assistant":
                row_class = "msg-row assistant"
                bubble_class = "msg-bubble assistant"
                label = "Assistant"
            elif role == "tool":
                row_class = "msg-row tool"
                bubble_class = "msg-bubble tool"
                label = "Tool"
            else:
                row_class = "msg-row system"
                bubble_class = "msg-bubble system"
                label = role or "System"

            tools_html = ""
            if tools:
                chips = "".join(
                    f'<span class="tool-badge">{html_escape(t)}</span>' for t in tools
                )
                tools_html = f'<div style="margin-bottom: 8px;">{chips}</div>'

            details_html = ""
            if role == "assistant" and msg["raw"].lstrip().startswith("data:"):
                chunk_info = f"（约 {chunk_count} 个 chunk）" if chunk_count is not None else ""
                details_html = f"""
                <details>
                  <summary>查看原始数据流 {chunk_info}</summary>
                  <pre class="raw-block">{esc_raw}</pre>
                </details>
                """

            msg_html = f"""
            <div class="message {role}">
              <div class="message-avatar">{label[0].upper()}</div>
              <div class="message-content">
                <div class="msg-meta">{html_escape(created_at)}</div>
                {tools_html.replace('msg-tools', 'msg-tools') if tools_html else ''}
                <div class="message-text">{esc_display}</div>
                {details_html}
              </div>
            </div>
            """
            msg_html_list.append(msg_html)

        # 解析推理步骤和 SQL
        reasoning_steps = []
        sql = None
        for msg in processed_msgs:
            if msg["role"] == "assistant":
                raw_content = msg["raw"]
                # 如果内容是 SSE 流格式，先简化再提取
                if raw_content and raw_content.lstrip().startswith("data:"):
                    simp = simplify_sse_message(raw_content)
                    # 从简化后的文本中提取 SQL
                    sql = extract_sql_from_message(simp["display_text"])
                    # 如果简化后的文本中没有找到，尝试从原始 SSE 流中提取
                    if not sql:
                        # 尝试从 SSE 流的所有行中提取 SQL
                        lines = raw_content.splitlines()
                        for line in lines:
                            if line.strip().startswith("data: "):
                                try:
                                    data_str = line.strip()[6:].strip()
                                    if data_str and data_str != "[DONE]":
                                        data_obj = json.loads(data_str)
                                        # 检查 simple.text 中是否有 SQL
                                        if data_obj.get("simple", {}).get("text"):
                                            text = data_obj["simple"]["text"]
                                            sql = extract_sql_from_message(text)
                                            if sql:
                                                break
                                        # 检查 rich.data.content 中是否有 SQL
                                        if not sql and data_obj.get("rich", {}).get("data", {}).get("content"):
                                            text = data_obj["rich"]["data"]["content"]
                                            sql = extract_sql_from_message(text)
                                            if sql:
                                                break
                                        # 检查 rich.data.message 中是否有 SQL
                                        if not sql and data_obj.get("rich", {}).get("data", {}).get("message"):
                                            text = data_obj["rich"]["data"]["message"]
                                            sql = extract_sql_from_message(text)
                                            if sql:
                                                break
                                        # 检查 rich.data 本身是否是字符串且包含 SQL
                                        if not sql and isinstance(data_obj.get("rich", {}).get("data"), str):
                                            text = data_obj["rich"]["data"]
                                            sql = extract_sql_from_message(text)
                                            if sql:
                                                break
                                except (json.JSONDecodeError, KeyError, TypeError):
                                    pass
                        # 如果还是没找到，尝试在整个原始内容中搜索
                        if not sql:
                            sql = extract_sql_from_message(raw_content)
                else:
                    sql = extract_sql_from_message(raw_content)
                
                reasoning_steps = parse_reasoning_steps(raw_content)
                if reasoning_steps or sql:
                    break

        html_page = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>对话详情 - {html_escape(conv["id"][:30])}</title>
          <style>
            :root {{
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
            }}

            * {{
              box-sizing: border-box;
              margin: 0;
              padding: 0;
            }}

            body {{
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
              background: var(--color-bg);
              color: var(--color-text);
              line-height: 1.6;
            }}

            .page {{
              max-width: 1000px;
              margin: 0 auto;
              padding: 24px 20px;
            }}

            .back-link {{
              margin-bottom: 16px;
            }}

            .back-link a {{
              display: inline-flex;
              align-items: center;
              gap: 6px;
              padding: 8px 12px;
              color: var(--color-text-muted);
              text-decoration: none;
              font-size: 13px;
              border-radius: var(--radius);
              transition: all 0.2s;
            }}

            .back-link a:hover {{
              background: var(--color-surface);
              color: var(--color-accent);
            }}

            .card {{
              background: var(--color-surface);
              border: 1px solid var(--color-border);
              border-radius: var(--radius-lg);
              padding: 20px;
              box-shadow: var(--shadow-sm);
              margin-bottom: 16px;
            }}

            .card-header {{
              display: flex;
              justify-content: space-between;
              align-items: center;
              margin-bottom: 16px;
            }}

            .card-title {{
              font-size: 20px;
              font-weight: 600;
            }}

            .status-badge {{
              display: inline-flex;
              align-items: center;
              padding: 4px 12px;
              border-radius: 12px;
              font-size: 12px;
              font-weight: 500;
            }}

            .status-badge.ok {{
              background: #f0fdf4;
              color: #15803d;
              border: 1px solid #bbf7d0;
            }}

            .status-badge.error {{
              background: #fef2f2;
              color: #b91c1c;
              border: 1px solid #fecaca;
            }}

            .meta-list {{
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
              gap: 12px;
              font-size: 13px;
              margin-bottom: 12px;
            }}

            .meta-item {{
              display: flex;
              flex-direction: column;
              gap: 4px;
            }}

            .meta-label {{
              color: var(--color-text-muted);
              font-size: 12px;
            }}

            .meta-value {{
              color: var(--color-text);
              font-weight: 500;
              word-break: break-all;
            }}

            .summary-box {{
              margin-top: 12px;
              padding: 12px;
              background: var(--color-bg);
              border-radius: var(--radius);
              font-size: 13px;
              line-height: 1.6;
            }}

            .reasoning-panel {{
              margin-top: 12px;
              padding: 12px;
              background: #f8fafc;
              border-radius: var(--radius);
              border-left: 3px solid var(--color-accent);
            }}

            .reasoning-title {{
              font-size: 12px;
              font-weight: 600;
              color: var(--color-text-muted);
              margin-bottom: 8px;
              text-transform: uppercase;
            }}

            .reasoning-steps {{
              display: flex;
              flex-direction: column;
              gap: 8px;
            }}

            .reasoning-step {{
              display: flex;
              gap: 8px;
              font-size: 13px;
            }}

            .step-number {{
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
            }}

            .step-text {{
              flex: 1;
              color: var(--color-text);
            }}

            .sql-block {{
              margin-top: 12px;
              padding: 12px;
              background: #1e293b;
              border-radius: var(--radius);
              overflow-x: auto;
            }}

            .sql-code {{
              font-family: "Monaco", "Menlo", "Consolas", monospace;
              font-size: 12px;
              color: #e2e8f0;
              line-height: 1.5;
            }}

            .chat-container {{
              display: flex;
              flex-direction: column;
              gap: 16px;
            }}

            .message {{
              display: flex;
              gap: 12px;
              max-width: 85%;
            }}

            .message.user {{
              align-self: flex-start;
            }}

            .message.assistant {{
              align-self: flex-end;
              margin-left: auto;
            }}

            .message-avatar {{
              width: 32px;
              height: 32px;
              border-radius: 50%;
              display: flex;
              align-items: center;
              justify-content: center;
              font-weight: 600;
              font-size: 14px;
              flex-shrink: 0;
            }}

            .message.user .message-avatar {{
              background: var(--color-accent);
              color: white;
            }}

            .message.assistant .message-avatar {{
              background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
              color: white;
            }}

            .message-content {{
              flex: 1;
              background: var(--color-surface);
              border: 1px solid var(--color-border);
              border-radius: var(--radius-lg);
              padding: 12px 16px;
              box-shadow: var(--shadow-sm);
            }}

            .message.user .message-content {{
              background: #eff6ff;
              border-color: #bfdbfe;
            }}

            .message-text {{
              font-size: 14px;
              line-height: 1.6;
              white-space: pre-wrap;
              word-break: break-word;
            }}

            .msg-meta {{
              font-size: 11px;
              color: var(--color-text-muted);
              margin-bottom: 6px;
            }}

            .tool-badge {{
              display: inline-block;
              padding: 2px 8px;
              background: #fef3c7;
              color: #92400e;
              border-radius: 12px;
              font-size: 11px;
              margin-right: 6px;
              margin-bottom: 4px;
            }}

            details {{
              margin-top: 8px;
              font-size: 12px;
            }}

            details summary {{
              cursor: pointer;
              color: var(--color-text-muted);
              padding: 4px 0;
            }}

            .raw-block {{
              white-space: pre-wrap;
              font-size: 11px;
              background: #f9fafb;
              border-radius: var(--radius);
              padding: 8px;
              max-height: 300px;
              overflow: auto;
              border: 1px solid var(--color-border);
              margin-top: 8px;
              font-family: monospace;
            }}
          </style>
        </head>
        <body>
          <div class="page">
            <div class="back-link">
              <a href="/logs">← 返回对话列表</a>
            </div>

            <div class="card">
              <div class="card-header">
                <div class="card-title">对话详情</div>
                <span class="status-badge {"error" if conv["has_error"] else "ok"}">
                  {"有错误" if conv["has_error"] else "正常"}
                </span>
              </div>
              <div class="meta-list">
                <div class="meta-item">
                  <div class="meta-label">会话 ID</div>
                  <div class="meta-value" style="font-family: monospace; font-size: 11px;">{html_escape(conv["id"])}</div>
                </div>
                <div class="meta-item">
                  <div class="meta-label">用户</div>
                  <div class="meta-value">{html_escape(conv["user_id"] or "")}</div>
                </div>
                <div class="meta-item">
                  <div class="meta-label">来源</div>
                  <div class="meta-value">{html_escape(conv["source"] or "")}</div>
                </div>
                <div class="meta-item">
                  <div class="meta-label">开始时间</div>
                  <div class="meta-value">{html_escape(conv["started_at"] or "")}</div>
                </div>
                <div class="meta-item">
                  <div class="meta-label">结束时间</div>
                  <div class="meta-value">{html_escape(conv["ended_at"] or "")}</div>
                </div>
              </div>
              <div class="summary-box">
                <div class="meta-label" style="margin-bottom: 6px;">摘要</div>
                {html_escape(conv.get("summary") or "（暂无摘要）")}
              </div>
              {f'''
              <div class="reasoning-panel">
                <div class="reasoning-title">AI 推理过程</div>
                <div class="reasoning-steps">
                  {''.join([
                    f'''
                    <div class="reasoning-step">
                      <div class="step-number">{step["number"]}</div>
                      <div class="step-text">{html_escape(step["text"])}</div>
                    </div>
                    '''
                    for step in reasoning_steps
                  ])}
                </div>
              </div>
              ''' if reasoning_steps else ''}
              {f'''
              <div class="sql-block">
                <div class="sql-block-header" style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: #0f172a; border-bottom: 1px solid #334155;">
                  <span style="font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase;">SQL 查询</span>
                  <button class="sql-copy-btn" onclick="copySqlToClipboard(\\'{html_escape(sql)}\\')" style="padding: 4px 8px; background: #4a5568; color: #e2e8f0; border: none; border-radius: 4px; cursor: pointer; font-size: 11px; transition: background 0.2s;" onmouseover="this.style.background=\\'#64748b\\'" onmouseout="this.style.background=\\'#4a5568\\'" title="复制 SQL">📋 复制</button>
                </div>
                <div class="sql-code" id="sql-code-{html_escape(conversation_id)}">{html_escape(sql)}</div>
              </div>
              <script>
                function copySqlToClipboard(sql) {{
                  navigator.clipboard.writeText(sql).then(() => {{
                    alert('SQL 已复制到剪贴板');
                  }}).catch(() => {{
                    alert('复制失败');
                  }});
                }}
              </script>
              ''' if sql else ''}
            </div>

            <div class="card">
              <div class="card-title" style="margin-bottom: 16px;">消息时间轴</div>
              <div class="chat-container">
                {''.join(msg_html_list)}
              </div>
            </div>
          </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_page)

    return router

