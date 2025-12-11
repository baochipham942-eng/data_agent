"""
Prompt 配置 API 路由。

提供：
- Prompt 版本管理
- 激活/切换 Prompt
- 使用统计
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.prompt_config import PromptConfig
from app.services.prompt_manager import PromptManager


# ============ 请求/响应模型 ============

class CreatePromptRequest(BaseModel):
    """创建 Prompt 请求"""
    name: str
    version: str
    content: str
    description: Optional[str] = None
    category: str = "system"


class UpdatePromptRequest(BaseModel):
    """更新 Prompt 请求"""
    content: Optional[str] = None
    description: Optional[str] = None


class SetActiveRequest(BaseModel):
    """设置激活版本请求"""
    name: str
    version: str


# ============ 路由创建 ============

def create_prompt_router(prompt_config: PromptConfig, prompt_manager: PromptManager = None) -> APIRouter:
    """创建 Prompt 配置路由"""
    router = APIRouter(prefix="/api/prompt", tags=["prompt"])
    
    @router.get("/list")
    async def list_prompts(name: Optional[str] = None, category: Optional[str] = None):
        """列出所有 Prompt 版本"""
        prompts = prompt_config.list_prompts(name, category)
        return {"success": True, "data": prompts}
    
    @router.post("/create")
    async def create_prompt(request: CreatePromptRequest):
        """创建新的 Prompt 版本"""
        try:
            prompt_id = prompt_config.create_prompt(
                name=request.name,
                version=request.version,
                content=request.content,
                description=request.description,
                category=request.category,
            )
            return {"success": True, "id": prompt_id}
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                raise HTTPException(status_code=400, detail="该版本已存在")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.put("/{name}/{version}")
    async def update_prompt(name: str, version: str, request: UpdatePromptRequest):
        """更新 Prompt"""
        updated = prompt_config.update_prompt(
            name=name,
            version=version,
            content=request.content,
            description=request.description,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Prompt 不存在")
        return {"success": True}
    
    @router.get("/{name}/{version}")
    async def get_prompt(name: str, version: str):
        """获取指定版本的 Prompt"""
        prompt = prompt_config.get_prompt(name, version)
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt 不存在")
        return {"success": True, "data": prompt}
    
    @router.get("/active/{name}")
    async def get_active_prompt(name: str):
        """获取激活的 Prompt"""
        prompt = prompt_config.get_active_prompt(name)
        if not prompt:
            raise HTTPException(status_code=404, detail="没有激活的 Prompt")
        return {"success": True, "data": prompt}
    
    @router.post("/activate")
    async def set_active_prompt(request: SetActiveRequest):
        """设置激活的 Prompt 版本"""
        success = prompt_config.set_active_prompt(request.name, request.version)
        if not success:
            raise HTTPException(status_code=404, detail="Prompt 不存在")
        
        # 刷新 PromptManager 缓存
        if prompt_manager:
            prompt_manager.refresh_cache(request.name)
        
        # 对于 system_prompt，需要重启服务才能生效
        message = f"已激活 {request.name} {request.version}"
        if request.name == "system_prompt":
            message += "（注意：system_prompt 需要重启服务才能生效）"
        
        return {"success": True, "message": message}
    
    @router.delete("/{name}/{version}")
    async def delete_prompt(name: str, version: str):
        """删除 Prompt（不能删除激活的版本）"""
        deleted = prompt_config.delete_prompt(name, version)
        if not deleted:
            raise HTTPException(
                status_code=400, 
                detail="删除失败：Prompt 不存在或是当前激活版本"
            )
        return {"success": True}
    
    @router.get("/stats")
    async def get_stats():
        """获取配置统计"""
        stats = prompt_config.get_stats()
        usage = prompt_config.get_usage_stats()
        return {"success": True, "data": {**stats, **usage}}
    
    @router.get("/usage/{conversation_id}")
    async def get_conversation_prompt(conversation_id: str):
        """获取会话使用的 Prompt"""
        usage = prompt_config.get_conversation_prompt(conversation_id)
        return {"success": True, "data": usage}
    
    return router

