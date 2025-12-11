"""
Prompt 配置服务。

提供：
- System Prompt 版本管理
- 不同 Prompt 配置保存和切换
- Prompt 模板管理
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


# 默认的 System Prompt
DEFAULT_SYSTEM_PROMPT = """你是一个数据分析助手，擅长：
1. 把用户的自然语言问题转换为合适的 SQL；
2. 调用 RunSqlTool 执行查询；
3. 在拿到按维度聚合或按时间序列的数据后，调用 VisualizeDataTool 生成图表。

使用约定：
- 当用户在问"趋势 / 变化 / 走势 / 随时间变化"等问题时，优先生成折线图。
- 当用户在问"对比 / 排名 / TopN / 各地区 / 各渠道"等问题时，优先生成柱状图或条形图。
- 当用户在问"占比 / 构成 / 分布"时，可以生成饼图或堆叠柱状图。

回答要求：
- 用中文解释：总量、最高/最低、对比结论、是否有明显变化。
- 告诉用户已经生成了一张图表，可以在界面中进行交互查看（悬停查看数值、缩放等）。
"""


class PromptConfig:
    """Prompt 配置管理"""
    
    def __init__(self, db_path: str | Path):
        """
        初始化 Prompt 配置。
        
        Args:
            db_path: SQLite 数据库路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._init_default_prompts()
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self) -> None:
        """初始化数据库表"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        # Prompt 版本表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS prompt_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                content TEXT NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT 0,
                category TEXT DEFAULT 'system',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, version)
            )
        """)
        
        # Prompt 配置历史（用于记录哪个会话使用了哪个 Prompt）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS prompt_usage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                prompt_name TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                model_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cur.execute("CREATE INDEX IF NOT EXISTS idx_prompt_active ON prompt_versions(is_active)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_prompt_category ON prompt_versions(category)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_usage_conversation ON prompt_usage_history(conversation_id)")
        
        conn.commit()
        conn.close()
    
    def _init_default_prompts(self) -> None:
        """初始化默认 Prompt"""
        default_prompts = [
            {
                "name": "system_prompt",
                "version": "v1.0",
                "content": DEFAULT_SYSTEM_PROMPT,
                "description": "基础版 System Prompt",
                "category": "system",
                "is_active": True,
            },
            {
                "name": "system_prompt",
                "version": "v1.1-detailed",
                "content": DEFAULT_SYSTEM_PROMPT + """

额外说明：
- 在生成 SQL 前，先分析用户问题中的关键词
- 如果用户的问题不清晰，主动询问澄清
- 在回答中引用具体的数字和百分比
- 如果数据量较大，提供 Top 5 或 Top 10 的摘要
""",
                "description": "详细版 - 增加分析步骤",
                "category": "system",
            },
            {
                "name": "system_prompt",
                "version": "v1.2-structured",
                "content": """你是一个专业的数据分析助手。

## 你的能力
1. 将自然语言问题转换为 SQL 查询
2. 执行 SQL 并分析结果
3. 生成数据可视化图表

## 工作流程
1. **理解问题**：分析用户问题，识别关键指标和维度
2. **生成 SQL**：基于数据库 Schema 编写正确的 SQL
3. **执行查询**：使用 RunSqlTool 执行 SQL
4. **分析结果**：解读数据，发现洞察
5. **可视化**：使用 VisualizeDataTool 生成合适的图表

## 图表选择
- 趋势分析 → 折线图
- 对比/排名 → 柱状图
- 占比/分布 → 饼图

## 回答规范
- 使用中文回答
- 包含具体数字和百分比
- 指出数据的关键发现
- 提示用户可以在图表上交互查看详情
""",
                "description": "结构化版 - 更清晰的工作流程",
                "category": "system",
            },
            {
                "name": "judge_prompt",
                "version": "v1.0",
                "content": """你是一个专业的数据分析质量评估专家。请评估 AI 回答的质量。

评分维度（1-5分）：
1. SQL 正确性
2. 结果解读准确性
3. 回答完整性
4. 表达清晰度

请以 JSON 格式输出评估结果。
""",
                "description": "LLM Judge 评估 Prompt",
                "category": "judge",
                "is_active": True,  # v1.0版本默认激活
            },
            # SQL 修复 Prompt
            {
                "name": "sql_fix_prompt",
                "version": "v1.0",
                "content": """你是一个 SQL 专家。用户的 SQL 执行出错了，请帮助修复。

## 数据库 Schema
{schema_context}

## 原始 SQL
```sql
{sql}
```

## 错误信息
{error}

请分析错误原因，并提供修复后的 SQL。只输出修复后的 SQL，不要有额外解释。

修复后的 SQL:
```sql
""",
                "description": "SQL 自动修复 Prompt",
                "category": "sql",
                "is_active": True,  # v1.0版本默认激活
            },
            # SQL 修改 Prompt
            {
                "name": "sql_modify_prompt",
                "version": "v1.0",
                "content": """你是一个 SQL 专家。请根据用户的要求修改已有的 SQL 查询。

## 原 SQL
```sql
{original_sql}
```

## 用户修改要求
{modification_request}

## 数据库 Schema（参考）
{schema_context}

请输出修改后的完整 SQL。只输出 SQL，不要有额外解释。

修改后的 SQL:
```sql
""",
                "description": "SQL 修改 Prompt",
                "category": "sql",
                "is_active": True,  # v1.0版本默认激活
            },
            # 问题改写 Prompt
            {
                "name": "rewrite_prompt",
                "version": "v1.0",
                "content": """你是一个数据分析助手。用户的问题可能引用了之前的对话上下文。
请将用户的问题改写成一个完整、独立的问题。

## 对话上下文
上一个问题: {last_question}
上一个 SQL:
```sql
{last_sql}
```

## 用户当前输入
{current_input}

## 改写规则
1. 如果用户使用了代词（"它"、"这个"、"那些"），替换为具体的实体
2. 如果用户在追问或要求修改，保留原有的查询意图
3. 如果是全新的问题，直接返回原问题

请输出改写后的完整问题。只输出问题本身，不要有任何解释。

改写后的问题:""",
                "description": "问题改写 Prompt",
                "category": "conversation",
                "is_active": True,  # v1.0版本默认激活
            },
            # 意图分类 Prompt
            {
                "name": "intent_classify_prompt",
                "version": "v1.0",
                "content": """你是一个智能助手，需要判断用户的意图类型。

## 上下文
{context}

## 用户输入
{user_input}

## 意图类型说明
- new_query: 新查询（全新的数据分析问题）
- followup: 追问（基于上次结果继续提问）
- correction: 修正（修改上次查询）
- clarification: 澄清（补充信息）
- chitchat: 闲聊

请判断用户输入的意图类型，以 JSON 格式输出：
{{
  "intent": "意图类型",
  "confidence": 0.9,
  "reason": "判断原因"
}}""",
                "description": "意图分类 Prompt",
                "category": "conversation",
                "is_active": True,  # v1.0版本默认激活
            },
            # 表选择 Prompt
            {
                "name": "table_select_prompt",
                "version": "v1.0",
                "content": """你是一个数据库专家。根据用户问题，从以下数据库表中选择最相关的表。

## 数据库表结构
{schema_description}

## 用户问题
{question}

请选择 1-3 个最相关的表，以 JSON 格式输出：
{{
  "tables": [
    {{
      "name": "表名",
      "reason": "选择这个表的原因"
    }}
  ]
}}

只输出 JSON，不要有额外解释。""",
                "description": "智能表选择 Prompt",
                "category": "sql",
                "is_active": True,  # v1.0版本默认激活
            },
            # 摘要生成 Prompt
            {
                "name": "summary_prompt",
                "version": "v1.0",
                "content": """你是一个数据分析平台的对话日志助手。

下面是一轮用户与数据分析 Agent 的对话（已做精简）：
------------------------
{context}
------------------------

请根据上面的对话内容，用 10-30 个中文字总结这次对话的主题。
只输出摘要本身，不要有"摘要："等前缀。""",
                "description": "会话摘要生成 Prompt",
                "category": "utility",
                "is_active": True,  # v1.0版本默认激活
            },
            # 联系专家邮件模板
            {
                "name": "contact_expert_email",
                "version": "v1.0",
                "content": """您好，专家团队：

我在使用 Data Agent 时遇到了问题，希望获得专业指导。

━━━━━━━━━━━━━━━━━━━━━━
📋 问题详情
━━━━━━━━━━━━━━━━━━━━━━

🔹 会话ID：{conversation_id}

🔹 用户问题：{user_question}

🔹 生成的SQL：
{sql}

🔹 AI回复摘要：
{ai_response}

━━━━━━━━━━━━━━━━━━━━━━
📝 我的问题描述
━━━━━━━━━━━━━━━━━━━━━━

（请在此描述您遇到的具体问题或需要的帮助）



━━━━━━━━━━━━━━━━━━━━━━
⏰ 反馈时间：{timestamp}
━━━━━━━━━━━━━━━━━━━━━━""",
                "description": "联系专家邮件模板",
                "category": "email",
                "is_active": True,  # v1.0版本默认激活
            },
        ]
        
        conn = self._get_conn()
        cur = conn.cursor()
        
        for prompt in default_prompts:
            try:
                # 先尝试插入，如果已存在则更新（但保留现有内容，只更新激活状态）
                cur.execute("""
                    INSERT OR IGNORE INTO prompt_versions 
                    (name, version, content, description, category, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    prompt["name"],
                    prompt["version"],
                    prompt["content"],
                    prompt["description"],
                    prompt["category"],
                    prompt.get("is_active", False),
                ))
                
                # 如果是v1.0版本且应该激活，确保激活状态正确
                if prompt.get("is_active", False) and prompt["version"] == "v1.0":
                    cur.execute("""
                        UPDATE prompt_versions 
                        SET is_active = 1 
                        WHERE name = ? AND version = 'v1.0'
                    """, (prompt["name"],))
            except Exception as e:
                logger.debug(f"Skip existing prompt: {e}")
        
        # 确保v1.0版本的所有类型都被激活（如果它们存在）
        # 先取消所有激活状态
        cur.execute("UPDATE prompt_versions SET is_active = 0 WHERE version = 'v1.0'")
        # 然后激活v1.0版本的所有类型
        cur.execute("UPDATE prompt_versions SET is_active = 1 WHERE version = 'v1.0'")
        
        conn.commit()
        conn.close()
    
    # ============ Prompt 版本管理 API ============
    
    def create_prompt(
        self,
        name: str,
        version: str,
        content: str,
        description: Optional[str] = None,
        category: str = "system",
    ) -> int:
        """创建新的 Prompt 版本"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO prompt_versions (name, version, content, description, category)
            VALUES (?, ?, ?, ?, ?)
        """, (name, version, content, description, category))
        
        prompt_id = cur.lastrowid
        conn.commit()
        conn.close()
        return prompt_id
    
    def update_prompt(
        self,
        name: str,
        version: str,
        content: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """更新 Prompt"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        updates = []
        params = []
        
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        
        if not updates:
            return False
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([name, version])
        
        cur.execute(f"""
            UPDATE prompt_versions 
            SET {', '.join(updates)}
            WHERE name = ? AND version = ?
        """, params)
        
        updated = cur.rowcount > 0
        conn.commit()
        conn.close()
        return updated
    
    def get_prompt(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        """获取指定版本的 Prompt"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM prompt_versions WHERE name = ? AND version = ?
        """, (name, version))
        
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return dict(row)
    
    def get_active_prompt(self, name: str) -> Optional[Dict[str, Any]]:
        """获取当前激活的 Prompt"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM prompt_versions 
            WHERE name = ? AND is_active = 1
            ORDER BY updated_at DESC
            LIMIT 1
        """, (name,))
        
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return dict(row)
    
    def set_active_prompt(self, name: str, version: str) -> bool:
        """设置激活的 Prompt 版本"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        # 先取消该名称的所有激活状态
        cur.execute("""
            UPDATE prompt_versions SET is_active = 0 WHERE name = ?
        """, (name,))
        
        # 激活指定版本
        cur.execute("""
            UPDATE prompt_versions SET is_active = 1 
            WHERE name = ? AND version = ?
        """, (name, version))
        
        updated = cur.rowcount > 0
        conn.commit()
        conn.close()
        return updated
    
    def list_prompts(
        self,
        name: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出所有 Prompt"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        conditions = []
        params = []
        
        if name:
            conditions.append("name = ?")
            params.append(name)
        
        if category:
            conditions.append("category = ?")
            params.append(category)
        
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        
        cur.execute(f"""
            SELECT * FROM prompt_versions 
            {where_clause}
            ORDER BY name, is_active DESC, created_at DESC
        """, params)
        
        rows = cur.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def delete_prompt(self, name: str, version: str) -> bool:
        """删除 Prompt（不允许删除激活的版本）"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        # 检查是否激活
        cur.execute("""
            SELECT is_active FROM prompt_versions WHERE name = ? AND version = ?
        """, (name, version))
        
        row = cur.fetchone()
        if row and row["is_active"]:
            conn.close()
            return False  # 不允许删除激活的版本
        
        cur.execute("""
            DELETE FROM prompt_versions WHERE name = ? AND version = ?
        """, (name, version))
        
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    
    # ============ 使用记录 API ============
    
    def record_usage(
        self,
        conversation_id: str,
        prompt_name: str,
        prompt_version: str,
        model_name: Optional[str] = None,
    ) -> None:
        """记录 Prompt 使用"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO prompt_usage_history 
            (conversation_id, prompt_name, prompt_version, model_name)
            VALUES (?, ?, ?, ?)
        """, (conversation_id, prompt_name, prompt_version, model_name))
        
        conn.commit()
        conn.close()
    
    def get_conversation_prompt(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """获取会话使用的 Prompt"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM prompt_usage_history 
            WHERE conversation_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (conversation_id,))
        
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return dict(row)
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        # 各版本使用次数
        cur.execute("""
            SELECT prompt_name, prompt_version, model_name, COUNT(*) as count
            FROM prompt_usage_history
            GROUP BY prompt_name, prompt_version, model_name
            ORDER BY count DESC
        """)
        
        usage = [dict(row) for row in cur.fetchall()]
        
        # 总数
        cur.execute("SELECT COUNT(*) FROM prompt_usage_history")
        total = cur.fetchone()[0]
        
        conn.close()
        
        return {
            "total_conversations": total,
            "usage_by_version": usage,
        }
    
    def get_stats(self) -> Dict[str, int]:
        """获取配置统计"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM prompt_versions")
        total = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(DISTINCT name) FROM prompt_versions")
        prompt_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM prompt_versions WHERE is_active = 1")
        active_count = cur.fetchone()[0]
        
        conn.close()
        
        return {
            "total_versions": total,
            "prompt_count": prompt_count,
            "active_count": active_count,
        }

