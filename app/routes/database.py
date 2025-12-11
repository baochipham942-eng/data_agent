"""
数据库管理 API 路由。
"""

from pathlib import Path
from typing import Literal, Optional, Dict
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.database_manager import DatabaseManager


class RenameRequest(BaseModel):
    """重命名请求"""
    new_name: str


class SqlQueryRequest(BaseModel):
    """SQL 查询请求"""
    sql: str


def create_database_router(db_manager: DatabaseManager) -> APIRouter:
    """创建数据库管理 API 路由"""
    
    router = APIRouter(prefix="/api/database", tags=["database"])
    
    @router.get("/info")
    async def get_database_info():
        """获取数据库概览信息"""
        info = db_manager.get_database_info()
        return {"success": True, "data": info}
    
    @router.get("/tables")
    async def get_tables():
        """获取所有表信息"""
        tables = db_manager.get_tables()
        return {
            "success": True,
            "data": [
                {
                    "name": t.name,
                    "row_count": t.row_count,
                    "column_count": t.column_count,
                    "size_bytes": t.size_bytes,
                    "columns": [
                        {
                            "name": c.name,
                            "dtype": c.dtype,
                            "nullable": c.nullable,
                        }
                        for c in t.columns
                    ],
                }
                for t in tables
            ],
        }
    
    @router.get("/tables/{table_name}")
    async def get_table_detail(table_name: str):
        """获取表详细信息"""
        schema = db_manager.get_table_schema(table_name)
        if not schema:
            raise HTTPException(status_code=404, detail=f"表 {table_name} 不存在")
        return {"success": True, "data": schema}
    
    @router.get("/tables/{table_name}/preview")
    async def preview_table(table_name: str, limit: int = Query(100, ge=1, le=1000)):
        """预览表数据"""
        preview = db_manager.preview_table(table_name, limit)
        return {"success": True, "data": preview}
    
    @router.post("/upload")
    async def upload_and_parse(file: UploadFile = File(...)):
        """上传文件并解析预览"""
        content = await file.read()
        try:
            result = db_manager.parse_upload(content, file.filename or "upload.csv")
            return {
                "success": True,
                "data": {
                    "filename": file.filename,
                    "columns": [
                        {
                            "name": c.name,
                            "dtype": c.dtype,
                            "nullable": c.nullable,
                            "sample_values": c.sample_values,
                        }
                        for c in result.columns
                    ],
                    "row_count": result.row_count,
                    "preview_data": result.preview_data,
                    "inferred_types": result.inferred_types,
                },
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")
    
    @router.post("/import")
    async def import_data(
        file: UploadFile = File(...),
        table_name: str = Form(...),
        mode: Literal['create', 'replace', 'append'] = Form('replace'),
    ):
        """导入数据到数据库"""
        content = await file.read()
        
        result = db_manager.import_data(
            file_content=content,
            filename=file.filename or "upload.csv",
            table_name=table_name,
            mode=mode,
        )
        
        if result.success:
            return {
                "success": True,
                "data": {
                    "table_name": result.table_name,
                    "rows_imported": result.rows_imported,
                    "message": result.message,
                },
            }
        else:
            raise HTTPException(status_code=400, detail=result.message)
    
    @router.delete("/tables/{table_name}")
    async def delete_table(table_name: str):
        """删除表"""
        result = db_manager.delete_table(table_name)
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    
    @router.post("/tables/{table_name}/rename")
    async def rename_table(table_name: str, request: RenameRequest):
        """重命名表"""
        result = db_manager.rename_table(table_name, request.new_name)
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    
    @router.get("/export/{table_name}")
    async def export_table(table_name: str):
        """导出表为 CSV"""
        try:
            output = db_manager.export_table(table_name)
            return StreamingResponse(
                output,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f'attachment; filename="{table_name}.csv"'
                },
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    @router.post("/refresh-schema")
    async def refresh_schema():
        """刷新 Agent Memory 中的 Schema"""
        count = await db_manager.refresh_schema()
        return {
            "success": True,
            "message": f"Schema 刷新完成",
            "tables_refreshed": count,
        }
    
    @router.post("/query")
    async def execute_query(request: SqlQueryRequest):
        """执行只读 SQL 查询"""
        result = db_manager.execute_sql(request.sql)
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    
    return router









