"""
会话记忆管理服务。

支持：
- 短期记忆：最近 N 轮对话
- 当前上下文：SQL、结果、提到的实体
- 临时事实：用户确认的信息
- 长期记忆：本轮关键发现（可选持久化）
"""

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """对话消息。"""
    role: str  # 'user' | 'assistant'
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionContext:
    """会话上下文。"""
    last_sql: Optional[str] = None
    last_result_preview: Optional[str] = None
    last_chart_type: Optional[str] = None
    mentioned_tables: List[str] = field(default_factory=list)
    mentioned_columns: List[str] = field(default_factory=list)
    pending_clarifications: List[str] = field(default_factory=list)


@dataclass
class SessionMemory:
    """
    单个会话的记忆。
    
    包含：
    - 短期记忆：最近 N 轮对话
    - 当前上下文：SQL、结果、提到的实体
    - 临时事实：用户在对话中确认的信息
    - 关键发现：本轮对话的重要结论
    """
    conversation_id: str
    user_id: str
    
    # 短期记忆 - 最近对话
    recent_messages: deque = field(default_factory=lambda: deque(maxlen=10))
    
    # 当前上下文
    context: SessionContext = field(default_factory=SessionContext)
    
    # 临时事实（用户确认的信息，如 "用户说的Q1是1-3月"）
    temp_facts: Dict[str, Any] = field(default_factory=dict)
    
    # 关键发现（本轮对话的重要结论）
    key_findings: List[str] = field(default_factory=list)
    
    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_active: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """添加消息到短期记忆。"""
        msg = Message(role=role, content=content, metadata=metadata or {})
        self.recent_messages.append(msg)
        self.last_active = datetime.now().isoformat()
    
    def update_context(
        self,
        sql: Optional[str] = None,
        result_preview: Optional[str] = None,
        chart_type: Optional[str] = None,
        tables: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
    ) -> None:
        """更新当前上下文。"""
        if sql is not None:
            self.context.last_sql = sql
        if result_preview is not None:
            self.context.last_result_preview = result_preview
        if chart_type is not None:
            self.context.last_chart_type = chart_type
        if tables:
            self.context.mentioned_tables = list(set(self.context.mentioned_tables + tables))
        if columns:
            self.context.mentioned_columns = list(set(self.context.mentioned_columns + columns))
        self.last_active = datetime.now().isoformat()
    
    def add_temp_fact(self, key: str, value: Any) -> None:
        """添加临时事实。"""
        self.temp_facts[key] = value
        self.last_active = datetime.now().isoformat()
    
    def add_finding(self, finding: str) -> None:
        """添加关键发现。"""
        if finding not in self.key_findings:
            self.key_findings.append(finding)
        self.last_active = datetime.now().isoformat()
    
    def add_clarification(self, question: str) -> None:
        """添加待澄清问题。"""
        if question not in self.context.pending_clarifications:
            self.context.pending_clarifications.append(question)
    
    def resolve_clarification(self, question: str) -> None:
        """解决澄清问题。"""
        if question in self.context.pending_clarifications:
            self.context.pending_clarifications.remove(question)
    
    def get_context_prompt(self, include_messages: bool = True) -> str:
        """
        生成上下文提示（用于增强 LLM 理解）。
        
        Args:
            include_messages: 是否包含最近对话
        
        Returns:
            格式化的上下文提示字符串
        """
        parts = []
        
        # 最近对话
        if include_messages and self.recent_messages:
            parts.append("## 最近对话")
            for msg in list(self.recent_messages)[-5:]:  # 最近5轮
                content_preview = msg.content[:150] + "..." if len(msg.content) > 150 else msg.content
                parts.append(f"**{msg.role}**: {content_preview}")
        
        # 当前 SQL 上下文
        if self.context.last_sql:
            parts.append(f"\n## 上一条 SQL\n```sql\n{self.context.last_sql}\n```")
        
        # 结果预览
        if self.context.last_result_preview:
            parts.append(f"\n## 上次结果预览\n{self.context.last_result_preview}")
        
        # 图表类型
        if self.context.last_chart_type:
            parts.append(f"\n## 当前图表类型: {self.context.last_chart_type}")
        
        # 提到的表和字段
        if self.context.mentioned_tables:
            parts.append(f"\n## 涉及的表: {', '.join(self.context.mentioned_tables)}")
        if self.context.mentioned_columns:
            parts.append(f"\n## 涉及的字段: {', '.join(self.context.mentioned_columns)}")
        
        # 临时事实
        if self.temp_facts:
            parts.append("\n## 已确认的信息")
            for k, v in self.temp_facts.items():
                parts.append(f"- {k}: {v}")
        
        # 关键发现
        if self.key_findings:
            parts.append("\n## 本轮关键发现")
            for finding in self.key_findings[-5:]:  # 最近5条
                parts.append(f"- {finding}")
        
        # 待澄清问题
        if self.context.pending_clarifications:
            parts.append("\n## 待澄清问题")
            for q in self.context.pending_clarifications:
                parts.append(f"- {q}")
        
        return "\n".join(parts) if parts else ""
    
    def get_followup_context(self) -> Dict[str, Any]:
        """获取追问所需的上下文信息。"""
        return {
            "last_sql": self.context.last_sql,
            "last_chart_type": self.context.last_chart_type,
            "mentioned_tables": self.context.mentioned_tables,
            "mentioned_columns": self.context.mentioned_columns,
            "temp_facts": self.temp_facts,
            "has_result": self.context.last_result_preview is not None,
        }
    
    def clear(self) -> None:
        """清除会话记忆。"""
        self.recent_messages.clear()
        self.context = SessionContext()
        self.temp_facts.clear()
        self.key_findings.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "recent_messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "metadata": m.metadata,
                }
                for m in self.recent_messages
            ],
            "context": {
                "last_sql": self.context.last_sql,
                "last_result_preview": self.context.last_result_preview,
                "last_chart_type": self.context.last_chart_type,
                "mentioned_tables": self.context.mentioned_tables,
                "mentioned_columns": self.context.mentioned_columns,
                "pending_clarifications": self.context.pending_clarifications,
            },
            "temp_facts": self.temp_facts,
            "key_findings": self.key_findings,
            "created_at": self.created_at,
            "last_active": self.last_active,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMemory":
        """从字典反序列化。"""
        session = cls(
            conversation_id=data["conversation_id"],
            user_id=data["user_id"],
        )
        session.created_at = data.get("created_at", session.created_at)
        session.last_active = data.get("last_active", session.last_active)
        
        # 恢复消息
        for msg_data in data.get("recent_messages", []):
            msg = Message(
                role=msg_data["role"],
                content=msg_data["content"],
                timestamp=msg_data.get("timestamp", ""),
                metadata=msg_data.get("metadata", {}),
            )
            session.recent_messages.append(msg)
        
        # 恢复上下文
        ctx_data = data.get("context", {})
        session.context.last_sql = ctx_data.get("last_sql")
        session.context.last_result_preview = ctx_data.get("last_result_preview")
        session.context.last_chart_type = ctx_data.get("last_chart_type")
        session.context.mentioned_tables = ctx_data.get("mentioned_tables", [])
        session.context.mentioned_columns = ctx_data.get("mentioned_columns", [])
        session.context.pending_clarifications = ctx_data.get("pending_clarifications", [])
        
        # 恢复临时事实和发现
        session.temp_facts = data.get("temp_facts", {})
        session.key_findings = data.get("key_findings", [])
        
        return session


class SessionMemoryManager:
    """
    会话记忆管理器。
    
    管理多个会话的记忆，支持：
    - 创建/获取会话记忆
    - 会话超时清理
    - 可选的持久化
    """
    
    def __init__(
        self,
        max_sessions: int = 1000,
        session_timeout_hours: int = 24,
    ):
        """
        初始化会话记忆管理器。
        
        Args:
            max_sessions: 最大会话数
            session_timeout_hours: 会话超时时间（小时）
        """
        self._sessions: Dict[str, SessionMemory] = {}
        self._max_sessions = max_sessions
        self._session_timeout_hours = session_timeout_hours
    
    def get_or_create(
        self,
        conversation_id: str,
        user_id: str,
    ) -> SessionMemory:
        """获取或创建会话记忆。"""
        if conversation_id not in self._sessions:
            # 清理过期会话
            self._cleanup_expired()
            
            # 如果超过最大数量，清理最旧的
            if len(self._sessions) >= self._max_sessions:
                self._cleanup_oldest()
            
            self._sessions[conversation_id] = SessionMemory(
                conversation_id=conversation_id,
                user_id=user_id,
            )
            logger.debug(f"Created new session memory: {conversation_id}")
        
        return self._sessions[conversation_id]
    
    def get(self, conversation_id: str) -> Optional[SessionMemory]:
        """获取会话记忆（如果存在）。"""
        return self._sessions.get(conversation_id)
    
    def remove(self, conversation_id: str) -> bool:
        """移除会话记忆。"""
        if conversation_id in self._sessions:
            del self._sessions[conversation_id]
            logger.debug(f"Removed session memory: {conversation_id}")
            return True
        return False
    
    def clear_all(self) -> int:
        """清除所有会话记忆。"""
        count = len(self._sessions)
        self._sessions.clear()
        logger.info(f"Cleared all {count} session memories")
        return count
    
    def _cleanup_expired(self) -> int:
        """清理过期会话。"""
        from datetime import timedelta
        
        now = datetime.now()
        cutoff = now - timedelta(hours=self._session_timeout_hours)
        cutoff_str = cutoff.isoformat()
        
        expired = [
            cid for cid, session in self._sessions.items()
            if session.last_active < cutoff_str
        ]
        
        for cid in expired:
            del self._sessions[cid]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
        
        return len(expired)
    
    def _cleanup_oldest(self, count: int = 100) -> int:
        """清理最旧的会话。"""
        if not self._sessions:
            return 0
        
        # 按最后活跃时间排序
        sorted_sessions = sorted(
            self._sessions.items(),
            key=lambda x: x[1].last_active,
        )
        
        # 删除最旧的
        to_remove = sorted_sessions[:count]
        for cid, _ in to_remove:
            del self._sessions[cid]
        
        logger.info(f"Cleaned up {len(to_remove)} oldest sessions")
        return len(to_remove)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息。"""
        if not self._sessions:
            return {
                "total_sessions": 0,
                "total_messages": 0,
                "users": [],
            }
        
        total_messages = sum(
            len(s.recent_messages) for s in self._sessions.values()
        )
        users = list(set(s.user_id for s in self._sessions.values()))
        
        return {
            "total_sessions": len(self._sessions),
            "total_messages": total_messages,
            "users": users,
            "max_sessions": self._max_sessions,
            "timeout_hours": self._session_timeout_hours,
        }
    
    def get_user_sessions(self, user_id: str) -> List[SessionMemory]:
        """获取用户的所有会话。"""
        return [
            s for s in self._sessions.values()
            if s.user_id == user_id
        ]
    
    def export_session(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """导出会话数据。"""
        session = self._sessions.get(conversation_id)
        return session.to_dict() if session else None
    
    def import_session(self, data: Dict[str, Any]) -> SessionMemory:
        """导入会话数据。"""
        session = SessionMemory.from_dict(data)
        self._sessions[session.conversation_id] = session
        return session


# 全局单例
_session_manager: Optional[SessionMemoryManager] = None


def get_session_manager() -> SessionMemoryManager:
    """获取会话记忆管理器单例。"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionMemoryManager()
    return _session_manager


def init_session_manager(
    max_sessions: int = 1000,
    session_timeout_hours: int = 24,
) -> SessionMemoryManager:
    """初始化会话记忆管理器。"""
    global _session_manager
    _session_manager = SessionMemoryManager(
        max_sessions=max_sessions,
        session_timeout_hours=session_timeout_hours,
    )
    return _session_manager









