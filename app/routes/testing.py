"""
测试管理 API 路由
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from app.services.test_runner import TestRunner
from app.config import SYSTEM_DB_PATH

logger = logging.getLogger(__name__)


class RunTestRequest(BaseModel):
    """运行测试请求"""
    test_scopes: List[str] = ["unit", "integration", "service"]  # 测试范围
    test_files: Optional[List[str]] = None  # 可选的测试文件列表


class TestReportResponse(BaseModel):
    """测试报告响应"""
    id: str
    test_scopes: List[str]
    test_count: int
    passed_count: int
    failed_count: int
    error_count: int
    skipped_count: int
    progress: float
    status: str  # running, passed, failed, error
    result: Optional[Dict[str, Any]] = None
    started_at: str
    completed_at: Optional[str] = None
    duration: Optional[float] = None
    created_at: str


def create_testing_router(test_runner: TestRunner) -> APIRouter:
    """创建测试管理路由"""
    router = APIRouter(prefix="/api/testing", tags=["testing"])
    
    async def run_tests_async(report_id: str, test_scopes: List[str], test_files: Optional[List[str]]):
        """异步运行测试"""
        await test_runner.run_tests(report_id, test_scopes, test_files)
    
    @router.post("/run", response_model=Dict[str, str])
    async def run_tests(
        request: RunTestRequest,
        background_tasks: BackgroundTasks,
    ):
        """
        运行测试（后台执行）
        
        Args:
            request: 测试请求，包含测试范围和可选的测试文件
            background_tasks: FastAPI 后台任务
        """
        try:
            # 创建测试报告
            report_id = test_runner.create_test_report(request.test_scopes)
            
            # 在后台运行测试
            background_tasks.add_task(
                run_tests_async,
                report_id,
                request.test_scopes,
                request.test_files,
            )
            
            return {
                "success": True,
                "report_id": report_id,
                "message": "测试已开始运行",
            }
        except Exception as e:
            logger.error(f"启动测试失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/reports", response_model=List[TestReportResponse])
    async def list_reports(
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ):
        """获取测试报告列表"""
        try:
            reports = test_runner.list_reports(limit=limit, offset=offset, status=status)
            return reports
        except Exception as e:
            logger.error(f"获取测试报告列表失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/reports/{report_id}", response_model=TestReportResponse)
    async def get_report(report_id: str):
        """获取测试报告详情"""
        try:
            report = test_runner.get_report(report_id)
            if not report:
                raise HTTPException(status_code=404, detail="测试报告不存在")
            return report
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取测试报告失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.delete("/reports/{report_id}")
    async def delete_report(report_id: str):
        """删除测试报告"""
        try:
            deleted = test_runner.delete_report(report_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="测试报告不存在")
            return {"success": True, "message": "测试报告已删除"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"删除测试报告失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/stats")
    async def get_test_stats():
        """获取测试统计信息"""
        try:
            total = test_runner.get_report_count()
            passed = test_runner.get_report_count("passed")
            failed = test_runner.get_report_count("failed")
            running = test_runner.get_report_count("running")
            error = test_runner.get_report_count("error")
            
            return {
                "total": total,
                "passed": passed,
                "failed": failed,
                "running": running,
                "error": error,
            }
        except Exception as e:
            logger.error(f"获取测试统计失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    return router









