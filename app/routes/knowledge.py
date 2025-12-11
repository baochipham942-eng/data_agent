"""
业务知识库 API 路由。

提供：
- 业务术语管理
- 字段映射管理
- 时间规则管理
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.business_knowledge import BusinessKnowledge


# ============ 请求模型 ============

class TermRequest(BaseModel):
    """业务术语请求"""
    keyword: str
    term_type: str
    description: str
    example: Optional[str] = None
    priority: Optional[int] = 1


class MappingRequest(BaseModel):
    """字段映射请求"""
    alias: str
    standard_name: str
    table_name: Optional[str] = None
    description: Optional[str] = None


class TimeRuleRequest(BaseModel):
    """时间规则请求"""
    keyword: str
    rule_type: str
    value: str
    description: Optional[str] = None


# ============ 路由创建 ============

def create_knowledge_router(knowledge: BusinessKnowledge) -> APIRouter:
    """创建业务知识库路由"""
    router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
    
    # ========== 统计 ==========
    
    @router.get("/stats")
    async def get_stats():
        """获取知识库统计"""
        terms = knowledge.get_all_terms()
        mappings = knowledge.get_all_mappings()
        rules = knowledge.get_all_time_rules()
        return {
            "terms": len(terms),
            "mappings": len(mappings),
            "rules": len(rules),
        }
    
    # ========== 业务术语 ==========
    
    @router.get("/terms")
    async def list_terms():
        """列出所有业务术语"""
        terms = knowledge.get_all_terms()
        return {"terms": terms}
    
    @router.post("/terms")
    async def add_term(request: TermRequest):
        """添加业务术语"""
        try:
            term_id = knowledge.add_term(
                keyword=request.keyword,
                term_type=request.term_type,
                description=request.description,
                example=request.example,
                priority=request.priority,
            )
            return {"success": True, "id": term_id}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    @router.delete("/terms/{keyword}")
    async def delete_term(keyword: str):
        """删除业务术语"""
        deleted = knowledge.delete_term(keyword)
        if not deleted:
            raise HTTPException(status_code=404, detail="术语不存在")
        return {"success": True}
    
    # ========== 字段映射 ==========
    
    @router.get("/mappings")
    async def list_mappings():
        """列出所有字段映射"""
        mappings = knowledge.get_all_mappings()
        return {"mappings": mappings}
    
    @router.post("/mappings")
    async def add_mapping(request: MappingRequest):
        """添加字段映射"""
        try:
            mapping_id = knowledge.add_mapping(
                alias=request.alias,
                standard_name=request.standard_name,
                table_name=request.table_name,
                description=request.description,
            )
            return {"success": True, "id": mapping_id}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # ========== 时间规则 ==========
    
    @router.get("/time-rules")
    async def list_time_rules():
        """列出所有时间规则"""
        rules = knowledge.get_all_time_rules()
        return {"rules": rules}
    
    @router.delete("/time-rules/{keyword}")
    async def delete_time_rule(keyword: str):
        """删除时间规则"""
        deleted = knowledge.delete_time_rule(keyword)
        if not deleted:
            raise HTTPException(status_code=404, detail="时间规则不存在")
        return {"success": True}
    
    return router
