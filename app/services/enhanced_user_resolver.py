"""
增强的用户解析器 - 支持多种方式识别用户并获取用户画像
"""
import logging
from typing import Optional
from vanna.core.user import UserResolver, User, RequestContext

from app.services.agent_memory import UserProfileService

logger = logging.getLogger(__name__)


class EnhancedUserResolver(UserResolver):
    """
    增强的用户解析器：
    - 支持从请求头 (X-User-ID) 识别用户
    - 支持从 Cookie (vanna_email) 识别用户
    - 支持从请求参数识别用户
    - 自动获取用户画像信息
    - 根据用户画像确定用户组和权限
    """
    
    def __init__(self, user_profile_service: Optional[UserProfileService] = None):
        """
        初始化增强的用户解析器。
        
        Args:
            user_profile_service: 用户画像服务，用于获取用户信息
        """
        self.user_profile_service = user_profile_service
    
    async def resolve_user(self, request_context: RequestContext) -> User:
        """
        解析用户信息。
        
        优先级：
        1. X-User-ID 请求头
        2. X-Email 请求头
        3. Cookie: vanna_email
        4. Cookie: user_id
        5. 查询参数: user_id
        6. 默认: guest@example.com
        """
        user_id = None
        email = None
        
        # 1. 从请求头获取
        user_id = request_context.get_header("X-User-ID") or request_context.get_header("x-user-id")
        email = request_context.get_header("X-Email") or request_context.get_header("x-email")
        
        # 2. 从 Cookie 获取
        if not user_id:
            user_id = request_context.get_cookie("user_id")
        if not email:
            email = request_context.get_cookie("vanna_email")
        
        # 3. 从查询参数获取
        if not user_id and hasattr(request_context, "query_params"):
            query_params = request_context.query_params or {}
            user_id = query_params.get("user_id")
        
        # 4. 使用 email 作为 user_id（如果还没有）
        if email and not user_id:
            user_id = email
        
        # 5. 默认用户
        if not user_id:
            user_id = "guest@example.com"
            email = "guest@example.com"
        
        # 如果没有 email，使用 user_id
        if not email:
            email = user_id if "@" in user_id else f"{user_id}@example.com"
        
        # 确定用户组（从用户画像或默认规则）
        group = await self._determine_user_group(user_id)
        
        # 获取用户元数据（从用户画像）
        metadata = await self._get_user_metadata(user_id)
        
        return User(
            id=user_id,
            email=email,
            group_memberships=[group],
            metadata=metadata,
        )
    
    async def _determine_user_group(self, user_id: str) -> str:
        """确定用户组"""
        # 管理员判断
        if user_id in ["admin@example.com", "admin"]:
            return "admin"
        
        # 从用户画像获取（如果有）
        if self.user_profile_service:
            try:
                profile = await self.user_profile_service.get_profile(user_id)
                if profile:
                    # 可以根据用户画像的某些字段确定组
                    # 例如：根据 expertise_level 或某个字段
                    expertise = profile.get("expertise_level", "")
                    if expertise == "expert":
                        return "expert"
                    elif expertise == "admin":
                        return "admin"
            except Exception as e:
                logger.warning(f"获取用户画像失败: {e}")
        
        # 默认用户组
        return "user"
    
    async def _get_user_metadata(self, user_id: str) -> dict:
        """获取用户元数据"""
        metadata = {}
        
        if self.user_profile_service:
            try:
                profile = await self.user_profile_service.get_profile(user_id)
                if profile:
                    metadata = {
                        "nickname": profile.get("nickname"),
                        "expertise_level": profile.get("expertise_level", "intermediate"),
                        "preferences": profile.get("preferences", {}),
                        "focus_dimensions": profile.get("focus_dimensions", []),
                    }
            except Exception as e:
                logger.warning(f"获取用户元数据失败: {e}")
        
        return metadata

