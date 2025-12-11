"""
数据库迁移脚本：将分散的数据库合并到统一的 system.db

将以下数据库合并：
- memory.db -> system.db (所有表直接迁移)
- knowledge.db -> system.db (所有表直接迁移)
- prompt.db -> system.db (所有表直接迁移)
- evaluation.db -> system.db (所有表直接迁移)
"""

import sqlite3
import shutil
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_database(source_db: Path, target_db: Path, db_name: str):
    """
    将一个源数据库的所有表和数据迁移到目标数据库
    
    Args:
        source_db: 源数据库路径
        target_db: 目标数据库路径
        db_name: 数据库名称（用于日志）
    """
    if not source_db.exists():
        logger.info(f"{db_name} 数据库不存在，跳过: {source_db}")
        return 0
    
    logger.info(f"开始迁移 {db_name} 数据库: {source_db} -> {target_db}")
    
    # 确保目标数据库目录存在
    target_db.parent.mkdir(parents=True, exist_ok=True)
    
    source_conn = sqlite3.connect(str(source_db))
    target_conn = sqlite3.connect(str(target_db))
    
    source_conn.row_factory = sqlite3.Row
    target_conn.row_factory = sqlite3.Row
    
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
    # 获取所有表名
    source_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in source_cursor.fetchall()]
    
    if not tables:
        logger.info(f"{db_name} 数据库中没有表，跳过")
        source_conn.close()
        target_conn.close()
        return 0
    
    migrated_count = 0
    
    for table in tables:
        try:
            # 检查目标数据库中是否已存在该表
            target_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            table_exists = target_cursor.fetchone() is not None
            
            if table_exists:
                logger.warning(f"表 {table} 在目标数据库中已存在，跳过")
                continue
            
            # 获取表结构
            source_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
            create_sql = source_cursor.fetchone()[0]
            
            # 在目标数据库中创建表
            target_cursor.execute(create_sql)
            
            # 复制数据
            source_cursor.execute(f"SELECT * FROM {table}")
            rows = source_cursor.fetchall()
            
            if rows:
                # 获取列名
                columns = [description[0] for description in source_cursor.description]
                placeholders = ", ".join(["?" for _ in columns])
                insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
                
                # 将 Row 对象转换为元组
                values = [tuple(row) for row in rows]
                target_cursor.executemany(insert_sql, values)
                migrated_count += len(values)
                logger.info(f"  迁移表 {table}: {len(values)} 条记录")
            
            # 复制索引
            source_cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=?", (table,))
            indexes = source_cursor.fetchall()
            for index_row in indexes:
                if index_row[0]:  # 有些索引可能没有 SQL
                    try:
                        target_cursor.execute(index_row[0])
                    except sqlite3.OperationalError as e:
                        logger.warning(f"  跳过索引创建（可能已存在）: {e}")
            
        except Exception as e:
            logger.error(f"迁移表 {table} 时出错: {e}")
            continue
    
    target_conn.commit()
    source_conn.close()
    target_conn.close()
    
    logger.info(f"完成迁移 {db_name} 数据库: 共迁移 {migrated_count} 条记录")
    return migrated_count


def main():
    """主函数：执行数据库迁移"""
    from app.config import SYSTEM_DB_PATH, PROJECT_ROOT, VANNA_DATA_DIR
    
    # 确定旧的数据库路径
    logs_dir = PROJECT_ROOT / "logs"
    old_memory_db = logs_dir / "memory.db"
    old_knowledge_db = VANNA_DATA_DIR / "knowledge.db"
    old_prompt_db = VANNA_DATA_DIR / "prompt.db"
    old_evaluation_db = VANNA_DATA_DIR / "evaluation.db"
    
    # 目标数据库
    target_db = SYSTEM_DB_PATH
    
    logger.info("=" * 60)
    logger.info("开始数据库迁移：合并到统一的 system.db")
    logger.info("=" * 60)
    
    total_records = 0
    
    # 迁移各个数据库
    total_records += migrate_database(old_memory_db, target_db, "memory")
    total_records += migrate_database(old_knowledge_db, target_db, "knowledge")
    total_records += migrate_database(old_prompt_db, target_db, "prompt")
    total_records += migrate_database(old_evaluation_db, target_db, "evaluation")
    
    logger.info("=" * 60)
    logger.info(f"数据库迁移完成！共迁移 {total_records} 条记录")
    logger.info(f"统一数据库路径: {target_db}")
    logger.info("=" * 60)
    logger.info("")
    logger.info("注意：")
    logger.info("1. 旧的数据库文件已保留，可以手动删除")
    logger.info("2. 请备份旧数据库后再删除")
    logger.info("3. 如果出现问题，可以恢复旧数据库")


if __name__ == "__main__":
    main()









