"""
动态 Agent 配置中间件 - 支持根据用户动态调整 Agent 配置
"""
import logging
from typing import Optional
from fastapi import Request
from vanna.core.user import User, RequestContext

from app.services.dynamic_prompt_builder import DynamicPromptBuilder
from app.services.agent_memory import UserProfileService

logger = logging.getLogger(__name__)


def register_dynamic_agent_middleware(
    app,
    dynamic_prompt_builder: DynamicPromptBuilder,
    user_profile_service: Optional[UserProfileService] = None,
):
    """
    注册动态 Agent 配置中间件。
    
    这个中间件会在请求处理前，根据用户信息动态调整 Agent 配置。
    注意：由于 Vanna Agent 的配置是静态的，我们需要通过其他方式实现个性化。
    例如：在 System Prompt 中添加用户特定的上下文。
    """
    
    @app.middleware("http")
    async def dynamic_agent_middleware(request: Request, call_next):
        path = request.url.path
        
        # 只处理聊天接口
        if path != "/api/vanna/v2/chat_sse":
            return await call_next(request)
        
        # 注意：由于 Agent 配置在初始化时就固定了，
        # 我们无法在运行时修改 System Prompt。
        # 但我们可以通过以下方式实现个性化：
        # 1. 在 UserResolver 中设置用户元数据
        # 2. 在 System Prompt 中使用变量，然后在运行时替换
        # 3. 在用户消息前添加个性化上下文
        
        # 这里我们主要是记录用户信息，实际的个性化在 UserResolver 中实现
        try:
            # 获取用户ID
            user_id = request.headers.get("X-User-ID") or request.cookies.get("vanna_email")
            
            if user_id and user_profile_service:
                # 可以在这里做一些用户级别的预处理
                # 例如：记录用户访问、更新最后活跃时间等
                pass
        except Exception as e:
            logger.warning(f"动态 Agent 中间件处理失败: {e}")
        
        return await call_next(request)









