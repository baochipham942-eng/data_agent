"""
查询分析 API 路由。
"""

import asyncio
import logging
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.query_analyzer import QueryAnalyzer

logger = logging.getLogger(__name__)


class AnalyzeRequest(BaseModel):
    """分析请求"""
    question: str


def create_analysis_router(query_analyzer: QueryAnalyzer) -> APIRouter:
    """创建查询分析 API 路由"""
    
    router = APIRouter(prefix="/api/analysis", tags=["analysis"])
    
    @router.post("/analyze")
    async def analyze_question(request: AnalyzeRequest):
        """分析用户问题"""
        try:
            # 【关键修复】将同步方法放到线程池中执行，避免阻塞事件循环
            logger.info(f'[分析API] 开始分析问题: {request.question[:50]}...')
            
            # 使用 asyncio.to_thread 或 run_in_executor 在线程池中执行同步方法
            try:
                # Python 3.9+ 支持
                result = await asyncio.to_thread(query_analyzer.analyze, request.question)
            except AttributeError:
                # Python < 3.9 的回退方案
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, query_analyzer.analyze, request.question)
            
            logger.info(f'[分析API] ✅ 分析完成: {request.question[:50]}...')
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f'[分析API] ❌ 分析失败: {e}', exc_info=True)
            return {"success": False, "error": str(e)}
    
    @router.post("/tables")
    async def get_related_tables(request: AnalyzeRequest):
        """获取相关表"""
        try:
            # 【关键修复】将同步方法放到线程池中执行
            try:
                tables = await asyncio.to_thread(query_analyzer.analyze_tables, request.question)
            except AttributeError:
                loop = asyncio.get_event_loop()
                tables = await loop.run_in_executor(None, query_analyzer.analyze_tables, request.question)
            return {"success": True, "data": tables}
        except Exception as e:
            logger.error(f'[分析API] 获取表失败: {e}', exc_info=True)
            return {"success": False, "error": str(e)}
    
    @router.post("/knowledge")
    async def get_relevant_knowledge(request: AnalyzeRequest):
        """获取相关业务知识"""
        try:
            # 【关键修复】将同步方法放到线程池中执行
            try:
                knowledge = await asyncio.to_thread(query_analyzer.get_relevant_knowledge, request.question)
            except AttributeError:
                loop = asyncio.get_event_loop()
                knowledge = await loop.run_in_executor(None, query_analyzer.get_relevant_knowledge, request.question)
            return {"success": True, "data": knowledge}
        except Exception as e:
            logger.error(f'[分析API] 获取知识失败: {e}', exc_info=True)
            return {"success": False, "error": str(e)}
    
    @router.get("/schema")
    async def get_schema():
        """获取数据库结构信息"""
        try:
            # 【关键修复】将同步方法放到线程池中执行
            try:
                table_info = await asyncio.to_thread(query_analyzer.get_table_info)
            except AttributeError:
                loop = asyncio.get_event_loop()
                table_info = await loop.run_in_executor(None, query_analyzer.get_table_info)
            
            return {
                "success": True,
                "data": {
                    "tables": [
                        {
                            "name": name,
                            "columns": info["column_names"],
                            "row_count": info["row_count"],
                        }
                        for name, info in table_info.items()
                    ]
                }
            }
        except Exception as e:
            logger.error(f'[分析API] 获取schema失败: {e}', exc_info=True)
            return {"success": False, "error": str(e)}
    
    return router

