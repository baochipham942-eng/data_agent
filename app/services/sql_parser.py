"""
SQL 解析与结构化服务。

提供：
- 将 SQL 解析为结构化组件
- 支持用户修改查询条件
- 重新生成 SQL
"""

import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class SQLColumn:
    """SQL 列定义"""
    expression: str  # 原始表达式
    alias: Optional[str] = None  # 别名
    aggregation: Optional[str] = None  # 聚合函数: SUM, AVG, COUNT, MAX, MIN
    is_group_by: bool = False  # 是否是分组字段


@dataclass
class SQLCondition:
    """SQL 条件"""
    field: str
    operator: str  # =, !=, >, <, >=, <=, LIKE, IN, BETWEEN, IS NULL, IS NOT NULL
    value: Any
    logic: str = "AND"  # AND, OR


@dataclass
class SQLOrderBy:
    """排序条件"""
    field: str
    direction: str = "ASC"  # ASC, DESC


@dataclass
class StructuredSQL:
    """结构化 SQL"""
    # SELECT 部分
    columns: List[SQLColumn] = field(default_factory=list)
    
    # FROM 部分
    table: str = ""
    joins: List[Dict[str, str]] = field(default_factory=list)
    
    # WHERE 部分
    conditions: List[SQLCondition] = field(default_factory=list)
    
    # GROUP BY 部分
    group_by: List[str] = field(default_factory=list)
    
    # HAVING 部分
    having: List[SQLCondition] = field(default_factory=list)
    
    # ORDER BY 部分
    order_by: List[SQLOrderBy] = field(default_factory=list)
    
    # LIMIT 部分
    limit: Optional[int] = None
    offset: Optional[int] = None
    
    # 原始 SQL
    original_sql: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "columns": [asdict(c) for c in self.columns],
            "table": self.table,
            "joins": self.joins,
            "conditions": [asdict(c) for c in self.conditions],
            "group_by": self.group_by,
            "having": [asdict(h) for h in self.having],
            "order_by": [asdict(o) for o in self.order_by],
            "limit": self.limit,
            "offset": self.offset,
            "original_sql": self.original_sql,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuredSQL":
        """从字典创建"""
        return cls(
            columns=[SQLColumn(**c) for c in data.get("columns", [])],
            table=data.get("table", ""),
            joins=data.get("joins", []),
            conditions=[SQLCondition(**c) for c in data.get("conditions", [])],
            group_by=data.get("group_by", []),
            having=[SQLCondition(**h) for h in data.get("having", [])],
            order_by=[SQLOrderBy(**o) for o in data.get("order_by", [])],
            limit=data.get("limit"),
            offset=data.get("offset"),
            original_sql=data.get("original_sql", ""),
        )
    
    def to_sql(self) -> str:
        """生成 SQL"""
        parts = []
        
        # SELECT
        if self.columns:
            select_parts = []
            for col in self.columns:
                expr = col.expression
                if col.aggregation:
                    expr = f"{col.aggregation}({expr})"
                if col.alias:
                    expr = f"{expr} AS {col.alias}"
                select_parts.append(expr)
            parts.append(f"SELECT {', '.join(select_parts)}")
        else:
            parts.append("SELECT *")
        
        # FROM
        if self.table:
            parts.append(f"FROM {self.table}")
        
        # JOIN
        for join in self.joins:
            join_type = join.get("type", "JOIN")
            join_table = join.get("table", "")
            join_on = join.get("on", "")
            parts.append(f"{join_type} {join_table} ON {join_on}")
        
        # WHERE
        if self.conditions:
            where_parts = []
            for i, cond in enumerate(self.conditions):
                if i > 0:
                    where_parts.append(cond.logic)
                
                if cond.operator.upper() == "IN":
                    if isinstance(cond.value, (list, tuple)):
                        values = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in cond.value)
                    else:
                        values = cond.value
                    where_parts.append(f"{cond.field} IN ({values})")
                elif cond.operator.upper() == "BETWEEN":
                    if isinstance(cond.value, (list, tuple)) and len(cond.value) == 2:
                        where_parts.append(f"{cond.field} BETWEEN '{cond.value[0]}' AND '{cond.value[1]}'")
                    else:
                        where_parts.append(f"{cond.field} {cond.operator} {cond.value}")
                elif cond.operator.upper() in ("IS NULL", "IS NOT NULL"):
                    where_parts.append(f"{cond.field} {cond.operator}")
                elif cond.operator.upper() == "LIKE":
                    where_parts.append(f"{cond.field} LIKE '{cond.value}'")
                else:
                    if isinstance(cond.value, str):
                        where_parts.append(f"{cond.field} {cond.operator} '{cond.value}'")
                    else:
                        where_parts.append(f"{cond.field} {cond.operator} {cond.value}")
            
            parts.append(f"WHERE {' '.join(where_parts)}")
        
        # GROUP BY
        if self.group_by:
            parts.append(f"GROUP BY {', '.join(self.group_by)}")
        
        # HAVING
        if self.having:
            having_parts = []
            for i, cond in enumerate(self.having):
                if i > 0:
                    having_parts.append(cond.logic)
                if isinstance(cond.value, str):
                    having_parts.append(f"{cond.field} {cond.operator} '{cond.value}'")
                else:
                    having_parts.append(f"{cond.field} {cond.operator} {cond.value}")
            parts.append(f"HAVING {' '.join(having_parts)}")
        
        # ORDER BY
        if self.order_by:
            order_parts = [f"{o.field} {o.direction}" for o in self.order_by]
            parts.append(f"ORDER BY {', '.join(order_parts)}")
        
        # LIMIT
        if self.limit is not None:
            if self.offset is not None:
                parts.append(f"LIMIT {self.limit} OFFSET {self.offset}")
            else:
                parts.append(f"LIMIT {self.limit}")
        
        return "\n".join(parts)


class SQLParser:
    """SQL 解析器"""
    
    # 聚合函数
    AGGREGATIONS = ["SUM", "AVG", "COUNT", "MAX", "MIN"]
    
    # 运算符
    OPERATORS = [">=", "<=", "!=", "<>", "=", ">", "<", "LIKE", "IN", "BETWEEN", "IS NOT NULL", "IS NULL"]
    
    def parse(self, sql: str) -> StructuredSQL:
        """
        解析 SQL 为结构化格式。
        
        Args:
            sql: SQL 语句
            
        Returns:
            StructuredSQL: 结构化 SQL
        """
        result = StructuredSQL(original_sql=sql)
        
        # 标准化 SQL
        sql = self._normalize_sql(sql)
        
        try:
            # 解析各个部分
            result.columns = self._parse_select(sql)
            result.table, result.joins = self._parse_from(sql)
            result.conditions = self._parse_where(sql)
            result.group_by = self._parse_group_by(sql)
            result.having = self._parse_having(sql)
            result.order_by = self._parse_order_by(sql)
            result.limit, result.offset = self._parse_limit(sql)
            
        except Exception as e:
            logger.warning(f"SQL 解析警告: {e}")
        
        return result
    
    def _normalize_sql(self, sql: str) -> str:
        """标准化 SQL"""
        # 移除多余空白
        sql = re.sub(r'\s+', ' ', sql.strip())
        # 移除注释
        sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        return sql
    
    def _parse_select(self, sql: str) -> List[SQLColumn]:
        """解析 SELECT 部分"""
        columns = []
        
        # 提取 SELECT 到 FROM 之间的部分
        match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE)
        if not match:
            return columns
        
        select_part = match.group(1)
        
        # 处理 DISTINCT
        select_part = re.sub(r'^DISTINCT\s+', '', select_part, flags=re.IGNORECASE)
        
        # 分割列（考虑函数中的逗号）
        col_strs = self._split_columns(select_part)
        
        for col_str in col_strs:
            col_str = col_str.strip()
            if not col_str or col_str == '*':
                continue
            
            col = self._parse_column(col_str)
            columns.append(col)
        
        return columns
    
    def _split_columns(self, select_part: str) -> List[str]:
        """分割列，考虑括号嵌套"""
        columns = []
        current = ""
        depth = 0
        
        for char in select_part:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == ',' and depth == 0:
                columns.append(current.strip())
                current = ""
                continue
            current += char
        
        if current.strip():
            columns.append(current.strip())
        
        return columns
    
    def _parse_column(self, col_str: str) -> SQLColumn:
        """解析单个列"""
        # 检查别名
        alias = None
        alias_match = re.search(r'\s+AS\s+[`"\']?(\w+)[`"\']?\s*$', col_str, re.IGNORECASE)
        if alias_match:
            alias = alias_match.group(1)
            col_str = col_str[:alias_match.start()].strip()
        
        # 检查聚合函数
        aggregation = None
        for agg in self.AGGREGATIONS:
            agg_match = re.match(rf'{agg}\s*\(\s*(.+)\s*\)', col_str, re.IGNORECASE)
            if agg_match:
                aggregation = agg.upper()
                col_str = agg_match.group(1).strip()
                break
        
        return SQLColumn(
            expression=col_str,
            alias=alias,
            aggregation=aggregation,
        )
    
    def _parse_from(self, sql: str) -> Tuple[str, List[Dict[str, str]]]:
        """解析 FROM 部分"""
        table = ""
        joins = []
        
        # 提取 FROM 部分
        match = re.search(
            r'FROM\s+([`"\']?\w+[`"\']?(?:\s+(?:AS\s+)?[`"\']?\w+[`"\']?)?)',
            sql,
            re.IGNORECASE
        )
        if match:
            table = match.group(1).strip()
        
        # 提取 JOIN
        join_pattern = r'(LEFT\s+JOIN|RIGHT\s+JOIN|INNER\s+JOIN|JOIN)\s+([`"\']?\w+[`"\']?)\s+(?:AS\s+)?(\w+\s+)?ON\s+([^WHERE|GROUP|ORDER|LIMIT]+)'
        for join_match in re.finditer(join_pattern, sql, re.IGNORECASE):
            joins.append({
                "type": join_match.group(1).upper(),
                "table": join_match.group(2).strip(),
                "alias": join_match.group(3).strip() if join_match.group(3) else "",
                "on": join_match.group(4).strip(),
            })
        
        return table, joins
    
    def _parse_where(self, sql: str) -> List[SQLCondition]:
        """解析 WHERE 部分"""
        conditions = []
        
        # 提取 WHERE 部分
        match = re.search(
            r'WHERE\s+(.*?)(?=GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT|$)',
            sql,
            re.IGNORECASE
        )
        if not match:
            return conditions
        
        where_part = match.group(1).strip()
        
        # 按 AND/OR 分割
        parts = re.split(r'\s+(AND|OR)\s+', where_part, flags=re.IGNORECASE)
        
        logic = "AND"
        for part in parts:
            part = part.strip()
            if part.upper() in ("AND", "OR"):
                logic = part.upper()
                continue
            
            cond = self._parse_condition(part, logic)
            if cond:
                conditions.append(cond)
                logic = "AND"  # 重置默认
        
        return conditions
    
    def _parse_condition(self, part: str, logic: str = "AND") -> Optional[SQLCondition]:
        """解析单个条件"""
        for op in self.OPERATORS:
            if op.upper() in ("IS NULL", "IS NOT NULL"):
                if op.upper() in part.upper():
                    field = re.sub(rf'\s*{op}\s*$', '', part, flags=re.IGNORECASE).strip()
                    return SQLCondition(field=field, operator=op.upper(), value=None, logic=logic)
            elif op.upper() == "IN":
                match = re.search(rf'(.+?)\s+IN\s*\((.+)\)', part, re.IGNORECASE)
                if match:
                    field = match.group(1).strip()
                    values = [v.strip().strip("'\"") for v in match.group(2).split(",")]
                    return SQLCondition(field=field, operator="IN", value=values, logic=logic)
            elif op.upper() == "BETWEEN":
                match = re.search(rf'(.+?)\s+BETWEEN\s+(.+)\s+AND\s+(.+)', part, re.IGNORECASE)
                if match:
                    field = match.group(1).strip()
                    val1 = match.group(2).strip().strip("'\"")
                    val2 = match.group(3).strip().strip("'\"")
                    return SQLCondition(field=field, operator="BETWEEN", value=[val1, val2], logic=logic)
            elif op.upper() == "LIKE":
                match = re.search(rf'(.+?)\s+LIKE\s+(.+)', part, re.IGNORECASE)
                if match:
                    field = match.group(1).strip()
                    value = match.group(2).strip().strip("'\"")
                    return SQLCondition(field=field, operator="LIKE", value=value, logic=logic)
            else:
                # 普通比较运算符
                if op in part:
                    parts = part.split(op, 1)
                    if len(parts) == 2:
                        field = parts[0].strip()
                        value = parts[1].strip().strip("'\"")
                        # 尝试转换为数字
                        try:
                            value = int(value)
                        except ValueError:
                            try:
                                value = float(value)
                            except ValueError:
                                pass
                        return SQLCondition(field=field, operator=op, value=value, logic=logic)
        
        return None
    
    def _parse_group_by(self, sql: str) -> List[str]:
        """解析 GROUP BY 部分"""
        match = re.search(
            r'GROUP\s+BY\s+(.*?)(?=HAVING|ORDER\s+BY|LIMIT|$)',
            sql,
            re.IGNORECASE
        )
        if not match:
            return []
        
        group_part = match.group(1).strip()
        return [g.strip() for g in group_part.split(',')]
    
    def _parse_having(self, sql: str) -> List[SQLCondition]:
        """解析 HAVING 部分"""
        conditions = []
        
        match = re.search(
            r'HAVING\s+(.*?)(?=ORDER\s+BY|LIMIT|$)',
            sql,
            re.IGNORECASE
        )
        if not match:
            return conditions
        
        having_part = match.group(1).strip()
        parts = re.split(r'\s+(AND|OR)\s+', having_part, flags=re.IGNORECASE)
        
        logic = "AND"
        for part in parts:
            part = part.strip()
            if part.upper() in ("AND", "OR"):
                logic = part.upper()
                continue
            
            cond = self._parse_condition(part, logic)
            if cond:
                conditions.append(cond)
                logic = "AND"
        
        return conditions
    
    def _parse_order_by(self, sql: str) -> List[SQLOrderBy]:
        """解析 ORDER BY 部分"""
        orders = []
        
        match = re.search(
            r'ORDER\s+BY\s+(.*?)(?=LIMIT|$)',
            sql,
            re.IGNORECASE
        )
        if not match:
            return orders
        
        order_part = match.group(1).strip()
        for item in order_part.split(','):
            item = item.strip()
            direction = "ASC"
            if item.upper().endswith(" DESC"):
                direction = "DESC"
                item = item[:-5].strip()
            elif item.upper().endswith(" ASC"):
                item = item[:-4].strip()
            
            orders.append(SQLOrderBy(field=item, direction=direction))
        
        return orders
    
    def _parse_limit(self, sql: str) -> Tuple[Optional[int], Optional[int]]:
        """解析 LIMIT 部分"""
        limit = None
        offset = None
        
        # LIMIT n OFFSET m
        match = re.search(r'LIMIT\s+(\d+)\s+OFFSET\s+(\d+)', sql, re.IGNORECASE)
        if match:
            limit = int(match.group(1))
            offset = int(match.group(2))
            return limit, offset
        
        # LIMIT m, n (MySQL style)
        match = re.search(r'LIMIT\s+(\d+)\s*,\s*(\d+)', sql, re.IGNORECASE)
        if match:
            offset = int(match.group(1))
            limit = int(match.group(2))
            return limit, offset
        
        # LIMIT n
        match = re.search(r'LIMIT\s+(\d+)', sql, re.IGNORECASE)
        if match:
            limit = int(match.group(1))
        
        return limit, offset


# 便捷函数
def parse_sql(sql: str) -> StructuredSQL:
    """解析 SQL"""
    parser = SQLParser()
    return parser.parse(sql)


def modify_sql(
    sql: str,
    add_conditions: Optional[List[Dict]] = None,
    remove_conditions: Optional[List[str]] = None,
    change_aggregation: Optional[Dict[str, str]] = None,
    change_group_by: Optional[List[str]] = None,
    change_order_by: Optional[List[Dict]] = None,
    change_limit: Optional[int] = None,
) -> str:
    """
    修改 SQL。
    
    Args:
        sql: 原始 SQL
        add_conditions: 添加的条件 [{"field": "", "operator": "", "value": ""}]
        remove_conditions: 要移除的条件字段列表
        change_aggregation: 修改聚合 {"column": "new_aggregation"}
        change_group_by: 新的分组字段
        change_order_by: 新的排序 [{"field": "", "direction": ""}]
        change_limit: 新的 LIMIT
        
    Returns:
        修改后的 SQL
    """
    parser = SQLParser()
    structured = parser.parse(sql)
    
    # 添加条件
    if add_conditions:
        for cond in add_conditions:
            structured.conditions.append(SQLCondition(
                field=cond["field"],
                operator=cond.get("operator", "="),
                value=cond["value"],
                logic=cond.get("logic", "AND"),
            ))
    
    # 移除条件
    if remove_conditions:
        structured.conditions = [
            c for c in structured.conditions
            if c.field not in remove_conditions
        ]
    
    # 修改聚合
    if change_aggregation:
        for col in structured.columns:
            if col.expression in change_aggregation:
                col.aggregation = change_aggregation[col.expression]
    
    # 修改分组
    if change_group_by is not None:
        structured.group_by = change_group_by
    
    # 修改排序
    if change_order_by is not None:
        structured.order_by = [
            SQLOrderBy(field=o["field"], direction=o.get("direction", "ASC"))
            for o in change_order_by
        ]
    
    # 修改 LIMIT
    if change_limit is not None:
        structured.limit = change_limit
    
    return structured.to_sql()









