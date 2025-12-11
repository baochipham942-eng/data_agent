"""
业务知识库服务。

提供业务术语、字段映射、时间规则的管理功能。
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class BusinessKnowledge:
    """业务知识库管理"""
    
    def __init__(self, db_path: str | Path):
        """
        初始化业务知识库。
        
        Args:
            db_path: SQLite 数据库路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self) -> None:
        """初始化数据库表"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        # 业务术语表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS business_terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL UNIQUE,
                term_type TEXT NOT NULL,
                description TEXT NOT NULL,
                example TEXT,
                priority INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 字段映射表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS field_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias TEXT NOT NULL UNIQUE,
                standard_name TEXT NOT NULL,
                table_name TEXT,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 时间规则表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS time_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL UNIQUE,
                rule_type TEXT NOT NULL,
                value TEXT NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        
        # 初始化默认数据
        self._init_default_data()
    
    def _init_default_data(self) -> None:
        """初始化默认的业务知识"""
        # 默认业务术语
        default_terms = [
            ("日活", "metric", "日活跃用户数，指当天访问过应用的独立用户数", "日活 1000 万"),
            ("PV", "metric", "页面浏览量，指页面被访问的总次数", "PV 突破 10 万"),
            ("UV", "metric", "独立访客数，指访问网站的独立用户数", "UV 日均 5 万"),
            ("转化率", "metric", "完成目标行为的用户比例", "转化率 5%"),
            ("留存率", "metric", "用户在一段时间后仍然活跃的比例", "次日留存率 30%"),
        ]
        
        for keyword, term_type, description, example in default_terms:
            try:
                self.add_term(keyword, term_type, description, example, priority=1)
            except:
                pass  # 已存在则跳过
        
        # 默认时间规则
        default_rules = [
            ("昨天", "relative", "-1 day", "相对于今天的前一天"),
            ("今天", "relative", "0 day", "当天"),
            ("本周", "relative", "this week", "本周一到现在"),
            ("上周", "relative", "last week", "上周一到上周日"),
            ("本月", "relative", "this month", "本月1日到现在"),
            ("上月", "relative", "last month", "上月1日到上月最后一天"),
            ("最近7天", "relative", "-7 days", "过去7天"),
            ("最近30天", "relative", "-30 days", "过去30天"),
        ]
        
        for keyword, rule_type, value, description in default_rules:
            try:
                self.add_time_rule(keyword, rule_type, value, description)
            except:
                pass  # 已存在则跳过
    
    # ========== 业务术语操作 ==========
    
    def get_all_terms(self) -> List[Dict[str, Any]]:
        """获取所有业务术语"""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_terms ORDER BY priority DESC, created_at DESC")
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def add_term(
        self,
        keyword: str,
        term_type: str,
        description: str,
        example: Optional[str] = None,
        priority: int = 1,
    ) -> int:
        """添加业务术语"""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO business_terms (keyword, term_type, description, example, priority)
            VALUES (?, ?, ?, ?, ?)
            """,
            (keyword, term_type, description, example, priority),
        )
        term_id = cur.lastrowid
        conn.commit()
        conn.close()
        return term_id
    
    def delete_term(self, keyword: str) -> bool:
        """删除业务术语"""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM business_terms WHERE keyword = ?", (keyword,))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    
    # ========== 字段映射操作 ==========
    
    def get_all_mappings(self) -> List[Dict[str, Any]]:
        """获取所有字段映射"""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM field_mappings ORDER BY created_at DESC")
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def add_mapping(
        self,
        alias: str,
        standard_name: str,
        table_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> int:
        """添加字段映射"""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO field_mappings (alias, standard_name, table_name, description)
            VALUES (?, ?, ?, ?)
            """,
            (alias, standard_name, table_name, description),
        )
        mapping_id = cur.lastrowid
        conn.commit()
        conn.close()
        return mapping_id
    
    # ========== 时间规则操作 ==========
    
    def get_all_time_rules(self) -> List[Dict[str, Any]]:
        """获取所有时间规则"""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM time_rules ORDER BY created_at DESC")
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def add_time_rule(
        self,
        keyword: str,
        rule_type: str,
        value: str,
        description: Optional[str] = None,
    ) -> int:
        """添加时间规则"""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO time_rules (keyword, rule_type, value, description)
            VALUES (?, ?, ?, ?)
            """,
            (keyword, rule_type, value, description),
        )
        rule_id = cur.lastrowid
        conn.commit()
        conn.close()
        return rule_id
    
    def delete_time_rule(self, keyword: str) -> bool:
        """删除时间规则"""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM time_rules WHERE keyword = ?", (keyword,))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
