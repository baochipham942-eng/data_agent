"""
SQL 增强 API 路由。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ValidateSQLRequest(BaseModel):
    sql: str


class ValidateSQLResponse(BaseModel):
    is_valid: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    suggestions: List[str] = []


class FixSQLRequest(BaseModel):
    sql: str
    error_message: str


class FixSQLResponse(BaseModel):
    success: bool
    original_sql: str
    fixed_sql: Optional[str] = None
    fix_description: Optional[str] = None
    attempts: int = 0


class GetExamplesRequest(BaseModel):
    question: str
    top_k: int = 3


class GetExamplesResponse(BaseModel):
    examples: List[Dict[str, Any]]
    formatted: str


class ClassifyIntentRequest(BaseModel):
    user_input: str
    last_query: Optional[str] = None
    last_sql: Optional[str] = None


class ClassifyIntentResponse(BaseModel):
    intent: str
    intent_label: str
    confidence: float


class RewriteQueryRequest(BaseModel):
    question: str
    conversation_id: str
    intent: str


class RewriteQueryResponse(BaseModel):
    original: str
    rewritten: str
    intent: str
    context_used: bool
    modifications: List[str] = []


class ModifySQLRequest(BaseModel):
    original_sql: str
    modification_request: str


class ModifySQLResponse(BaseModel):
    success: bool
    original_sql: str
    modified_sql: Optional[str] = None


class UpdateContextRequest(BaseModel):
    conversation_id: str
    question: str
    sql: Optional[str] = None
    result_data: Optional[List[Dict[str, Any]]] = None


class UpdateContextResponse(BaseModel):
    success: bool
    context: Dict[str, Any]


def create_sql_enhance_router(
    sql_validator=None,
    sql_fixer=None,
    few_shot_selector=None,
    intent_classifier=None,
    conversation_enhancer=None,
) -> APIRouter:
    """创建 SQL 增强路由"""
    
    router = APIRouter(prefix="/api/sql-enhance", tags=["sql-enhance"])
    
    @router.post("/validate", response_model=ValidateSQLResponse)
    async def validate_sql(request: ValidateSQLRequest) -> ValidateSQLResponse:
        """验证 SQL 语法和表/列名"""
        if not sql_validator:
            raise HTTPException(status_code=503, detail="SQL 校验器未初始化")
        
        result = sql_validator.validate(request.sql)
        
        return ValidateSQLResponse(
            is_valid=result.is_valid,
            error_type=result.error_type,
            error_message=result.error_message,
            suggestions=result.suggestions or [],
        )
    
    @router.post("/fix", response_model=FixSQLResponse)
    async def fix_sql(request: FixSQLRequest) -> FixSQLResponse:
        """尝试自动修复 SQL"""
        if not sql_fixer:
            raise HTTPException(status_code=503, detail="SQL 修复器未初始化")
        
        result = await sql_fixer.fix_sql(request.sql, request.error_message)
        
        return FixSQLResponse(
            success=result.success,
            original_sql=result.original_sql,
            fixed_sql=result.fixed_sql,
            fix_description=result.fix_description,
            attempts=result.attempts,
        )
    
    @router.post("/examples", response_model=GetExamplesResponse)
    async def get_examples(request: GetExamplesRequest) -> GetExamplesResponse:
        """获取相似的 Few-shot 示例"""
        if not few_shot_selector:
            raise HTTPException(status_code=503, detail="Few-shot 选择器未初始化")
        
        examples = await few_shot_selector.select_examples(
            request.question,
            min_similarity=0.2,
        )
        
        formatted = few_shot_selector.format_examples(examples)
        
        return GetExamplesResponse(
            examples=examples,
            formatted=formatted,
        )
    
    @router.post("/classify-intent", response_model=ClassifyIntentResponse)
    async def classify_intent(request: ClassifyIntentRequest) -> ClassifyIntentResponse:
        """分类用户意图"""
        if not intent_classifier:
            raise HTTPException(status_code=503, detail="意图分类器未初始化")
        
        intent, confidence = intent_classifier.classify(
            request.user_input,
            request.last_query,
            request.last_sql,
        )
        
        intent_labels = {
            "new_query": "新查询",
            "followup": "追问",
            "correction": "修正",
            "clarification": "澄清",
            "chitchat": "闲聊",
        }
        
        return ClassifyIntentResponse(
            intent=intent,
            intent_label=intent_labels.get(intent, "未知"),
            confidence=confidence,
        )
    
    @router.post("/rewrite-query", response_model=RewriteQueryResponse)
    async def rewrite_query(request: RewriteQueryRequest) -> RewriteQueryResponse:
        """改写用户查询"""
        if not conversation_enhancer:
            raise HTTPException(status_code=503, detail="对话增强器未初始化")
        
        result = await conversation_enhancer.rewrite_query(
            request.question,
            request.conversation_id,
            request.intent,
        )
        
        return RewriteQueryResponse(
            original=result.original,
            rewritten=result.rewritten,
            intent=result.intent,
            context_used=result.context_used,
            modifications=result.modifications,
        )
    
    @router.post("/modify-sql", response_model=ModifySQLResponse)
    async def modify_sql(request: ModifySQLRequest) -> ModifySQLResponse:
        """基于请求修改 SQL"""
        if not conversation_enhancer:
            raise HTTPException(status_code=503, detail="对话增强器未初始化")
        
        schema_context = ""
        if sql_validator:
            schema_context = sql_validator.get_schema_context()
        
        modified_sql = await conversation_enhancer.modify_sql(
            request.original_sql,
            request.modification_request,
            schema_context,
        )
        
        return ModifySQLResponse(
            success=modified_sql is not None,
            original_sql=request.original_sql,
            modified_sql=modified_sql,
        )
    
    @router.post("/update-context", response_model=UpdateContextResponse)
    async def update_context(request: UpdateContextRequest) -> UpdateContextResponse:
        """更新对话上下文"""
        if not conversation_enhancer:
            raise HTTPException(status_code=503, detail="对话增强器未初始化")
        
        context = conversation_enhancer.update_context(
            request.conversation_id,
            request.question,
            request.sql,
            request.result_data,
        )
        
        return UpdateContextResponse(
            success=True,
            context=context.to_dict(),
        )
    
    @router.get("/context/{conversation_id}")
    async def get_context(conversation_id: str) -> Dict[str, Any]:
        """获取对话上下文"""
        if not conversation_enhancer:
            raise HTTPException(status_code=503, detail="对话增强器未初始化")
        
        context = conversation_enhancer.get_context(conversation_id)
        
        if not context:
            return {"exists": False}
        
        return {"exists": True, "context": context.to_dict()}
    
    @router.delete("/context/{conversation_id}")
    async def clear_context(conversation_id: str) -> Dict[str, bool]:
        """清除对话上下文"""
        if not conversation_enhancer:
            raise HTTPException(status_code=503, detail="对话增强器未初始化")
        
        conversation_enhancer.clear_context(conversation_id)
        return {"success": True}
    
    @router.post("/refresh-schema")
    async def refresh_schema() -> Dict[str, bool]:
        """刷新 schema 缓存"""
        if sql_validator:
            sql_validator.refresh_schema()
        return {"success": True}
    
    return router

