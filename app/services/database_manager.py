"""
数据库管理服务。

支持：
- 表结构查看
- CSV/Excel 导入
- 数据类型推断
- 增量/覆盖导入
- 数据导出
"""

import sqlite3
import pandas as pd
from pathlib import Path
from typing import Dict, List, Literal, Optional, Any
from dataclasses import dataclass, asdict
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


@dataclass
class ColumnInfo:
    """列信息"""
    name: str
    dtype: str
    nullable: bool
    sample_values: List[Any]


@dataclass
class TableInfo:
    """表信息"""
    name: str
    row_count: int
    column_count: int
    size_bytes: int
    columns: List[ColumnInfo]


@dataclass
class ParseResult:
    """文件解析结果"""
    columns: List[ColumnInfo]
    row_count: int
    preview_data: List[Dict[str, Any]]
    inferred_types: Dict[str, str]


@dataclass
class ImportResult:
    """导入结果"""
    success: bool
    table_name: str
    rows_imported: int
    message: str


class DatabaseManager:
    """数据库管理服务"""
    
    # Pandas 类型到 SQLite 类型的映射
    PANDAS_TO_SQLITE = {
        'int64': 'INTEGER',
        'int32': 'INTEGER',
        'float64': 'REAL',
        'float32': 'REAL',
        'object': 'TEXT',
        'bool': 'INTEGER',
        'datetime64[ns]': 'TEXT',
        'datetime64': 'TEXT',
        'category': 'TEXT',
    }
    
    # 保护的系统表（不允许删除）
    PROTECTED_TABLES = {'sqlite_sequence'}
    
    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {'.csv', '.xlsx', '.xls'}
    
    # 最大文件大小（50MB）
    MAX_FILE_SIZE = 50 * 1024 * 1024
    
    def __init__(self, db_path: Path, agent_memory=None):
        """
        初始化数据库管理器。
        
        Args:
            db_path: 数据库文件路径
            agent_memory: Agent Memory 实例（用于刷新 schema）
        """
        self.db_path = Path(db_path)
        self.agent_memory = agent_memory
        
        # 确保数据库文件所在目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _sanitize_name(self, name: str) -> str:
        """清理表名/列名，防止 SQL 注入"""
        # 移除危险字符，只保留字母、数字、下划线
        import re
        sanitized = re.sub(r'[^\w]', '_', name)
        # 确保不以数字开头
        if sanitized and sanitized[0].isdigit():
            sanitized = '_' + sanitized
        return sanitized or 'unnamed'
    
    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库概览信息"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        # 获取表数量
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        table_count = cur.fetchone()[0]
        
        # 获取数据库文件大小
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        
        # 获取最后修改时间
        import os
        last_modified = os.path.getmtime(self.db_path) if self.db_path.exists() else None
        
        conn.close()
        
        return {
            "table_count": table_count,
            "size_bytes": db_size,
            "size_mb": round(db_size / (1024 * 1024), 2),
            "last_modified": last_modified,
            "db_path": str(self.db_path),
        }
    
    def get_tables(self) -> List[TableInfo]:
        """获取所有表信息"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        # 获取所有用户表名
        cur.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        table_names = [row[0] for row in cur.fetchall()]
        
        # 获取数据库总大小用于估算
        total_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        total_rows = 0
        
        # 先统计总行数
        for name in table_names:
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{name}"')
                total_rows += cur.fetchone()[0]
            except:
                pass
        
        tables = []
        for name in table_names:
            try:
                # 行数
                cur.execute(f'SELECT COUNT(*) FROM "{name}"')
                row_count = cur.fetchone()[0]
                
                # 列信息
                cur.execute(f'PRAGMA table_info("{name}")')
                columns = []
                for col in cur.fetchall():
                    columns.append(ColumnInfo(
                        name=col['name'],
                        dtype=col['type'] or 'TEXT',
                        nullable=not col['notnull'],
                        sample_values=[],
                    ))
                
                # 估算表大小（按行数比例分配）
                if total_rows > 0:
                    size_bytes = int(total_size * (row_count / total_rows))
                else:
                    size_bytes = total_size // max(len(table_names), 1)
                
                tables.append(TableInfo(
                    name=name,
                    row_count=row_count,
                    column_count=len(columns),
                    size_bytes=size_bytes,
                    columns=columns,
                ))
            except Exception as e:
                logger.warning(f"获取表 {name} 信息失败: {e}")
                continue
        
        conn.close()
        return tables
    
    def get_table_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        """获取表的详细结构信息"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        try:
            # 表信息
            cur.execute(f'PRAGMA table_info("{table_name}")')
            columns = []
            for col in cur.fetchall():
                columns.append({
                    "cid": col['cid'],
                    "name": col['name'],
                    "type": col['type'] or 'TEXT',
                    "notnull": bool(col['notnull']),
                    "default_value": col['dflt_value'],
                    "pk": bool(col['pk']),
                })
            
            # 索引信息
            cur.execute(f'PRAGMA index_list("{table_name}")')
            indexes = []
            for idx in cur.fetchall():
                indexes.append({
                    "name": idx['name'],
                    "unique": bool(idx['unique']),
                })
            
            # 行数
            cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            row_count = cur.fetchone()[0]
            
            conn.close()
            
            return {
                "name": table_name,
                "columns": columns,
                "indexes": indexes,
                "row_count": row_count,
            }
        except Exception as e:
            logger.error(f"获取表结构失败: {e}")
            conn.close()
            return None
    
    def preview_table(self, table_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """预览表数据"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        try:
            cur.execute(f'SELECT * FROM "{table_name}" LIMIT ?', (limit,))
            columns = [desc[0] for desc in cur.description]
            rows = []
            for row in cur.fetchall():
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # 处理特殊类型
                    if isinstance(value, bytes):
                        value = f"<BLOB {len(value)} bytes>"
                    row_dict[col] = value
                rows.append(row_dict)
            return rows
        except Exception as e:
            logger.error(f"预览表数据失败: {e}")
            return []
        finally:
            conn.close()
    
    def parse_upload(self, file_content: bytes, filename: str) -> ParseResult:
        """
        解析上传的文件，返回预览信息。
        
        Args:
            file_content: 文件内容
            filename: 文件名
            
        Returns:
            ParseResult: 解析结果
        """
        # 检查文件大小
        if len(file_content) > self.MAX_FILE_SIZE:
            raise ValueError(f"文件过大，最大支持 {self.MAX_FILE_SIZE // (1024*1024)}MB")
        
        # 检查扩展名
        ext = Path(filename).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的文件格式: {ext}，支持: {', '.join(self.SUPPORTED_EXTENSIONS)}")
        
        # 根据扩展名选择解析方式
        try:
            if ext == '.csv':
                # 尝试多种编码
                for encoding in ['utf-8', 'gbk', 'gb2312', 'latin1']:
                    try:
                        df = pd.read_csv(BytesIO(file_content), encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    df = pd.read_csv(BytesIO(file_content), encoding='utf-8', errors='replace')
            elif ext in ['.xlsx', '.xls']:
                df = pd.read_excel(BytesIO(file_content))
            else:
                raise ValueError(f"不支持的文件格式: {ext}")
        except Exception as e:
            raise ValueError(f"文件解析失败: {str(e)}")
        
        # 清理列名
        df.columns = [self._sanitize_name(str(col).strip()) for col in df.columns]
        
        # 推断类型
        inferred_types = {}
        columns = []
        
        for col in df.columns:
            dtype_str = str(df[col].dtype)
            sqlite_type = self.PANDAS_TO_SQLITE.get(dtype_str, 'TEXT')
            inferred_types[col] = sqlite_type
            
            # 获取示例值（非空的前3个）
            samples = df[col].dropna().head(3).tolist()
            # 转换为可序列化的类型
            samples = [str(s) if not isinstance(s, (int, float, str, bool, type(None))) else s for s in samples]
            
            columns.append(ColumnInfo(
                name=col,
                dtype=sqlite_type,
                nullable=bool(df[col].isna().any()),
                sample_values=samples,
            ))
        
        # 预览数据（前10行）
        preview_df = df.head(10).copy()
        # 处理特殊类型
        for col in preview_df.columns:
            preview_df[col] = preview_df[col].apply(
                lambda x: str(x) if not isinstance(x, (int, float, str, bool, type(None))) and pd.notna(x) else x
            )
        preview_data = preview_df.where(pd.notna(preview_df), None).to_dict('records')
        
        return ParseResult(
            columns=columns,
            row_count=len(df),
            preview_data=preview_data,
            inferred_types=inferred_types,
        )
    
    def import_data(
        self,
        file_content: bytes,
        filename: str,
        table_name: str,
        mode: Literal['create', 'replace', 'append'],
        column_types: Optional[Dict[str, str]] = None,
    ) -> ImportResult:
        """
        导入数据到数据库。
        
        Args:
            file_content: 文件内容
            filename: 文件名
            table_name: 目标表名
            mode: 导入模式 (create/replace/append)
            column_types: 自定义列类型
            
        Returns:
            ImportResult: 导入结果
        """
        try:
            # 清理表名
            table_name = self._sanitize_name(table_name)
            
            # 检查保护表
            if table_name.lower() in self.PROTECTED_TABLES:
                return ImportResult(False, table_name, 0, f"不能修改系统表: {table_name}")
            
            # 解析文件
            ext = Path(filename).suffix.lower()
            if ext == '.csv':
                for encoding in ['utf-8', 'gbk', 'gb2312', 'latin1']:
                    try:
                        df = pd.read_csv(BytesIO(file_content), encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    df = pd.read_csv(BytesIO(file_content), encoding='utf-8', errors='replace')
            elif ext in ['.xlsx', '.xls']:
                df = pd.read_excel(BytesIO(file_content))
            else:
                return ImportResult(False, table_name, 0, f"不支持的格式: {ext}")
            
            # 清理列名
            df.columns = [self._sanitize_name(str(col).strip()) for col in df.columns]
            
            # 连接数据库
            conn = self._get_conn()
            
            # 检查表是否存在
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            table_exists = cur.fetchone() is not None
            
            # 根据模式处理
            if mode == 'create' and table_exists:
                conn.close()
                return ImportResult(False, table_name, 0, f"表 {table_name} 已存在，请选择覆盖或追加模式")
            
            if mode == 'append' and not table_exists:
                conn.close()
                return ImportResult(False, table_name, 0, f"表 {table_name} 不存在，无法追加数据")
            
            if_exists = {
                'create': 'fail',
                'replace': 'replace',
                'append': 'append',
            }[mode]
            
            # 导入数据
            df.to_sql(table_name, conn, if_exists=if_exists, index=False)
            
            conn.close()
            
            logger.info(f"成功导入 {len(df)} 行数据到表 {table_name}")
            
            return ImportResult(
                success=True,
                table_name=table_name,
                rows_imported=len(df),
                message=f"成功导入 {len(df)} 行数据到表 {table_name}",
            )
            
        except Exception as e:
            logger.error(f"导入失败: {e}")
            return ImportResult(
                success=False,
                table_name=table_name,
                rows_imported=0,
                message=str(e),
            )
    
    def delete_table(self, table_name: str) -> Dict[str, Any]:
        """删除表"""
        # 检查保护表
        if table_name.lower() in self.PROTECTED_TABLES:
            return {"success": False, "message": f"不能删除系统表: {table_name}"}
        
        try:
            conn = self._get_conn()
            conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            conn.commit()
            conn.close()
            logger.info(f"已删除表: {table_name}")
            return {"success": True, "message": f"已删除表: {table_name}"}
        except Exception as e:
            logger.error(f"删除表失败: {e}")
            return {"success": False, "message": str(e)}
    
    def rename_table(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """重命名表"""
        # 清理新名称
        new_name = self._sanitize_name(new_name)
        
        # 检查保护表
        if old_name.lower() in self.PROTECTED_TABLES:
            return {"success": False, "message": f"不能重命名系统表: {old_name}"}
        
        try:
            conn = self._get_conn()
            conn.execute(f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"')
            conn.commit()
            conn.close()
            logger.info(f"已重命名表: {old_name} -> {new_name}")
            return {"success": True, "message": f"已重命名: {old_name} -> {new_name}"}
        except Exception as e:
            logger.error(f"重命名表失败: {e}")
            return {"success": False, "message": str(e)}
    
    def export_table(self, table_name: str) -> BytesIO:
        """导出表为 CSV"""
        conn = self._get_conn()
        df = pd.read_sql(f'SELECT * FROM "{table_name}"', conn)
        conn.close()
        
        output = BytesIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        return output
    
    def execute_sql(self, sql: str) -> Dict[str, Any]:
        """
        执行自定义 SQL（仅支持只读查询）。
        
        Args:
            sql: SQL 语句
            
        Returns:
            查询结果
        """
        # 简单的安全检查
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith('SELECT'):
            return {"success": False, "message": "只支持 SELECT 查询"}
        
        try:
            conn = self._get_conn()
            df = pd.read_sql(sql, conn)
            conn.close()
            
            return {
                "success": True,
                "columns": list(df.columns),
                "data": df.head(1000).to_dict('records'),
                "row_count": len(df),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def refresh_schema(self) -> int:
        """刷新 Agent Memory 中的 Schema"""
        if not self.agent_memory:
            logger.warning("Agent Memory 未配置，跳过 schema 刷新")
            return 0
        
        try:
            from app.services.schema_loader import load_schema_to_memory
            
            count = await load_schema_to_memory(
                data_db_path=self.db_path,
                agent_memory=self.agent_memory,
                force_reload=True,
            )
            logger.info(f"Schema 刷新完成，更新了 {count} 个表")
            return count
        except Exception as e:
            logger.error(f"Schema 刷新失败: {e}")
            return 0









