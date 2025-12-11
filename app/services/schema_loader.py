"""
数据库 Schema 加载器。

在应用启动时自动加载数据库表结构信息到 Agent Memory，
帮助 LLM 更好地理解数据库结构，生成更准确的 SQL。
"""

import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from vanna.core.tool import ToolContext
from vanna.core.user import User

from app.services.agent_memory import SqliteAgentMemory

logger = logging.getLogger(__name__)


async def load_schema_to_memory(
    data_db_path: Path,
    agent_memory: SqliteAgentMemory,
    *,
    force_reload: bool = False,
) -> int:
    """
    加载数据库 Schema 到 Agent Memory。

    Args:
        data_db_path: 数据库文件路径
        agent_memory: Agent Memory 实例
        force_reload: 是否强制重新加载（清除旧的 schema 信息）

    Returns:
        加载的表数量
    """
    if not data_db_path.exists():
        logger.warning(f"数据库文件不存在: {data_db_path}")
        return 0

    # 创建临时 context
    context = ToolContext(
        user=User(id="system", email="system@internal"),
        conversation_id="schema_loader",
        request_id="init",
        agent_memory=agent_memory,
    )

    # 检查是否已经加载过 schema
    if not force_reload:
        existing_memories = await agent_memory.search_text_memories(
            query="数据库表结构",
            context=context,
            limit=1,
            similarity_threshold=0.8,
        )
        if existing_memories:
            logger.info("Schema 信息已存在于 Memory 中，跳过加载")
            return 0

    # 连接数据库获取 schema
    conn = sqlite3.connect(str(data_db_path))
    cursor = conn.cursor()

    # 获取所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]

    if not tables:
        logger.warning("数据库中没有找到任何表")
        conn.close()
        return 0

    loaded_count = 0
    for table_name in tables:
        try:
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            # 获取示例数据（前 3 行）
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            sample_rows = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description] if cursor.description else []

            # 获取行数
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]

            # 构建 schema 描述
            schema_text = _build_schema_description(
                table_name, columns, column_names, sample_rows, row_count
            )

            # 保存到 Memory
            await agent_memory.save_text_memory(schema_text, context)
            loaded_count += 1
            logger.info(f"已加载表 {table_name} 的 schema 信息")

        except Exception as e:
            logger.warning(f"加载表 {table_name} 的 schema 失败: {e}")

    conn.close()

    # 保存一个总体概述
    overview = _build_database_overview(tables)
    await agent_memory.save_text_memory(overview, context)

    logger.info(f"Schema 加载完成，共加载 {loaded_count} 个表的信息")
    return loaded_count


def _build_schema_description(
    table_name: str,
    columns: List[tuple],
    column_names: List[str],
    sample_rows: List[tuple],
    row_count: int,
) -> str:
    """构建表的 schema 描述文本。"""
    lines = [
        f"## 数据库表结构: {table_name}",
        f"表名: {table_name}",
        f"总行数: {row_count}",
        "",
        "### 列信息:",
    ]

    for col in columns:
        # col: (cid, name, type, notnull, default_value, pk)
        col_name = col[1]
        col_type = col[2]
        is_pk = col[5]
        is_notnull = col[3]

        constraints = []
        if is_pk:
            constraints.append("主键")
        if is_notnull:
            constraints.append("非空")

        constraint_str = f" ({', '.join(constraints)})" if constraints else ""
        lines.append(f"- {col_name}: {col_type}{constraint_str}")

    # 添加示例数据
    if sample_rows and column_names:
        lines.append("")
        lines.append("### 示例数据:")
        lines.append(f"列名: {', '.join(column_names)}")
        for i, row in enumerate(sample_rows[:3], 1):
            # 截断过长的值
            row_values = [str(v)[:50] + "..." if len(str(v)) > 50 else str(v) for v in row]
            lines.append(f"示例{i}: {', '.join(row_values)}")

    return "\n".join(lines)


def _build_database_overview(tables: List[str]) -> str:
    """构建数据库概述。"""
    return f"""## 数据库概述

本数据库包含以下 {len(tables)} 个表:
{chr(10).join(f'- {t}' for t in tables)}

在生成 SQL 查询时，请确保使用正确的表名和列名。
"""


def get_schema_summary(data_db_path: Path) -> Optional[Dict]:
    """
    获取数据库 schema 摘要（同步版本，用于调试）。

    Returns:
        包含表信息的字典，如果失败返回 None
    """
    if not data_db_path.exists():
        return None

    try:
        conn = sqlite3.connect(str(data_db_path))
        cursor = conn.cursor()

        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]

        result = {"tables": {}}
        for table_name in tables:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]

            result["tables"][table_name] = {
                "columns": [
                    {"name": col[1], "type": col[2], "pk": bool(col[5])}
                    for col in columns
                ],
                "row_count": row_count,
            }

        conn.close()
        return result

    except Exception as e:
        logger.error(f"获取 schema 摘要失败: {e}")
        return None









