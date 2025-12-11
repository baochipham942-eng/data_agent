"""
SQL 编辑 API 路由。

提供：
- SQL 解析为结构化格式
- SQL 修改
- SQL 重新生成
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.sql_parser import parse_sql, modify_sql, StructuredSQL


# ============ 请求/响应模型 ============

class ParseSQLRequest(BaseModel):
    """解析 SQL 请求"""
    sql: str


class ModifySQLRequest(BaseModel):
    """修改 SQL 请求"""
    sql: str
    add_conditions: Optional[List[Dict[str, Any]]] = None
    remove_conditions: Optional[List[str]] = None
    change_aggregation: Optional[Dict[str, str]] = None
    change_group_by: Optional[List[str]] = None
    change_order_by: Optional[List[Dict[str, str]]] = None
    change_limit: Optional[int] = None


class RebuildSQLRequest(BaseModel):
    """重建 SQL 请求"""
    structured: Dict[str, Any]


# ============ 路由创建 ============

def create_sql_editor_router() -> APIRouter:
    """创建 SQL 编辑路由"""
    router = APIRouter(prefix="/api/sql-editor", tags=["sql-editor"])
    
    @router.post("/parse")
    async def parse_sql_api(request: ParseSQLRequest):
        """
        解析 SQL 为结构化格式。
        
        返回：
        - columns: 列定义（包括聚合函数、别名）
        - table: 主表
        - joins: JOIN 信息
        - conditions: WHERE 条件
        - group_by: 分组字段
        - having: HAVING 条件
        - order_by: 排序
        - limit/offset: 分页
        """
        try:
            structured = parse_sql(request.sql)
            return {
                "success": True,
                "data": structured.to_dict(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    @router.post("/modify")
    async def modify_sql_api(request: ModifySQLRequest):
        """
        修改 SQL。
        
        支持的修改：
        - add_conditions: 添加 WHERE 条件
        - remove_conditions: 移除 WHERE 条件
        - change_aggregation: 修改聚合函数
        - change_group_by: 修改分组
        - change_order_by: 修改排序
        - change_limit: 修改 LIMIT
        """
        try:
            new_sql = modify_sql(
                sql=request.sql,
                add_conditions=request.add_conditions,
                remove_conditions=request.remove_conditions,
                change_aggregation=request.change_aggregation,
                change_group_by=request.change_group_by,
                change_order_by=request.change_order_by,
                change_limit=request.change_limit,
            )
            return {
                "success": True,
                "data": {
                    "original_sql": request.sql,
                    "modified_sql": new_sql,
                },
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    @router.post("/rebuild")
    async def rebuild_sql_api(request: RebuildSQLRequest):
        """
        从结构化数据重建 SQL。
        """
        try:
            structured = StructuredSQL.from_dict(request.structured)
            new_sql = structured.to_sql()
            return {
                "success": True,
                "data": {
                    "sql": new_sql,
                },
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    @router.get("/aggregations")
    async def get_aggregations():
        """获取支持的聚合函数列表"""
        return {
            "success": True,
            "data": [
                {"name": "SUM", "label": "求和", "description": "计算数值总和"},
                {"name": "AVG", "label": "平均值", "description": "计算数值平均值"},
                {"name": "COUNT", "label": "计数", "description": "统计行数"},
                {"name": "MAX", "label": "最大值", "description": "取最大值"},
                {"name": "MIN", "label": "最小值", "description": "取最小值"},
            ],
        }
    
    @router.get("/operators")
    async def get_operators():
        """获取支持的运算符列表"""
        return {
            "success": True,
            "data": [
                {"name": "=", "label": "等于"},
                {"name": "!=", "label": "不等于"},
                {"name": ">", "label": "大于"},
                {"name": ">=", "label": "大于等于"},
                {"name": "<", "label": "小于"},
                {"name": "<=", "label": "小于等于"},
                {"name": "LIKE", "label": "模糊匹配"},
                {"name": "IN", "label": "包含"},
                {"name": "BETWEEN", "label": "范围"},
                {"name": "IS NULL", "label": "为空"},
                {"name": "IS NOT NULL", "label": "不为空"},
            ],
        }
    
    return router









