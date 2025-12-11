"""
Agent Memory 管理 API 路由。

提供查看和管理 Agent Memory 的接口。
"""

import json
import logging
from typing import Any
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def create_memory_router(
    agent_memory: Any,  # 支持任何类型的 agent_memory
    rag_knowledge_base=None,  # RAG 知识库实例（可选）
) -> APIRouter:
    """创建 Memory 管理路由。"""
    router = APIRouter(prefix="/api/memory", tags=["memory"])

    @router.get("/stats")
    async def get_memory_stats():
        """获取 Memory 统计信息。"""
        try:
            # 尝试调用 get_stats，如果不存在则返回默认值
            if hasattr(agent_memory, 'get_stats'):
                stats = await agent_memory.get_stats()
            else:
                # DemoAgentMemory 可能没有 get_stats 方法
                stats = {
                    "total_tool_memories": 0,
                    "successful_tool_memories": 0,
                    "total_text_memories": 0,
                }
            return JSONResponse(content=stats)
        except Exception as e:
            logger.error(f"获取 Memory 统计失败: {e}")
            return JSONResponse(content={
                "total_tool_memories": 0,
                "successful_tool_memories": 0,
                "total_text_memories": 0,
            })

    @router.get("/tools")
    async def get_recent_tool_memories(limit: int = 20):
        """获取最近的工具使用记录。"""
        try:
            if hasattr(agent_memory, 'get_recent_memories'):
                from vanna.core.tool import ToolContext
                from vanna.core.user import User
                
                context = ToolContext(
                    user=User(id="api", email="api@internal"),
                    conversation_id="api",
                    request_id="api",
                    agent_memory=agent_memory,
                )
                
                memories = await agent_memory.get_recent_memories(context, limit=limit)
                return JSONResponse(content={
                    "memories": [
                        {
                            "id": m.memory_id,
                            "question": m.question,
                            "tool_name": m.tool_name,
                            "args": m.args,
                            "timestamp": m.timestamp,
                            "success": m.success,
                            "metadata": m.metadata or {},
                        }
                        for m in memories
                    ],
                })
            else:
                return JSONResponse(content={"memories": []})
        except Exception as e:
            logger.error(f"获取工具记忆失败: {e}")
            return JSONResponse(content={"memories": []})

    @router.get("/texts")
    async def get_recent_text_memories(limit: int = 20):
        """获取最近的文本记忆。"""
        try:
            if hasattr(agent_memory, 'get_recent_text_memories'):
                from vanna.core.tool import ToolContext
                from vanna.core.user import User
                
                context = ToolContext(
                    user=User(id="api", email="api@internal"),
                    conversation_id="api",
                    request_id="api",
                    agent_memory=agent_memory,
                )
                
                memories = await agent_memory.get_recent_text_memories(context, limit=limit)
                return JSONResponse(content={
                    "memories": [
                        {
                            "id": m.memory_id,
                            "content": m.content[:500] + "..." if len(m.content) > 500 else m.content,
                            "timestamp": m.timestamp,
                        }
                        for m in memories
                    ],
                })
            else:
                return JSONResponse(content={"memories": []})
        except Exception as e:
            logger.error(f"获取文本记忆失败: {e}")
            return JSONResponse(content={"memories": []})

    @router.post("/clear")
    async def clear_memories(tool_name: str = None):
        """清除 Memory（谨慎使用）。"""
        try:
            if hasattr(agent_memory, 'clear_memories'):
                from vanna.core.tool import ToolContext
                from vanna.core.user import User
                
                context = ToolContext(
                    user=User(id="api", email="api@internal"),
                    conversation_id="api",
                    request_id="api",
                    agent_memory=agent_memory,
                )
                
                deleted_count = await agent_memory.clear_memories(
                    context,
                    tool_name=tool_name,
                )
                return JSONResponse(content={
                    "success": True,
                    "deleted_count": deleted_count,
                })
            else:
                return JSONResponse(content={
                    "success": True,
                    "deleted_count": 0,
                })
        except Exception as e:
            logger.error(f"清除记忆失败: {e}")
            return JSONResponse(
                content={"success": False, "error": str(e)},
                status_code=500,
            )
    
    @router.get("/rag-high-score")
    async def get_rag_high_score_cases(limit: int = 100, min_score: float = 4.0):
        """获取 RAG 知识库的高分案例。"""
        if not rag_knowledge_base:
            return JSONResponse(
                content={"success": False, "error": "RAG 知识库未初始化"},
                status_code=503,
            )
        
        try:
            # 直接从数据库查询高分案例（不使用检索方法，因为检索需要查询字符串）
            conn = rag_knowledge_base._get_conn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM rag_qa_pairs
                WHERE score >= ? AND quality_score >= 0.7
                ORDER BY score DESC, quality_score DESC
                LIMIT ?
            """, (min_score, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            # 转换为前端需要的格式
            data = []
            for row in rows:
                metadata = {}
                if row["metadata"]:
                    try:
                        metadata = json.loads(row["metadata"])
                    except Exception as e:
                        logger.warning(f"解析metadata失败: {e}")
                
                tags = []
                if row["tags"]:
                    try:
                        tags = json.loads(row["tags"])
                    except Exception as e:
                        logger.warning(f"解析tags失败: {e}")
                
                data.append({
                    "id": row["id"],
                    "question": row["question"],
                    "sql": row["sql"],
                    "answer_preview": row["answer_preview"] or "",
                    "score": row["score"] or 0.0,
                    "quality_score": row["quality_score"] or 0.0,
                    "source": row["source"] or "unknown",
                    "expert_rating": metadata.get("expert_rating"),
                    "user_rating": metadata.get("user_rating"),
                    "llm_score": metadata.get("llm_score"),
                    "category": row["category"],
                    "tags": tags,
                    "usage_count": row["usage_count"] or 0,
                    "created_at": row["created_at"],
                })
            
            return JSONResponse(content={
                "cases": data,
            })
        except Exception as e:
            logger.error(f"获取 RAG 高分案例失败: {e}")
            return JSONResponse(
                content={"success": False, "error": str(e)},
                status_code=500,
            )
    
    @router.get("/rag-stats")
    async def get_rag_stats():
        """获取 RAG 知识库统计信息。"""
        if not rag_knowledge_base:
            return JSONResponse(content={"total": 0})
        
        try:
            stats = rag_knowledge_base.get_stats()
            return JSONResponse(content=stats)
        except Exception as e:
            logger.error(f"获取 RAG 统计信息失败: {e}")
            return JSONResponse(content={"total": 0})

    return router

