"""
动态 Prompt 构建器 - 根据用户画像和上下文动态生成 System Prompt
"""
import logging
from typing import Optional, Dict, Any
from vanna.core.user import User

from app.services.prompt_manager import PromptManager
from app.services.agent_memory import UserProfileService

logger = logging.getLogger(__name__)


class DynamicPromptBuilder:
    """动态 Prompt 构建器"""
    
    def __init__(
        self,
        prompt_manager: PromptManager,
        user_profile_service: Optional[UserProfileService] = None,
    ):
        """
        初始化动态 Prompt 构建器。
        
        Args:
            prompt_manager: Prompt 管理器
            user_profile_service: 用户画像服务
        """
        self.prompt_manager = prompt_manager
        self.user_profile_service = user_profile_service
    
    async def build_system_prompt(self, user: User) -> str:
        """
        根据用户信息构建动态 System Prompt。
        
        Args:
            user: 用户对象
        
        Returns:
            动态生成的 System Prompt
        """
        # 获取基础 System Prompt
        base_prompt = self.prompt_manager.get_active_prompt_content("system_prompt")
        if not base_prompt:
            # 如果没有配置的 prompt，使用默认值
            base_prompt = """你是一个数据分析助手，擅长：
1. 把用户的自然语言问题转换为合适的 SQL；
2. 调用 RunSqlTool 执行查询；
3. 在拿到按维度聚合或按时间序列的数据后，调用 VisualizeDataTool 生成图表。

使用约定：
- 当用户在问"趋势 / 变化 / 走势 / 随时间变化"等问题时，优先生成折线图。
- 当用户在问"对比 / 排名 / TopN / 各地区 / 各渠道"等问题时，优先生成柱状图或条形图。
- 当用户在问"占比 / 构成 / 分布"时，可以生成饼图或堆叠柱状图。

回答要求：
- 用中文解释：总量、最高/最低、对比结论、是否有明显变化。
- 告诉用户已经生成了一张图表，可以在界面中进行交互查看（悬停查看数值、缩放等）。
"""
        
        # 获取用户画像信息
        user_metadata = user.metadata or {}
        preferences = user_metadata.get("preferences", {})
        expertise_level = user_metadata.get("expertise_level", "intermediate")
        focus_dimensions = user_metadata.get("focus_dimensions", [])
        
        # 构建个性化增强部分
        enhancements = []
        
        # 根据专业水平调整 Prompt
        if expertise_level == "beginner":
            enhancements.append("""
【用户级别】：初级用户
- 回答要更加详细和通俗易懂
- 适当解释 SQL 的作用
- 提供更多上下文说明
""")
        elif expertise_level == "expert":
            enhancements.append("""
【用户级别】：专家用户
- 可以使用更专业的术语
- 可以提供更深入的分析建议
- SQL 可以更复杂和优化
""")
        
        # 根据用户偏好调整
        preferred_chart = preferences.get("preferred_chart_type")
        if preferred_chart:
            enhancements.append(f"""
【用户偏好】：优先使用 {preferred_chart} 图表类型
- 在合适的情况下，优先考虑使用 {preferred_chart} 图表
- 如果数据不适合 {preferred_chart}，再考虑其他类型
""")
        
        # 根据关注的维度调整
        if focus_dimensions:
            dims_str = "、".join(focus_dimensions[:3])  # 最多显示3个
            enhancements.append(f"""
【用户关注维度】：{dims_str}
- 用户经常关注这些维度，在分析时可以考虑优先展示
- 如果用户问题涉及这些维度，可以给出更详细的分析
""")
        
        # 组合 Prompt
        if enhancements:
            enhanced_prompt = base_prompt + "\n\n---\n【个性化配置】" + "\n".join(enhancements)
            logger.debug(f"为用户 {user.id} 构建个性化 Prompt（专业级别: {expertise_level}）")
            return enhanced_prompt
        
        return base_prompt
    
    def build_contextual_prompt(
        self,
        base_prompt: str,
        user: User,
        conversation_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        根据对话上下文构建 Prompt（可用于多轮对话）。
        
        Args:
            base_prompt: 基础 Prompt
            user: 用户对象
            conversation_context: 对话上下文
        
        Returns:
            增强后的 Prompt
        """
        # 目前返回基础 Prompt，可以根据需要扩展
        return base_prompt









