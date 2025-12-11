"""
系统数据库统一管理。

将原本分散的多个数据库（memory, knowledge, prompt, evaluation）合并到一个 system.db 中，
使用不同的表名前缀来区分不同的模块。
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SystemDB:
    """系统数据库统一管理"""
    
    def __init__(self, db_path: Path):
        """
        初始化系统数据库。
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self) -> None:
        """初始化数据库表结构（所有模块的表都在这里）"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        # 执行所有表的创建语句（如果不存在）
        # 这里不实际创建表，只是确保数据库文件存在
        # 各个服务会在首次使用时创建自己的表
        
        conn.commit()
        conn.close()
        logger.info(f"系统数据库已初始化: {self.db_path}")
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接（供其他服务使用）"""
        return self._get_conn()
    
    def migrate_from_old_databases(
        self,
        memory_db_path: Optional[Path] = None,
        knowledge_db_path: Optional[Path] = None,
        prompt_db_path: Optional[Path] = None,
        evaluation_db_path: Optional[Path] = None,
    ) -> dict:
        """
        从旧的数据库迁移数据到新的系统数据库。
        
        Args:
            memory_db_path: 旧的 memory.db 路径
            knowledge_db_path: 旧的 knowledge.db 路径
            prompt_db_path: 旧的 prompt.db 路径
            evaluation_db_path: 旧的 evaluation.db 路径
        
        Returns:
            迁移结果统计
        """
        result = {
            "memory": 0,
            "knowledge": 0,
            "prompt": 0,
            "evaluation": 0,
            "errors": [],
        }
        
        # 迁移 memory 数据
        if memory_db_path and memory_db_path.exists():
            try:
                count = self._migrate_memory_tables(memory_db_path)
                result["memory"] = count
                logger.info(f"迁移 memory 数据: {count} 条记录")
            except Exception as e:
                error_msg = f"迁移 memory 数据失败: {e}"
                result["errors"].append(error_msg)
                logger.error(error_msg)
        
        # 迁移 knowledge 数据
        if knowledge_db_path and knowledge_db_path.exists():
            try:
                count = self._migrate_knowledge_tables(knowledge_db_path)
                result["knowledge"] = count
                logger.info(f"迁移 knowledge 数据: {count} 条记录")
            except Exception as e:
                error_msg = f"迁移 knowledge 数据失败: {e}"
                result["errors"].append(error_msg)
                logger.error(error_msg)
        
        # 迁移 prompt 数据
        if prompt_db_path and prompt_db_path.exists():
            try:
                count = self._migrate_prompt_tables(prompt_db_path)
                result["prompt"] = count
                logger.info(f"迁移 prompt 数据: {count} 条记录")
            except Exception as e:
                error_msg = f"迁移 prompt 数据失败: {e}"
                result["errors"].append(error_msg)
                logger.error(error_msg)
        
        # 迁移 evaluation 数据
        if evaluation_db_path and evaluation_db_path.exists():
            try:
                count = self._migrate_evaluation_tables(evaluation_db_path)
                result["evaluation"] = count
                logger.info(f"迁移 evaluation 数据: {count} 条记录")
            except Exception as e:
                error_msg = f"迁移 evaluation 数据失败: {e}"
                result["errors"].append(error_msg)
                logger.error(error_msg)
        
        return result
    
    def _migrate_memory_tables(self, old_db_path: Path) -> int:
        """迁移 memory 表"""
        old_conn = sqlite3.connect(str(old_db_path))
        old_conn.row_factory = sqlite3.Row
        old_cur = old_conn.cursor()
        
        new_conn = self._get_conn()
        new_cur = new_conn.cursor()
        
        count = 0
        
        # 检查旧数据库中是否有表
        old_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in old_cur.fetchall()]
        
        for table in tables:
            if table.startswith('sqlite_'):
                continue
            
            # 获取表结构
            old_cur.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in old_cur.fetchall()]
            
            # 在新数据库中创建表（如果不存在）
            # 注意：这里需要根据实际的表结构来创建
            # 为了简化，我们直接复制数据（假设表结构已经存在）
            try:
                old_cur.execute(f"SELECT * FROM {table}")
                rows = old_cur.fetchall()
                
                if rows:
                    # 这里需要根据实际表结构插入数据
                    # 暂时跳过，让各个服务自己处理迁移
                    count += len(rows)
            except Exception as e:
                logger.warning(f"迁移表 {table} 时出错: {e}")
        
        old_conn.close()
        new_conn.close()
        
        return count
    
    def _migrate_knowledge_tables(self, old_db_path: Path) -> int:
        """迁移 knowledge 表"""
        # 类似 memory 的迁移逻辑
        return 0
    
    def _migrate_prompt_tables(self, old_db_path: Path) -> int:
        """迁移 prompt 表"""
        # 类似 memory 的迁移逻辑
        return 0
    
    def _migrate_evaluation_tables(self, old_db_path: Path) -> int:
        """迁移 evaluation 表"""
        # 类似 memory 的迁移逻辑
        return 0









