from pathlib import Path

from vanna import Agent, AgentConfig
from vanna.servers.fastapi import VannaFastAPIServer
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.integrations.openai import OpenAILlmService
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.integrations.sqlite import SqliteRunner
from vanna.integrations.local import LocalFileSystem
from vanna.integrations.local.agent_memory import DemoAgentMemory
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import (
    DATA_DB_PATH,
    VANNA_DATA_DIR,
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    DEEPSEEK_BASE_URL,
    PROJECT_ROOT,
)
from app.middleware.logging import register_logging_middleware
from app.routes.logs import create_logs_router
from app.routes.chat import create_chat_router
from app.routes.feedback import create_feedback_router
from app.routes.prompt import create_prompt_router
from app.routes.knowledge import create_knowledge_router
from app.routes.memory import create_memory_router
from app.routes.analysis import create_analysis_router
from app.services.prompt_config import PromptConfig
from app.services.prompt_manager import PromptManager
from app.services.business_knowledge import BusinessKnowledge
from app.services.query_analyzer import QueryAnalyzer

# 前端构建文件目录
FRONTEND_DIR = PROJECT_ROOT / "frontend" / "dist"


class SimpleUserResolver(UserResolver):
    """
    简单的用户解析器：
    - 从 cookie 里读 vanna_email
    - admin@example.com 认为是 admin，其余都是 user
    """

    async def resolve_user(self, request_context: RequestContext) -> User:
        email = request_context.get_cookie("vanna_email") or "guest@example.com"
        group = "admin" if email == "admin@example.com" else "user"
        return User(
            id=email,
            email=email,
            group_memberships=[group],
        )


file_system = LocalFileSystem(str(VANNA_DATA_DIR))

tools = ToolRegistry()
tools.register_local_tool(
    RunSqlTool(
        sql_runner=SqliteRunner(database_path=str(DATA_DB_PATH)),
        file_system=file_system,
    ),
    access_groups=["user", "admin"],
)
tools.register_local_tool(
    VisualizeDataTool(
        file_system=file_system,
    ),
    access_groups=["user", "admin"],
)

system_prompt = """
你是一个数据分析助手，擅长：
1. 把用户的自然语言问题转换为合适的 SQL；
2. 调用 RunSqlTool 执行查询；
3. 在拿到按维度聚合或按时间序列的数据后，调用 VisualizeDataTool 生成图表。

使用约定：
- 当用户在问“趋势 / 变化 / 走势 / 随时间变化”等问题时，优先生成折线图。
- 当用户在问“对比 / 排名 / TopN / 各地区 / 各渠道”等问题时，优先生成柱状图或条形图。
- 当用户在问“占比 / 构成 / 分布”时，可以生成饼图或堆叠柱状图。

回答要求：
- 用中文解释：总量、最高/最低、对比结论、是否有明显变化。
- 告诉用户已经生成了一张图表，可以在界面中进行交互查看（悬停查看数值、缩放等）。
"""

llm = OpenAILlmService(
    api_key=DEEPSEEK_API_KEY,
    model=DEEPSEEK_MODEL,
    base_url=DEEPSEEK_BASE_URL,
)

# 创建 agent memory 实例（用于 feedback 路由）
agent_memory = DemoAgentMemory(max_items=1000)

agent = Agent(
    llm_service=llm,
    tool_registry=tools,
    user_resolver=SimpleUserResolver(),
    agent_memory=agent_memory,
    config=AgentConfig(
        stream_responses=True,
        system_prompt=system_prompt,
    ),
)

server = VannaFastAPIServer(agent)
app = server.create_app()

register_logging_middleware(app)
app.include_router(create_logs_router(llm))
app.include_router(create_chat_router())

# 注册 feedback 路由（用于评分和评测）
feedback_router = create_feedback_router(
    agent_memory=agent_memory,
    llm_service=llm,
)
app.include_router(feedback_router)

# 注册 prompt 配置路由
SYSTEM_DB_PATH = PROJECT_ROOT / "data" / "system.db"
prompt_config = PromptConfig(str(SYSTEM_DB_PATH))
prompt_manager = PromptManager(prompt_config)
prompt_router = create_prompt_router(prompt_config, prompt_manager)
app.include_router(prompt_router)

# 注册业务知识库路由
knowledge = BusinessKnowledge(str(SYSTEM_DB_PATH))
knowledge_router = create_knowledge_router(knowledge)
app.include_router(knowledge_router)

# 注册学习记忆路由
memory_router = create_memory_router(agent_memory)
app.include_router(memory_router)

# 注册查询分析路由（用于意图分析、表选择、知识匹配）
query_analyzer = QueryAnalyzer(
    data_db_path=DATA_DB_PATH,
    knowledge_db_path=SYSTEM_DB_PATH,
    llm_service=llm,
    prompt_manager=prompt_manager,
)
analysis_router = create_analysis_router(query_analyzer)
app.include_router(analysis_router)

# 挂载前端静态文件 (如果存在构建目录)
if FRONTEND_DIR.exists():
    # 挂载静态资源 - 注意路径与 vite.config.ts 的 base 设置一致
    app.mount("/app/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="frontend_assets")
    
    # 新的前端入口点 - /app 路径
    @app.get("/app")
    @app.get("/app/")
    async def serve_frontend():
        """服务新的 React 前端"""
        return FileResponse(FRONTEND_DIR / "index.html")
    
    @app.get("/app/{path:path}")
    async def serve_frontend_path(path: str):
        """处理前端路由和静态文件"""
        # 如果请求的是静态文件（如 vite.svg），返回该文件
        file_path = FRONTEND_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # 否则返回 index.html（SPA 路由）
        return FileResponse(FRONTEND_DIR / "index.html")
    
    # /chat 路径也指向新版本前端（作为新版本的别名）
    @app.get("/chat")
    @app.get("/chat/")
    async def serve_chat_frontend():
        """新版本聊天界面（/chat 别名）"""
        return FileResponse(FRONTEND_DIR / "index.html")
    
    @app.get("/chat/{path:path}")
    async def serve_chat_frontend_path(path: str):
        """处理 /chat 路径下的前端路由和静态文件"""
        # 如果请求的是静态文件，返回该文件
        file_path = FRONTEND_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # 否则返回 index.html（SPA 路由）
        return FileResponse(FRONTEND_DIR / "index.html")

