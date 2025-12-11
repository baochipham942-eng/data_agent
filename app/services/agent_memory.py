"""
SQLite 持久化的 AgentMemory 实现。

支持：
- 工具使用记录的持久化存储
- 文本记忆的持久化存储
- 基于关键词的相似度搜索
- 自动学习成功的 SQL 查询模式
- 用户隔离的跨会话记忆
- 用户画像和偏好管理
"""

import asyncio
import difflib
import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from vanna.capabilities.agent_memory import (
    AgentMemory,
    TextMemory,
    TextMemorySearchResult,
    ToolMemory,
    ToolMemorySearchResult,
)
from vanna.core.tool import ToolContext

logger = logging.getLogger(__name__)


class SqliteAgentMemory(AgentMemory):
    """
    SQLite 持久化的 Agent Memory 实现。
    
    特点：
    - 数据持久化存储，服务重启不丢失
    - 基于关键词的相似度搜索（Jaccard + difflib）
    - 支持 FIFO 淘汰策略
    - 线程安全
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        max_items: int = 10_000,
    ):
        """
        初始化 SQLite Agent Memory。

        Args:
            db_path: SQLite 数据库文件路径
            max_items: 最大记忆数量，超出后按 FIFO 淘汰
        """
        self.db_path = Path(db_path)
        self._max_items = max_items
        self._lock = asyncio.Lock()
        
        # 确保数据库目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库表
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """初始化数据库表结构。"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 工具使用记忆表（增加用户隔离）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_memory (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                args TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 1,
                metadata TEXT,
                user_id TEXT DEFAULT 'system',
                access_count INTEGER DEFAULT 1,
                last_accessed DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 文本记忆表（增加用户隔离）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS text_memory (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                user_id TEXT DEFAULT 'system',
                memory_type TEXT DEFAULT 'general',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 用户画像表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                user_id TEXT PRIMARY KEY,
                nickname TEXT,
                preferences TEXT,
                focus_dimensions TEXT,
                frequent_patterns TEXT,
                expertise_level TEXT DEFAULT 'intermediate',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 用户查询历史（用于学习偏好）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                query_text TEXT NOT NULL,
                query_type TEXT,
                chart_type TEXT,
                dimensions TEXT,
                metrics TEXT,
                time_range TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 为现有表添加新字段（兼容旧数据）- 必须在创建索引之前执行
        self._migrate_add_columns(cursor)

        # 创建索引（在迁移后执行，确保字段存在）
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tool_memory_tool_name 
            ON tool_memory(tool_name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tool_memory_success 
            ON tool_memory(success)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tool_memory_created_at 
            ON tool_memory(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tool_memory_user_id 
            ON tool_memory(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_text_memory_created_at 
            ON text_memory(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_text_memory_user_id 
            ON text_memory(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_history_user_id 
            ON user_query_history(user_id)
        """)

        conn.commit()
        conn.close()
    
    def _migrate_add_columns(self, cursor) -> None:
        """迁移：为现有表添加新字段。"""
        # 为 tool_memory 添加新字段
        migrations = [
            ("tool_memory", "user_id", "TEXT DEFAULT 'system'"),
            ("tool_memory", "access_count", "INTEGER DEFAULT 1"),
            ("tool_memory", "last_accessed", "DATETIME"),
            ("text_memory", "user_id", "TEXT DEFAULT 'system'"),
            ("text_memory", "memory_type", "TEXT DEFAULT 'general'"),
        ]
        
        for table, column, col_type in migrations:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            except sqlite3.OperationalError:
                pass  # 字段已存在

    @staticmethod
    def _now_iso() -> str:
        """获取当前 ISO 格式时间戳。"""
        return datetime.now().isoformat()

    @staticmethod
    def _normalize(text: str) -> str:
        """规范化文本：小写 + 合并空白。"""
        return " ".join(text.lower().split())

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """简单分词：按空格分割。"""
        return set(text.lower().split())

    @classmethod
    def _similarity(cls, a: str, b: str) -> float:
        """
        计算两个字符串的相似度。
        使用 Jaccard 相似度和 difflib 比率的最大值。
        """
        a_norm, b_norm = cls._normalize(a), cls._normalize(b)

        # Jaccard 相似度
        ta, tb = cls._tokenize(a_norm), cls._tokenize(b_norm)
        if not ta and not tb:
            jaccard = 1.0
        elif not ta or not tb:
            jaccard = 0.0
        else:
            jaccard = len(ta & tb) / max(1, len(ta | tb))

        # difflib 比率
        ratio = difflib.SequenceMatcher(None, a_norm, b_norm).ratio()

        return max(jaccard, ratio)

    async def _enforce_limit(self, conn: sqlite3.Connection, table: str) -> None:
        """强制执行最大记录数限制（FIFO 淘汰）。"""
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]

        if count > self._max_items:
            overflow = count - self._max_items
            cursor.execute(f"""
                DELETE FROM {table} 
                WHERE id IN (
                    SELECT id FROM {table} 
                    ORDER BY created_at ASC 
                    LIMIT ?
                )
            """, (overflow,))
            conn.commit()

    async def save_tool_usage(
        self,
        question: str,
        tool_name: str,
        args: Dict[str, Any],
        context: ToolContext,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: str = "system",
    ) -> None:
        """保存工具使用记录（支持用户隔离）。"""
        memory_id = str(uuid.uuid4())
        timestamp = self._now_iso()

        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO tool_memory (id, question, tool_name, args, timestamp, success, metadata, user_id, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory_id,
                question,
                tool_name,
                json.dumps(args, ensure_ascii=False),
                timestamp,
                1 if success else 0,
                json.dumps(metadata, ensure_ascii=False) if metadata else None,
                user_id,
                timestamp,
            ))

            conn.commit()
            await self._enforce_limit(conn, "tool_memory")
            conn.close()

    async def save_text_memory(
        self, content: str, context: ToolContext,
        user_id: str = "system",
        memory_type: str = "general",
    ) -> TextMemory:
        """保存文本记忆（支持用户隔离）。"""
        memory_id = str(uuid.uuid4())
        timestamp = self._now_iso()

        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO text_memory (id, content, timestamp, user_id, memory_type)
                VALUES (?, ?, ?, ?, ?)
            """, (memory_id, content, timestamp, user_id, memory_type))

            conn.commit()
            await self._enforce_limit(conn, "text_memory")
            conn.close()

        return TextMemory(
            memory_id=memory_id,
            content=content,
            timestamp=timestamp,
        )

    async def search_similar_usage(
        self,
        question: str,
        context: ToolContext,
        *,
        limit: int = 10,
        similarity_threshold: float = 0.5,
        tool_name_filter: Optional[str] = None,
        user_id: Optional[str] = None,
        include_system: bool = True,
    ) -> List[ToolMemorySearchResult]:
        """搜索相似的工具使用记录（支持用户隔离）。
        
        Args:
            user_id: 用户ID，如果提供则优先搜索该用户的记忆
            include_system: 是否包含系统级记忆（默认True）
        """
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 构建查询（支持用户隔离）
            query = "SELECT * FROM tool_memory WHERE success = 1"
            params: List[Any] = []

            if user_id:
                if include_system:
                    query += " AND (user_id = ? OR user_id = 'system')"
                else:
                    query += " AND user_id = ?"
                params.append(user_id)

            if tool_name_filter:
                query += " AND tool_name = ?"
                params.append(tool_name_filter)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # 计算相似度并排序
            results: List[tuple[ToolMemory, float, str]] = []
            matched_ids = []
            for row in rows:
                score = self._similarity(question, row["question"])
                if score >= similarity_threshold:
                    memory = ToolMemory(
                        memory_id=row["id"],
                        question=row["question"],
                        tool_name=row["tool_name"],
                        args=json.loads(row["args"]),
                        timestamp=row["timestamp"],
                        success=bool(row["success"]),
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    )
                    # 用户自己的记忆优先级更高
                    user_boost = 0.1 if user_id and row["user_id"] == user_id else 0
                    results.append((memory, min(score + user_boost, 1.0), row["id"]))
                    matched_ids.append(row["id"])

            # 按相似度排序
            results.sort(key=lambda x: x[1], reverse=True)
            
            # 更新访问计数
            if matched_ids:
                placeholders = ",".join(["?" for _ in matched_ids[:limit]])
                cursor.execute(f"""
                    UPDATE tool_memory 
                    SET access_count = access_count + 1, last_accessed = ?
                    WHERE id IN ({placeholders})
                """, [self._now_iso()] + matched_ids[:limit])
                conn.commit()
            
            conn.close()

            # 构建返回结果
            return [
                ToolMemorySearchResult(memory=m, similarity_score=s, rank=idx)
                for idx, (m, s, _) in enumerate(results[:limit], start=1)
            ]

    async def search_text_memories(
        self,
        query: str,
        context: ToolContext,
        *,
        limit: int = 10,
        similarity_threshold: float = 0.5,
        user_id: Optional[str] = None,
        include_system: bool = True,
        memory_type: Optional[str] = None,
    ) -> List[TextMemorySearchResult]:
        """搜索文本记忆（支持用户隔离）。"""
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 构建查询
            sql = "SELECT * FROM text_memory WHERE 1=1"
            params: List[Any] = []
            
            if user_id:
                if include_system:
                    sql += " AND (user_id = ? OR user_id = 'system')"
                else:
                    sql += " AND user_id = ?"
                params.append(user_id)
            
            if memory_type:
                sql += " AND memory_type = ?"
                params.append(memory_type)

            cursor.execute(sql, params)
            rows = cursor.fetchall()
            conn.close()

            # 计算相似度并排序
            results: List[tuple[TextMemory, float]] = []
            for row in rows:
                score = self._similarity(query, row["content"])
                if score >= similarity_threshold:
                    memory = TextMemory(
                        memory_id=row["id"],
                        content=row["content"],
                        timestamp=row["timestamp"],
                    )
                    # 用户自己的记忆优先级更高
                    user_boost = 0.1 if user_id and row["user_id"] == user_id else 0
                    results.append((memory, min(score + user_boost, 1.0)))

            # 按相似度排序
            results.sort(key=lambda x: x[1], reverse=True)

            # 构建返回结果
            return [
                TextMemorySearchResult(memory=m, similarity_score=s, rank=idx)
                for idx, (m, s) in enumerate(results[:limit], start=1)
            ]

    async def get_recent_memories(
        self, context: ToolContext, limit: int = 10
    ) -> List[ToolMemory]:
        """获取最近的工具使用记录。"""
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM tool_memory 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            conn.close()

            return [
                ToolMemory(
                    memory_id=row["id"],
                    question=row["question"],
                    tool_name=row["tool_name"],
                    args=json.loads(row["args"]),
                    timestamp=row["timestamp"],
                    success=bool(row["success"]),
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                )
                for row in rows
            ]

    async def get_recent_text_memories(
        self, context: ToolContext, limit: int = 10
    ) -> List[TextMemory]:
        """获取最近的文本记忆。"""
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM text_memory 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            conn.close()

            return [
                TextMemory(
                    memory_id=row["id"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                )
                for row in rows
            ]

    async def delete_by_id(self, context: ToolContext, memory_id: str) -> bool:
        """删除指定 ID 的工具记忆。"""
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM tool_memory WHERE id = ?", (memory_id,))
            deleted = cursor.rowcount > 0

            conn.commit()
            conn.close()
            return deleted

    async def delete_text_memory(self, context: ToolContext, memory_id: str) -> bool:
        """删除指定 ID 的文本记忆。"""
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM text_memory WHERE id = ?", (memory_id,))
            deleted = cursor.rowcount > 0

            conn.commit()
            conn.close()
            return deleted

    async def clear_memories(
        self,
        context: ToolContext,
        tool_name: Optional[str] = None,
        before_date: Optional[str] = None,
    ) -> int:
        """清除记忆。"""
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            total_deleted = 0

            # 清除工具记忆
            tool_query = "DELETE FROM tool_memory WHERE 1=1"
            tool_params: List[Any] = []

            if tool_name:
                tool_query += " AND tool_name = ?"
                tool_params.append(tool_name)

            if before_date:
                tool_query += " AND timestamp < ?"
                tool_params.append(before_date)

            cursor.execute(tool_query, tool_params)
            total_deleted += cursor.rowcount

            # 清除文本记忆（仅当没有指定 tool_name 时）
            if not tool_name:
                text_query = "DELETE FROM text_memory WHERE 1=1"
                text_params: List[Any] = []

                if before_date:
                    text_query += " AND timestamp < ?"
                    text_params.append(before_date)

                cursor.execute(text_query, text_params)
                total_deleted += cursor.rowcount

            conn.commit()
            conn.close()
            return total_deleted

    async def get_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """获取记忆统计信息（可按用户过滤）。"""
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            if user_id:
                cursor.execute("SELECT COUNT(*) FROM tool_memory WHERE user_id = ? OR user_id = 'system'", (user_id,))
                tool_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM tool_memory WHERE (user_id = ? OR user_id = 'system') AND success = 1", (user_id,))
                success_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM text_memory WHERE user_id = ? OR user_id = 'system'", (user_id,))
                text_count = cursor.fetchone()[0]
                cursor.execute("""
                    SELECT tool_name, COUNT(*) as count 
                    FROM tool_memory 
                    WHERE user_id = ? OR user_id = 'system'
                    GROUP BY tool_name
                """, (user_id,))
            else:
                cursor.execute("SELECT COUNT(*) FROM tool_memory")
                tool_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM tool_memory WHERE success = 1")
                success_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM text_memory")
                text_count = cursor.fetchone()[0]
                cursor.execute("""
                    SELECT tool_name, COUNT(*) as count 
                    FROM tool_memory 
                    GROUP BY tool_name
                """)
            
            tool_breakdown = {row["tool_name"]: row["count"] for row in cursor.fetchall()}
            
            # 用户分布统计
            cursor.execute("""
                SELECT user_id, COUNT(*) as count 
                FROM tool_memory 
                GROUP BY user_id
            """)
            user_breakdown = {row["user_id"]: row["count"] for row in cursor.fetchall()}

            conn.close()

            return {
                "total_tool_memories": tool_count,
                "successful_tool_memories": success_count,
                "total_text_memories": text_count,
                "tool_breakdown": tool_breakdown,
                "user_breakdown": user_breakdown,
            }


class UserProfileService:
    """用户画像服务 - 管理用户偏好和学习用户行为模式。"""
    
    def __init__(self, agent_memory: SqliteAgentMemory):
        self.agent_memory = agent_memory
        self._lock = asyncio.Lock()
    
    def _get_connection(self) -> sqlite3.Connection:
        return self.agent_memory._get_connection()
    
    def get_nickname_sync(self, user_id: str) -> Optional[str]:
        """同步获取用户昵称（用于在会话创建时快速获取）。"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 【关键修复】先检查表是否存在，避免查询不存在的表
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='user_profile'
            """)
            table_exists = cursor.fetchone()
            
            if not table_exists:
                conn.close()
                return None
            
            cursor.execute("SELECT nickname FROM user_profile WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row and row["nickname"]:
                return row["nickname"]
            return None
        except Exception as e:
            logger.warning(f"获取用户昵称失败: {e}")
            return None
    
    async def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户画像。"""
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_profile WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "user_id": row["user_id"],
                    "nickname": row["nickname"],
                    "preferences": json.loads(row["preferences"]) if row["preferences"] else {},
                    "focus_dimensions": json.loads(row["focus_dimensions"]) if row["focus_dimensions"] else [],
                    "frequent_patterns": json.loads(row["frequent_patterns"]) if row["frequent_patterns"] else [],
                    "expertise_level": row["expertise_level"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            return None
    
    async def create_or_update_profile(
        self,
        user_id: str,
        nickname: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None,
        focus_dimensions: Optional[List[str]] = None,
        expertise_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建或更新用户画像。"""
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 检查是否存在
            cursor.execute("SELECT * FROM user_profile WHERE user_id = ?", (user_id,))
            existing = cursor.fetchone()
            
            now = datetime.now().isoformat()
            
            if existing:
                # 合并更新
                current_prefs = json.loads(existing["preferences"]) if existing["preferences"] else {}
                current_dims = json.loads(existing["focus_dimensions"]) if existing["focus_dimensions"] else []
                
                if preferences:
                    current_prefs.update(preferences)
                if focus_dimensions:
                    current_dims = list(set(current_dims + focus_dimensions))
                
                cursor.execute("""
                    UPDATE user_profile 
                    SET nickname = COALESCE(?, nickname),
                        preferences = ?,
                        focus_dimensions = ?,
                        expertise_level = COALESCE(?, expertise_level),
                        updated_at = ?
                    WHERE user_id = ?
                """, (
                    nickname,
                    json.dumps(current_prefs, ensure_ascii=False),
                    json.dumps(current_dims, ensure_ascii=False),
                    expertise_level,
                    now,
                    user_id,
                ))
            else:
                cursor.execute("""
                    INSERT INTO user_profile (user_id, nickname, preferences, focus_dimensions, expertise_level, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    nickname or user_id,
                    json.dumps(preferences or {}, ensure_ascii=False),
                    json.dumps(focus_dimensions or [], ensure_ascii=False),
                    expertise_level or "intermediate",
                    now,
                    now,
                ))
            
            conn.commit()
            conn.close()
            
            return await self.get_profile(user_id)
    
    async def record_query(
        self,
        user_id: str,
        query_text: str,
        query_type: Optional[str] = None,
        chart_type: Optional[str] = None,
        dimensions: Optional[List[str]] = None,
        metrics: Optional[List[str]] = None,
        time_range: Optional[str] = None,
    ) -> None:
        """记录用户查询，用于学习偏好。"""
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_query_history 
                (user_id, query_text, query_type, chart_type, dimensions, metrics, time_range)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                query_text,
                query_type,
                chart_type,
                json.dumps(dimensions, ensure_ascii=False) if dimensions else None,
                json.dumps(metrics, ensure_ascii=False) if metrics else None,
                time_range,
            ))
            conn.commit()
            conn.close()
    
    async def learn_preferences(self, user_id: str) -> Dict[str, Any]:
        """从历史查询中学习用户偏好。"""
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 统计图表类型偏好
            cursor.execute("""
                SELECT chart_type, COUNT(*) as count
                FROM user_query_history
                WHERE user_id = ? AND chart_type IS NOT NULL
                GROUP BY chart_type
                ORDER BY count DESC
                LIMIT 5
            """, (user_id,))
            chart_prefs = {row["chart_type"]: row["count"] for row in cursor.fetchall()}
            
            # 统计常用维度
            cursor.execute("""
                SELECT dimensions
                FROM user_query_history
                WHERE user_id = ? AND dimensions IS NOT NULL
            """, (user_id,))
            all_dims = []
            for row in cursor.fetchall():
                dims = json.loads(row["dimensions"]) if row["dimensions"] else []
                all_dims.extend(dims)
            
            from collections import Counter
            dim_counts = Counter(all_dims)
            top_dims = [dim for dim, _ in dim_counts.most_common(5)]
            
            # 统计时间范围偏好
            cursor.execute("""
                SELECT time_range, COUNT(*) as count
                FROM user_query_history
                WHERE user_id = ? AND time_range IS NOT NULL
                GROUP BY time_range
                ORDER BY count DESC
                LIMIT 1
            """, (user_id,))
            time_pref = cursor.fetchone()
            
            # 统计查询类型
            cursor.execute("""
                SELECT query_type, COUNT(*) as count
                FROM user_query_history
                WHERE user_id = ? AND query_type IS NOT NULL
                GROUP BY query_type
                ORDER BY count DESC
            """, (user_id,))
            query_types = {row["query_type"]: row["count"] for row in cursor.fetchall()}
            
            conn.close()
            
            # 确定首选图表类型（修复：空字典时max会报错）
            preferred_chart = max(chart_prefs, key=chart_prefs.get) if chart_prefs and len(chart_prefs) > 0 else None
            preferred_time = time_pref["time_range"] if time_pref else None
            
            # 更新用户画像
            preferences = {
                "preferred_chart_type": preferred_chart,
                "preferred_time_range": preferred_time,
                "chart_type_stats": chart_prefs,
                "query_type_stats": query_types,
            }
            
            await self.create_or_update_profile(
                user_id=user_id,
                preferences=preferences,
                focus_dimensions=top_dims,
            )
            
            return {
                "preferences": preferences,
                "focus_dimensions": top_dims,
            }
    
    async def get_user_context_prompt(self, user_id: str) -> str:
        """生成用户上下文提示（用于增强 LLM 回答）。"""
        profile = await self.get_profile(user_id)
        if not profile:
            return ""
        
        parts = ["## 用户偏好信息"]
        
        prefs = profile.get("preferences", {})
        if prefs.get("preferred_chart_type"):
            parts.append(f"- 偏好图表类型: {prefs['preferred_chart_type']}")
        if prefs.get("preferred_time_range"):
            parts.append(f"- 常用时间范围: {prefs['preferred_time_range']}")
        
        if profile.get("focus_dimensions"):
            parts.append(f"- 关注维度: {', '.join(profile['focus_dimensions'])}")
        
        if profile.get("expertise_level"):
            level_desc = {
                "beginner": "初学者，需要详细解释",
                "intermediate": "中级用户，适度解释",
                "advanced": "高级用户，简洁回答即可",
            }
            parts.append(f"- 用户水平: {level_desc.get(profile['expertise_level'], '中级')}")
        
        return "\n".join(parts) if len(parts) > 1 else ""
    
    async def get_query_history(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户查询历史。"""
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM user_query_history
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "id": row["id"],
                    "query_text": row["query_text"],
                    "query_type": row["query_type"],
                    "chart_type": row["chart_type"],
                    "dimensions": json.loads(row["dimensions"]) if row["dimensions"] else None,
                    "metrics": json.loads(row["metrics"]) if row["metrics"] else None,
                    "time_range": row["time_range"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

