"""
测试运行服务 - 管理和执行自动化测试
"""
import asyncio
import json
import sqlite3
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class TestRunner:
    """测试运行器"""
    
    def __init__(self, db_path: Path):
        """
        初始化测试运行器。
        
        Args:
            db_path: 数据库路径（使用系统数据库）
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
        """初始化数据库表"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        # 测试报告表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS test_reports (
                id TEXT PRIMARY KEY,
                test_scopes TEXT NOT NULL,
                test_count INTEGER DEFAULT 0,
                passed_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                skipped_count INTEGER DEFAULT 0,
                progress REAL DEFAULT 0.0,
                status TEXT DEFAULT 'running',
                result TEXT,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                duration REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 测试结果详情表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS test_report_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id TEXT NOT NULL,
                test_name TEXT NOT NULL,
                test_file TEXT NOT NULL,
                status TEXT NOT NULL,
                duration REAL,
                error_message TEXT,
                error_traceback TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(report_id) REFERENCES test_reports(id)
            )
        """)
        
        # 创建索引
        cur.execute("CREATE INDEX IF NOT EXISTS idx_report_status ON test_reports(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_report_created ON test_reports(created_at DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_detail_report ON test_report_details(report_id)")
        
        conn.commit()
        conn.close()
    
    def create_test_report(self, test_scopes: List[str]) -> str:
        """
        创建新的测试报告记录。
        
        Args:
            test_scopes: 测试范围列表，如 ['unit', 'integration', 'service']
        
        Returns:
            测试报告 ID
        """
        report_id = str(uuid.uuid4())
        conn = self._get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO test_reports (id, test_scopes, status, progress)
            VALUES (?, ?, ?, ?)
        """, (report_id, json.dumps(test_scopes), 'running', 0.0))
        
        conn.commit()
        conn.close()
        
        logger.info(f"创建测试报告: {report_id}, 测试范围: {test_scopes}")
        return report_id
    
    async def run_tests(
        self,
        report_id: str,
        test_scopes: List[str],
        test_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        运行测试。
        
        Args:
            report_id: 测试报告 ID
            test_scopes: 测试范围列表
            test_files: 可选的测试文件列表
        
        Returns:
            测试结果
        """
        try:
            # 更新状态为运行中
            self._update_report_status(report_id, 'running', 0.0)
            
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            
            # 运行测试（在后台线程中运行以避免阻塞）
            loop = asyncio.get_event_loop()
            
            # 简化命令（去掉 json-report 相关，因为可能没有安装）
            # 使用 python -m pytest 确保使用正确的环境
            import sys
            python_executable = sys.executable
            simplified_cmd = [python_executable, "-m", "pytest", "-v", "--tb=short"]
            
            # 根据测试范围添加标记
            if test_scopes:
                markers = " or ".join([f"({scope})" for scope in test_scopes])
                simplified_cmd.extend(["-m", markers])
            
            # 添加测试文件
            if test_files:
                simplified_cmd.extend(test_files)
            else:
                simplified_cmd.append("tests/")
            
            process = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    simplified_cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(project_root),
                    timeout=300,  # 5分钟超时
                )
            )
            
            # 解析结果
            result = self._parse_pytest_output(process.stdout, process.stderr, process.returncode)
            
            # 更新报告
            self._update_report_result(report_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"运行测试失败: {e}", exc_info=True)
            error_result = {
                "status": "error",
                "error": str(e),
                "test_count": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
            }
            self._update_report_status(report_id, 'error', 100.0, error_result)
            return error_result
    
    def _parse_pytest_output(self, stdout: str, stderr: str, return_code: int) -> Dict[str, Any]:
        """解析 pytest 输出"""
        # 简单的输出解析（可以改进使用 pytest-json-report 插件）
        lines = stdout.split('\n')
        
        # 统计测试数量
        test_count = 0
        passed = 0
        failed = 0
        errors = 0
        skipped = 0
        
        for line in lines:
            if "passed" in line.lower() and "failed" not in line.lower():
                # 解析类似 "36 passed" 的行
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "passed":
                        try:
                            passed = int(parts[i-1])
                            test_count += passed
                        except:
                            pass
                    elif part == "failed":
                        try:
                            failed = int(parts[i-1])
                            test_count += failed
                        except:
                            pass
                    elif part == "error" or part == "errors":
                        try:
                            errors = int(parts[i-1])
                            test_count += errors
                        except:
                            pass
                    elif part == "skipped":
                        try:
                            skipped = int(parts[i-1])
                            test_count += skipped
                        except:
                            pass
        
        # 如果没有解析到，尝试从最后的汇总行解析
        if test_count == 0:
            summary_line = lines[-2] if len(lines) > 1 else ""
            if "passed" in summary_line or "failed" in summary_line:
                # 尝试提取数字
                import re
                numbers = re.findall(r'\d+', summary_line)
                if numbers:
                    passed = int(numbers[0]) if len(numbers) > 0 else 0
                    failed = int(numbers[1]) if len(numbers) > 1 else 0
                    test_count = passed + failed
        
        status = "passed" if return_code == 0 and failed == 0 and errors == 0 else "failed"
        
        return {
            "status": status,
            "test_count": test_count,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code,
        }
    
    def _update_report_status(
        self,
        report_id: str,
        status: str,
        progress: float,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """更新报告状态"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        if result:
            cur.execute("""
                UPDATE test_reports
                SET status = ?, progress = ?, result = ?,
                    test_count = ?, passed_count = ?, failed_count = ?,
                    error_count = ?, skipped_count = ?,
                    completed_at = CURRENT_TIMESTAMP,
                    duration = (julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400
                WHERE id = ?
            """, (
                status,
                progress,
                json.dumps(result),
                result.get("test_count", 0),
                result.get("passed", 0),
                result.get("failed", 0),
                result.get("errors", 0),
                result.get("skipped", 0),
                report_id,
            ))
        else:
            cur.execute("""
                UPDATE test_reports
                SET status = ?, progress = ?
                WHERE id = ?
            """, (status, progress, report_id))
        
        conn.commit()
        conn.close()
    
    def _update_report_result(self, report_id: str, result: Dict[str, Any]) -> None:
        """更新测试结果"""
        status = "passed" if result.get("status") == "passed" else "failed"
        if result.get("status") == "error":
            status = "error"
        
        self._update_report_status(report_id, status, 100.0, result)
    
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """获取测试报告"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM test_reports WHERE id = ?", (report_id,))
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return None
        
        report = dict(row)
        if report.get("test_scopes"):
            report["test_scopes"] = json.loads(report["test_scopes"])
        if report.get("result"):
            report["result"] = json.loads(report["result"])
        
        return report
    
    def list_reports(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出测试报告"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        query = "SELECT * FROM test_reports WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        
        reports = []
        for row in rows:
            report = dict(row)
            if report.get("test_scopes"):
                report["test_scopes"] = json.loads(report["test_scopes"])
            reports.append(report)
        
        return reports
    
    def get_report_count(self, status: Optional[str] = None) -> int:
        """获取报告数量"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        if status:
            cur.execute("SELECT COUNT(*) FROM test_reports WHERE status = ?", (status,))
        else:
            cur.execute("SELECT COUNT(*) FROM test_reports")
        
        count = cur.fetchone()[0]
        conn.close()
        return count
    
    def delete_report(self, report_id: str) -> bool:
        """删除测试报告"""
        conn = self._get_conn()
        cur = conn.cursor()
        
        # 先删除详情
        cur.execute("DELETE FROM test_report_details WHERE report_id = ?", (report_id,))
        
        # 再删除报告
        cur.execute("DELETE FROM test_reports WHERE id = ?", (report_id,))
        
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted

