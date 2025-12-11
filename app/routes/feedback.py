"""
反馈与评测 API 路由。

提供：
- 用户反馈提交
- LLM 自动评估
- 反馈学习触发
- 优化报告获取
"""

import json
import sqlite3
import logging
from typing import Optional, List
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import LOGS_DB_PATH
from app.services.llm_judge import (
    LLMJudge,
    FeedbackLearner,
    AutoOptimizer,
    EvaluationResult,
)

logger = logging.getLogger(__name__)


# ============ 请求/响应模型 ============

class FeedbackSubmitRequest(BaseModel):
    """提交专家评分请求"""
    conversation_id: str
    rating: int = Field(..., ge=1, le=5, description="专家评分 1-5")
    comment: Optional[str] = Field(None, description="评论")
    auto_learn: bool = Field(True, description="是否自动学习")


class UserVoteRequest(BaseModel):
    """用户点赞/点踩请求"""
    conversation_id: str
    vote: str = Field(..., description="用户评价: 'like' | 'dislike' | 'none'")


class FeedbackSubmitResponse(BaseModel):
    """提交反馈响应"""
    success: bool
    message: str
    learning_result: Optional[dict] = None


class LLMEvaluateRequest(BaseModel):
    """LLM 评估请求"""
    conversation_id: str
    force: bool = Field(False, description="强制重新评估")


class LLMEvaluateResponse(BaseModel):
    """LLM 评估响应"""
    success: bool
    evaluation: Optional[dict] = None
    error: Optional[str] = None


class BatchEvaluateRequest(BaseModel):
    """批量评估请求"""
    conversation_ids: Optional[List[str]] = Field(None, description="指定会话ID，为空则评估最近的")
    limit: int = Field(10, ge=1, le=50, description="评估数量")
    skip_evaluated: bool = Field(True, description="跳过已评估的")


class OptimizationReportResponse(BaseModel):
    """优化报告响应"""
    weakness_report: dict
    suggestions: List[str]
    total_feedbacks: int
    high_score_count: int
    low_score_count: int


# ============ 数据库操作 ============

def _get_conn():
    """获取数据库连接"""
    return sqlite3.connect(str(LOGS_DB_PATH))


def _init_feedback_table():
    """初始化反馈表"""
    conn = _get_conn()
    cur = conn.cursor()
    
    # 创建反馈表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversation_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            user_vote TEXT,
            expert_rating INTEGER,
            user_comment TEXT,
            llm_evaluation TEXT,
            llm_overall_score REAL,
            learned BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(conversation_id)
        )
    """)
    
    # 尝试添加新字段（兼容旧表）
    try:
        cur.execute("ALTER TABLE conversation_feedback ADD COLUMN user_vote TEXT")
    except:
        pass  # 字段已存在
    
    try:
        cur.execute("ALTER TABLE conversation_feedback ADD COLUMN expert_rating INTEGER")
    except:
        pass  # 字段已存在
    
    # 迁移旧数据：user_rating -> expert_rating
    try:
        cur.execute("""
            UPDATE conversation_feedback 
            SET expert_rating = user_rating 
            WHERE expert_rating IS NULL AND user_rating IS NOT NULL
        """)
    except:
        pass
    
    # 创建索引
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_feedback_conversation_id 
        ON conversation_feedback(conversation_id)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_feedback_score 
        ON conversation_feedback(llm_overall_score)
    """)
    
    conn.commit()
    conn.close()


def _save_feedback(
    conversation_id: str,
    user_vote: Optional[str] = None,  # 'like' | 'dislike' | 'none'
    expert_rating: Optional[int] = None,
    user_comment: Optional[str] = None,
    llm_evaluation: Optional[EvaluationResult] = None,
    learned: bool = False,
):
    """保存反馈"""
    conn = _get_conn()
    cur = conn.cursor()
    
    llm_eval_json = json.dumps(asdict(llm_evaluation)) if llm_evaluation else None
    llm_score = llm_evaluation.overall_score if llm_evaluation else None
    
    cur.execute("""
        INSERT INTO conversation_feedback 
        (conversation_id, user_vote, expert_rating, user_comment, llm_evaluation, llm_overall_score, learned)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(conversation_id) DO UPDATE SET
            user_vote = COALESCE(excluded.user_vote, user_vote),
            expert_rating = COALESCE(excluded.expert_rating, expert_rating),
            user_comment = COALESCE(excluded.user_comment, user_comment),
            llm_evaluation = COALESCE(excluded.llm_evaluation, llm_evaluation),
            llm_overall_score = COALESCE(excluded.llm_overall_score, llm_overall_score),
            learned = excluded.learned OR learned
    """, (conversation_id, user_vote, expert_rating, user_comment, llm_eval_json, llm_score, learned))
    
    conn.commit()
    conn.close()


def _get_feedback(conversation_id: str) -> Optional[dict]:
    """获取反馈"""
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM conversation_feedback WHERE conversation_id = ?
    """, (conversation_id,))
    
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return dict(row)


def _get_conversation_data(conversation_id: str) -> Optional[dict]:
    """获取会话数据"""
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # 获取会话信息
    cur.execute("SELECT * FROM conversation WHERE id = ?", (conversation_id,))
    conv = cur.fetchone()
    
    if not conv:
        conn.close()
        return None
    
    # 获取消息
    cur.execute("""
        SELECT role, content, created_at
        FROM conversation_message
        WHERE conversation_id = ?
        ORDER BY created_at
    """, (conversation_id,))
    
    messages = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    return {
        "conversation": dict(conv),
        "messages": messages,
    }


def _get_feedback_stats() -> dict:
    """获取反馈统计"""
    conn = _get_conn()
    cur = conn.cursor()
    
    stats = {"total": 0, "high_score": 0, "low_score": 0}
    
    try:
        cur.execute("SELECT COUNT(*) FROM conversation_feedback")
        stats["total"] = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*) FROM conversation_feedback 
            WHERE (user_rating >= 4 OR llm_overall_score >= 4.0)
        """)
        stats["high_score"] = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*) FROM conversation_feedback 
            WHERE (user_rating <= 2 OR llm_overall_score <= 2.5)
        """)
        stats["low_score"] = cur.fetchone()[0]
    except:
        pass
    
    conn.close()
    return stats


# ============ 路由创建 ============

def create_feedback_router(
    agent_memory,
    llm_service,
    prompt_manager=None,
    rag_knowledge_base=None,  # RAG 知识库实例（可选）
) -> APIRouter:
    """
    创建反馈路由。
    
    Args:
        agent_memory: Agent Memory 实例
        llm_service: LLM 服务实例
        prompt_manager: Prompt管理器（可选）
        rag_knowledge_base: RAG 知识库实例（可选）
    """
    router = APIRouter(prefix="/api/feedback", tags=["feedback"])
    
    # 初始化表
    _init_feedback_table()
    
    # 初始化 RAG 相关服务（如果提供了 RAG 知识库）
    rag_learner = None
    if rag_knowledge_base:
        from app.services.rag_learner import RAGLearner
        rag_learner = RAGLearner(rag_knowledge_base)
        logger.info("RAG 学习器已初始化")
    
    # 初始化服务
    llm_judge = LLMJudge(llm_service, prompt_manager=prompt_manager)
    feedback_learner = FeedbackLearner(agent_memory, llm_judge, rag_learner=rag_learner)
    auto_optimizer = AutoOptimizer(agent_memory, llm_service)
    
    @router.get("/scores")
    async def get_all_scores():
        """
        获取所有会话的评分（用户打分、专家打分、模型打分）。
        """
        conn = _get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                conversation_id,
                user_vote,
                expert_rating,
                llm_overall_score,
                llm_evaluation,
                created_at
            FROM conversation_feedback
        """)
        
        rows = cur.fetchall()
        conn.close()
        
        scores = []
        for row in rows:
            conv_id, user_vote, expert_rating, llm_score, llm_eval_json, created_at = row
            
            # 解析用户投票为分数
            user_vote_score = None
            if user_vote == 'like':
                user_vote_score = 5.0
            elif user_vote == 'dislike':
                user_vote_score = 1.0
            
            # 解析 LLM 评估解释 - 使用正确的字段名
            llm_explanation = ""
            if llm_eval_json:
                try:
                    llm_eval = json.loads(llm_eval_json)
                    # 构建解释文本
                    parts = []
                    if llm_eval.get("reasoning"):
                        parts.append(f"📝 评估理由：{llm_eval['reasoning']}")
                    if llm_eval.get("strengths"):
                        parts.append(f"✅ 优点：{'；'.join(llm_eval['strengths'])}")
                    if llm_eval.get("weaknesses"):
                        parts.append(f"⚠️ 不足：{'；'.join(llm_eval['weaknesses'])}")
                    if llm_eval.get("suggestions"):
                        parts.append(f"💡 建议：{'；'.join(llm_eval['suggestions'])}")
                    
                    llm_explanation = '\n\n'.join(parts) if parts else (
                        f"SQL正确性: {llm_eval.get('sql_correctness', '-')}/5, "
                        f"结果解读: {llm_eval.get('result_interpretation', '-')}/5, "
                        f"完整性: {llm_eval.get('answer_completeness', '-')}/5, "
                        f"清晰度: {llm_eval.get('expression_clarity', '-')}/5"
                    )
                except:
                    pass
            
            scores.append({
                "conversation_id": conv_id,
                "user_vote": user_vote,
                "user_vote_score": user_vote_score,
                "expert_score": expert_rating,
                "llm_score": llm_score,
                "llm_explanation": llm_explanation,
                "evaluated_at": created_at,
            })
        
        return {"success": True, "scores": scores}
    
    @router.post("/{conversation_id}/expert-score")
    async def save_expert_score(conversation_id: str, data: dict):
        """
        保存专家评分。
        """
        score = data.get("score")
        if not score or not isinstance(score, (int, float)) or score < 1 or score > 5:
            raise HTTPException(status_code=400, detail="评分必须在 1-5 之间")
        
        _save_feedback(
            conversation_id=conversation_id,
            expert_rating=int(score),
        )
        
        return {"success": True, "message": "专家评分已保存"}
    
    @router.post("/submit", response_model=FeedbackSubmitResponse)
    async def submit_feedback(request: FeedbackSubmitRequest):
        """
        提交专家评分。
        
        - 保存专家评分（1-5星）
        - 如果评分高，触发自动学习
        """
        conv_data = _get_conversation_data(request.conversation_id)
        if not conv_data:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 提取用户问题和 AI 回答
        user_question = ""
        ai_response = ""
        generated_sql = None
        
        for msg in conv_data["messages"]:
            if msg["role"] == "user" and not user_question:
                user_question = msg["content"]
            elif msg["role"] == "assistant":
                ai_response = msg["content"]
                # 尝试提取 SQL
                if "SELECT" in msg["content"].upper():
                    import re
                    sql_match = re.search(
                        r'(SELECT\s+.+?(?:;|$))', 
                        msg["content"], 
                        re.IGNORECASE | re.DOTALL
                    )
                    if sql_match:
                        generated_sql = sql_match.group(1)
        
        learning_result = None
        
        # 自动学习
        if request.auto_learn:
            learning_result = await feedback_learner.learn_from_feedback(
                conversation_id=request.conversation_id,
                user_question=user_question,
                generated_sql=generated_sql,
                ai_response=ai_response,
                expert_rating=request.rating,  # 专家评分
                user_rating=None,  # 用户评分（这里没有，因为这是专家评分接口）
            )
            
            # 记录弱项
            if learning_result.get("action") == "analyzed_weakness":
                analysis = learning_result.get("details", {}).get("analysis", {})
                if analysis.get("category"):
                    auto_optimizer.record_weakness(analysis["category"])
        
        # 保存反馈
        _save_feedback(
            conversation_id=request.conversation_id,
            expert_rating=request.rating,
            user_comment=request.comment,
            learned=learning_result.get("learned", False) if learning_result else False,
        )
        
        return FeedbackSubmitResponse(
            success=True,
            message="专家评分已提交",
            learning_result=learning_result,
        )
    
    @router.post("/vote")
    async def submit_user_vote(request: UserVoteRequest):
        """
        提交用户点赞/点踩。
        
        - vote: 'like' | 'dislike' | 'none'
        """
        if request.vote not in ['like', 'dislike', 'none']:
            raise HTTPException(status_code=400, detail="无效的评价类型")
        
        # 保存用户评价
        _save_feedback(
            conversation_id=request.conversation_id,
            user_vote=request.vote if request.vote != 'none' else None,
        )
        
        return {
            "success": True,
            "message": "用户评价已保存",
            "vote": request.vote,
        }
    
    @router.post("/{conversation_id}/vote")
    async def submit_user_vote_by_id(conversation_id: str, data: dict):
        """
        通过路径参数提交用户点赞/点踩。
        """
        vote = data.get("vote", "")
        if vote not in ['like', 'dislike', 'none']:
            raise HTTPException(status_code=400, detail="无效的评价类型")
        
        # 保存用户评价
        _save_feedback(
            conversation_id=conversation_id,
            user_vote=vote if vote != 'none' else None,
        )
        
        return {
            "success": True,
            "message": "用户评价已保存",
            "vote": vote,
        }
    
    @router.get("/{conversation_id}")
    async def get_feedback_by_id(conversation_id: str):
        """
        获取会话的反馈信息。
        """
        feedback = _get_feedback(conversation_id)
        if not feedback:
            return {"exists": False}
        
        return {
            "exists": True,
            "feedback": {
                "user_vote": feedback.get("user_vote"),
                "expert_rating": feedback.get("expert_rating"),
                "llm_score": feedback.get("llm_overall_score"),
            }
        }
    
    @router.post("/evaluate", response_model=LLMEvaluateResponse)
    async def llm_evaluate(request: LLMEvaluateRequest):
        """
        使用 LLM 评估会话质量。
        """
        # 检查是否已评估
        if not request.force:
            existing = _get_feedback(request.conversation_id)
            if existing and existing.get("llm_evaluation"):
                return LLMEvaluateResponse(
                    success=True,
                    evaluation=json.loads(existing["llm_evaluation"]),
                )
        
        # 获取会话数据
        conv_data = _get_conversation_data(request.conversation_id)
        if not conv_data:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 提取数据
        user_question = ""
        ai_response = ""
        generated_sql = None
        sql_result = None
        
        for msg in conv_data["messages"]:
            if msg["role"] == "user" and not user_question:
                user_question = msg["content"]
            elif msg["role"] == "assistant":
                content = msg["content"]
                ai_response = content
                
                # 提取 SQL 和结果（简化处理）
                if "SELECT" in content.upper():
                    import re
                    sql_match = re.search(
                        r'(SELECT\s+.+?(?:;|$))', 
                        content, 
                        re.IGNORECASE | re.DOTALL
                    )
                    if sql_match:
                        generated_sql = sql_match.group(1)
        
        try:
            # 执行 LLM 评估
            evaluation = await llm_judge.evaluate(
                user_question=user_question,
                generated_sql=generated_sql,
                sql_result=sql_result,
                ai_response=ai_response,
            )
            
            # 保存评估结果
            _save_feedback(
                conversation_id=request.conversation_id,
                llm_evaluation=evaluation,
            )
            
            # 获取已有的专家评分（如果有）
            existing_feedback = _get_feedback(request.conversation_id)
            expert_rating = existing_feedback.get("expert_rating") if existing_feedback else None
            
            # 触发学习
            learning_result = await feedback_learner.learn_from_feedback(
                conversation_id=request.conversation_id,
                user_question=user_question,
                generated_sql=generated_sql,
                ai_response=ai_response,
                expert_rating=expert_rating,  # 传递专家评分（如果有）
                llm_evaluation=evaluation,
            )
            
            # 记录弱项
            if learning_result.get("action") == "analyzed_weakness":
                analysis = learning_result.get("details", {}).get("analysis", {})
                if analysis.get("category"):
                    auto_optimizer.record_weakness(analysis["category"])
            
            return LLMEvaluateResponse(
                success=True,
                evaluation=asdict(evaluation),
            )
            
        except Exception as e:
            logger.error(f"LLM 评估失败: {e}")
            return LLMEvaluateResponse(
                success=False,
                error=str(e),
            )
    
    @router.post("/batch-evaluate")
    async def batch_evaluate(request: BatchEvaluateRequest):
        """
        批量 LLM 评估。
        """
        conn = _get_conn()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # 获取待评估的会话
        if request.conversation_ids:
            placeholders = ",".join(["?" for _ in request.conversation_ids])
            cur.execute(f"""
                SELECT id FROM conversation 
                WHERE id IN ({placeholders})
                ORDER BY started_at DESC
            """, request.conversation_ids)
        else:
            if request.skip_evaluated:
                cur.execute("""
                    SELECT c.id FROM conversation c
                    LEFT JOIN conversation_feedback f ON c.id = f.conversation_id
                    WHERE f.llm_evaluation IS NULL
                    ORDER BY c.started_at DESC
                    LIMIT ?
                """, (request.limit,))
            else:
                cur.execute("""
                    SELECT id FROM conversation
                    ORDER BY started_at DESC
                    LIMIT ?
                """, (request.limit,))
        
        conversation_ids = [row["id"] for row in cur.fetchall()]
        conn.close()
        
        results = []
        for conv_id in conversation_ids:
            try:
                result = await llm_evaluate(LLMEvaluateRequest(
                    conversation_id=conv_id,
                    force=not request.skip_evaluated,
                ))
                results.append({
                    "conversation_id": conv_id,
                    "success": result.success,
                    "score": result.evaluation.get("overall_score") if result.evaluation else None,
                })
            except Exception as e:
                results.append({
                    "conversation_id": conv_id,
                    "success": False,
                    "error": str(e),
                })
        
        return {
            "total": len(conversation_ids),
            "results": results,
        }
    
    @router.get("/optimization-report", response_model=OptimizationReportResponse)
    async def get_optimization_report():
        """
        获取优化报告。
        """
        stats = _get_feedback_stats()
        
        return OptimizationReportResponse(
            weakness_report=auto_optimizer.get_weakness_report(),
            suggestions=auto_optimizer.suggest_prompt_improvements(),
            total_feedbacks=stats["total"],
            high_score_count=stats["high_score"],
            low_score_count=stats["low_score"],
        )
    
    @router.get("/fewshot-examples/{category}")
    async def get_fewshot_examples(category: str, limit: int = 3):
        """
        获取指定类别的 Few-shot 示例。
        """
        examples = await auto_optimizer.generate_fewshot_examples(category, limit)
        return {
            "category": category,
            "examples": examples,
        }
    
    @router.get("/{conversation_id}")
    async def get_feedback(conversation_id: str):
        """
        获取会话的反馈信息。
        """
        feedback = _get_feedback(conversation_id)
        if not feedback:
            return {"exists": False}
        
        # 解析 LLM 评估
        if feedback.get("llm_evaluation"):
            feedback["llm_evaluation"] = json.loads(feedback["llm_evaluation"])
        
        return {
            "exists": True,
            "feedback": feedback,
        }
    
    return router

