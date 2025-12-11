"""
增强版评测 API 路由。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class EvaluateRequest(BaseModel):
    conversation_id: str
    question: str
    sql: Optional[str] = None
    result_summary: Optional[str] = None
    answer: Optional[str] = None


class DimensionScoreResponse(BaseModel):
    name: str
    score: float
    max_score: float
    weight: float
    reasoning: str
    sub_scores: Dict[str, float]


class EvaluationResultResponse(BaseModel):
    conversation_id: str
    analysis_insight: Optional[DimensionScoreResponse] = None
    visualization: Optional[DimensionScoreResponse] = None
    robustness: Optional[DimensionScoreResponse] = None
    overall_score: float
    evaluation_level: str
    evaluation_level_label: str
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    evaluated_at: str


class AggregateReportResponse(BaseModel):
    period_days: int
    total_evaluations: int
    average_score: float
    dimension_scores: Dict[str, float]
    level_distribution: Dict[str, int]
    top_weaknesses: List[Dict[str, Any]]


def create_enhanced_evaluation_router(
    evaluator,
    report_generator,
) -> APIRouter:
    """创建增强版评测路由"""
    
    router = APIRouter(prefix="/api/enhanced-evaluation", tags=["enhanced-evaluation"])
    
    @router.post("/evaluate", response_model=EvaluationResultResponse)
    async def evaluate(request: EvaluateRequest) -> EvaluationResultResponse:
        """执行多维度评测"""
        if not evaluator:
            raise HTTPException(status_code=503, detail="评测服务未初始化")
        
        try:
            result = await evaluator.evaluate(
                conversation_id=request.conversation_id,
                question=request.question,
                sql=request.sql,
                result_summary=request.result_summary or "",
                answer=request.answer or "",
            )
            
            # 保存评测结果
            if report_generator:
                report_generator.save_evaluation(result)
            
            level_labels = {
                "pass": "达标级",
                "industrial": "工业可用级",
                "professional": "专业研究级",
            }
            
            def dim_to_response(dim) -> Optional[DimensionScoreResponse]:
                if not dim:
                    return None
                return DimensionScoreResponse(
                    name=dim.name,
                    score=dim.score,
                    max_score=dim.max_score,
                    weight=dim.weight,
                    reasoning=dim.reasoning,
                    sub_scores=dim.sub_scores,
                )
            
            return EvaluationResultResponse(
                conversation_id=result.conversation_id,
                analysis_insight=dim_to_response(result.analysis_insight),
                visualization=dim_to_response(result.visualization),
                robustness=dim_to_response(result.robustness),
                overall_score=result.overall_score,
                evaluation_level=result.evaluation_level.value,
                evaluation_level_label=level_labels.get(result.evaluation_level.value, "未知"),
                strengths=result.strengths,
                weaknesses=result.weaknesses,
                recommendations=result.recommendations,
                evaluated_at=result.evaluated_at,
            )
        except Exception as e:
            logger.error(f"评测失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/result/{conversation_id}", response_model=Optional[EvaluationResultResponse])
    async def get_evaluation_result(conversation_id: str):
        """获取评测结果"""
        if not report_generator:
            raise HTTPException(status_code=503, detail="评测报告服务未初始化")
        
        result = report_generator.get_evaluation(conversation_id)
        
        if not result:
            return None
        
        level_labels = {
            "pass": "达标级",
            "industrial": "工业可用级",
            "professional": "专业研究级",
        }
        
        def dim_to_response(dim) -> Optional[DimensionScoreResponse]:
            if not dim:
                return None
            return DimensionScoreResponse(
                name=dim.name,
                score=dim.score,
                max_score=dim.max_score,
                weight=dim.weight,
                reasoning=dim.reasoning,
                sub_scores=dim.sub_scores,
            )
        
        return EvaluationResultResponse(
            conversation_id=result.conversation_id,
            analysis_insight=dim_to_response(result.analysis_insight),
            visualization=dim_to_response(result.visualization),
            robustness=dim_to_response(result.robustness),
            overall_score=result.overall_score,
            evaluation_level=result.evaluation_level.value,
            evaluation_level_label=level_labels.get(result.evaluation_level.value, "未知"),
            strengths=result.strengths,
            weaknesses=result.weaknesses,
            recommendations=result.recommendations,
            evaluated_at=result.evaluated_at,
        )
    
    @router.get("/aggregate-report", response_model=AggregateReportResponse)
    async def get_aggregate_report(days: int = 7) -> AggregateReportResponse:
        """获取聚合评测报告"""
        if not report_generator:
            raise HTTPException(status_code=503, detail="评测报告服务未初始化")
        
        report = report_generator.generate_aggregate_report(days)
        
        return AggregateReportResponse(
            period_days=report["period_days"],
            total_evaluations=report["total_evaluations"],
            average_score=report["average_score"],
            dimension_scores=report["dimension_scores"],
            level_distribution=report["level_distribution"],
            top_weaknesses=report["top_weaknesses"],
        )
    
    return router









