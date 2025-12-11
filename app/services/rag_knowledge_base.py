"""
RAG 知识库服务。

提供：
- 高质量问答对的存储和管理
- 基于关键词的检索（阶段1）
- 向量化检索支持（阶段2）
- 自动学习高分案例
"""

import json
import sqlite3
import uuid
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import SYSTEM_DB_PATH

logger = logging.getLogger(__name__)


class RAGQAResult:
    """RAG 检索结果"""
    
    def __init__(
        self,
        qa_id: str,
        question: str,
        sql: str,
        answer_preview: str,
        similarity: float = 0.0,
        score: float = 0.0,
        quality_score: float = 0.0,
        source: str = "unknown",
    ):
        self.qa_id = qa_id
        self.question = question
        self.sql = sql
        self.answer_preview = answer_preview
        self.similarity = similarity
        self.score = score
        self.quality_score = quality_score
        self.source = source
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "qa_id": self.qa_id,
            "question": self.question,
            "sql": self.sql,
            "answer_preview": self.answer_preview,
            "similarity": self.similarity,
            "score": self.score,
            "quality_score": self.quality_score,
            "source": self.source,
        }


class RAGKnowledgeBase:
    """
    RAG 知识库：存储高质量的问答对，支持检索。
    
    阶段1：基于关键词的检索
    阶段2：向量化检索（支持）
    """
    
    def __init__(
        self,
        db_path: Optional[Path] = None,
        embedding_service=None,  # EmbeddingService 实例（可选）
    ):
        """
        初始化 RAG 知识库。
        
        Args:
            db_path: 数据库文件路径，默认使用 SYSTEM_DB_PATH
            embedding_service: 向量嵌入服务（可选）
        """
        self.db_path = Path(db_path) if db_path else SYSTEM_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedding_service = embedding_service
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self) -> None:
        """初始化数据库表结构"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # RAG 问答对表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rag_qa_pairs (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                sql TEXT NOT NULL,
                answer_preview TEXT,
                
                -- 向量嵌入（阶段2）
                embedding BLOB,
                
                -- 质量评分
                score REAL DEFAULT 0.0,
                quality_score REAL DEFAULT 0.0,
                
                -- 来源信息
                source TEXT,
                conversation_id TEXT,
                
                -- 标签和分类
                tags TEXT,
                category TEXT,
                
                -- 元数据
                metadata TEXT,
                usage_count INTEGER DEFAULT 0,
                last_used_at DATETIME,
                
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rag_score ON rag_qa_pairs(score DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rag_quality ON rag_qa_pairs(quality_score DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rag_source ON rag_qa_pairs(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rag_category ON rag_qa_pairs(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rag_created ON rag_qa_pairs(created_at DESC)")
        
        conn.commit()
        conn.close()
        logger.info("RAG 知识库表结构已初始化")
    
    @staticmethod
    def _serialize_embedding(embedding: List[float]) -> bytes:
        """序列化向量嵌入为 bytes"""
        try:
            return pickle.dumps(embedding)
        except Exception as e:
            logger.error(f"序列化向量嵌入失败: {e}")
            return b""
    
    @staticmethod
    def _deserialize_embedding(embedding_bytes: bytes) -> Optional[List[float]]:
        """反序列化向量嵌入"""
        if not embedding_bytes:
            return None
        try:
            return pickle.loads(embedding_bytes)
        except Exception as e:
            logger.error(f"反序列化向量嵌入失败: {e}")
            return None
    
    def add_qa_pair(
        self,
        question: str,
        sql: str,
        answer_preview: str = "",
        score: float = 0.0,
        quality_score: float = 0.0,
        source: str = "unknown",
        conversation_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[bytes] = None,
        embedding_list: Optional[List[float]] = None,  # 支持直接传入向量列表
    ) -> str:
        """
        添加问答对到 RAG 知识库。
        
        Args:
            question: 用户问题
            sql: 对应的 SQL 查询
            answer_preview: 答案预览
            score: 原始评分
            quality_score: 质量评分
            source: 来源（'feedback', 'expert', 'auto'）
            conversation_id: 会话 ID
            tags: 标签列表
            category: 分类
            metadata: 元数据
            embedding: 向量嵌入（bytes格式）
            embedding_list: 向量嵌入（List[float]格式，会自动序列化）
            
        Returns:
            qa_id: 问答对 ID
        """
        # 如果提供了 embedding_list，自动序列化
        if embedding_list and not embedding:
            embedding = self._serialize_embedding(embedding_list)
        
        # 如果提供了 embedding_service 但没有向量，自动生成
        if self.embedding_service and not embedding:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果在运行中的事件循环，创建任务
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            lambda: asyncio.run(self.embedding_service.embed(question))
                        )
                        embedding_list = future.result()
                else:
                    embedding_list = loop.run_until_complete(self.embedding_service.embed(question))
                
                if embedding_list:
                    embedding = self._serialize_embedding(embedding_list)
            except Exception as e:
                logger.warning(f"自动生成向量嵌入失败: {e}，将不存储向量")
        
        qa_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO rag_qa_pairs (
                    id, question, sql, answer_preview,
                    score, quality_score, source, conversation_id,
                    tags, category, metadata, embedding,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                qa_id,
                question,
                sql,
                answer_preview,
                score,
                quality_score,
                source,
                conversation_id,
                json.dumps(tags) if tags else None,
                category,
                json.dumps(metadata) if metadata else None,
                embedding,
                now,
                now,
            ))
            
            conn.commit()
            logger.info(f"已添加 RAG 问答对: {qa_id[:8]}... ({source}, score={score:.1f})")
            return qa_id
        except Exception as e:
            conn.rollback()
            logger.error(f"添加 RAG 问答对失败: {e}")
            raise
        finally:
            conn.close()
    
    def update_usage(self, qa_id: str) -> None:
        """更新使用计数和最后使用时间"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE rag_qa_pairs
                SET usage_count = usage_count + 1,
                    last_used_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), qa_id))
            conn.commit()
        except Exception as e:
            logger.error(f"更新使用计数失败: {e}")
        finally:
            conn.close()
    
    def update_score(self, qa_id: str, score: float, quality_score: Optional[float] = None) -> bool:
        """
        更新问答对的评分。
        
        Args:
            qa_id: 问答对 ID
            score: 新的评分
            quality_score: 新的质量评分（可选）
            
        Returns:
            是否更新成功
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            if quality_score is not None:
                cursor.execute("""
                    UPDATE rag_qa_pairs
                    SET score = ?,
                        quality_score = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (score, quality_score, datetime.now().isoformat(), qa_id))
            else:
                cursor.execute("""
                    UPDATE rag_qa_pairs
                    SET score = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (score, datetime.now().isoformat(), qa_id))
            
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"已更新 RAG 问答对评分: {qa_id[:8]}... (score={score:.1f})")
            return updated
        except Exception as e:
            logger.error(f"更新评分失败: {e}")
            return False
        finally:
            conn.close()
    
    def find_duplicate(
        self,
        question: str,
        sql: str,
        similarity_threshold: float = 0.9,
    ) -> Optional[RAGQAResult]:
        """
        查找重复的问答对（基于问题相似度和 SQL 匹配）。
        
        Args:
            question: 问题
            sql: SQL 查询
            similarity_threshold: 相似度阈值
            
        Returns:
            如果找到重复，返回 RAGQAResult，否则返回 None
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM rag_qa_pairs")
            rows = cursor.fetchall()
            
            # 简单的文本相似度匹配
            question_lower = question.lower()
            sql_normalized = sql.strip().upper()
            
            for row in rows:
                existing_question = row["question"].lower()
                existing_sql = row["sql"].strip().upper()
                
                # 计算问题相似度（简单的 Jaccard）
                q1_words = set(question_lower.split())
                q2_words = set(existing_question.split())
                if q1_words and q2_words:
                    jaccard = len(q1_words & q2_words) / len(q1_words | q2_words)
                else:
                    jaccard = 0.0
                
                # SQL 完全匹配或高度相似
                sql_match = existing_sql == sql_normalized or sql_normalized in existing_sql or existing_sql in sql_normalized
                
                if jaccard >= similarity_threshold and sql_match:
                    return self._row_to_result(row)
            
            return None
        except Exception as e:
            logger.error(f"查找重复问答对失败: {e}")
            return None
        finally:
            conn.close()
    
    def retrieve_similar(
        self,
        query: str,
        top_k: int = 3,
        min_score: float = 3.5,
        min_quality: float = 0.6,
        source_filter: Optional[str] = None,
        use_vector: bool = False,  # 是否使用向量检索（阶段2）
    ) -> List[RAGQAResult]:
        """
        检索相似的问答对。
        
        阶段1：基于关键词匹配
        阶段2：支持向量相似度搜索
        
        Args:
            query: 查询问题
            top_k: 返回数量
            min_score: 最小评分
            min_quality: 最小质量评分
            source_filter: 来源过滤（'feedback', 'expert', 'auto'）
            use_vector: 是否使用向量检索（如果可用）
            
        Returns:
            相似的问答对列表，按相似度+质量分排序
        """
        # 如果启用向量检索且有 embedding_service
        if use_vector and self.embedding_service:
            return self._retrieve_with_vector(query, top_k, min_score, min_quality, source_filter)
        
        # 否则使用关键词检索
        return self._retrieve_with_keywords(query, top_k, min_score, min_quality, source_filter)
    
    def _retrieve_with_keywords(
        self,
        query: str,
        top_k: int,
        min_score: float,
        min_quality: float,
        source_filter: Optional[str],
    ) -> List[RAGQAResult]:
        """基于关键词的检索（阶段1）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # 构建查询
            sql_query = """
                SELECT * FROM rag_qa_pairs
                WHERE score >= ? AND quality_score >= ?
            """
            params = [min_score, min_quality]
            
            if source_filter:
                sql_query += " AND source = ?"
                params.append(source_filter)
            
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()
            
            # 计算相似度并排序
            results = []
            query_words = set(query.lower().split())
            
            for row in rows:
                question_words = set(row["question"].lower().split())
                
                # 计算 Jaccard 相似度
                if query_words and question_words:
                    jaccard = len(query_words & question_words) / len(query_words | question_words)
                else:
                    jaccard = 0.0
                
                # 综合评分：相似度 * 0.6 + 质量分 * 0.4
                composite_score = jaccard * 0.6 + row["quality_score"] * 0.4
                
                if jaccard > 0.3:  # 最小相似度阈值
                    result = self._row_to_result(row)
                    result.similarity = jaccard
                    results.append((result, composite_score))
            
            # 按综合评分排序
            results.sort(key=lambda x: x[1], reverse=True)
            
            return [r[0] for r in results[:top_k]]
        except Exception as e:
            logger.error(f"检索相似问答对失败: {e}")
            return []
        finally:
            conn.close()
    
    def _retrieve_with_vector(
        self,
        query: str,
        top_k: int,
        min_score: float,
        min_quality: float,
        source_filter: Optional[str],
    ) -> List[RAGQAResult]:
        """基于向量的检索（阶段2）"""
        if not self.embedding_service:
            return self._retrieve_with_keywords(query, top_k, min_score, min_quality, source_filter)
        
        import asyncio
        
        try:
            # 生成查询向量
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(self.embedding_service.embed(query))
                    )
                    query_embedding = future.result()
            else:
                query_embedding = loop.run_until_complete(self.embedding_service.embed(query))
            
            if not query_embedding:
                return self._retrieve_with_keywords(query, top_k, min_score, min_quality, source_filter)
            
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # 构建查询
            sql_query = """
                SELECT * FROM rag_qa_pairs
                WHERE score >= ? AND quality_score >= ? AND embedding IS NOT NULL
            """
            params = [min_score, min_quality]
            
            if source_filter:
                sql_query += " AND source = ?"
                params.append(source_filter)
            
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()
            
            # 计算向量相似度
            results = []
            for row in rows:
                embedding_bytes = row["embedding"]
                if not embedding_bytes:
                    continue
                
                stored_embedding = self._deserialize_embedding(embedding_bytes)
                if not stored_embedding:
                    continue
                
                # 计算余弦相似度
                similarity = self.embedding_service.cosine_similarity(query_embedding, stored_embedding)
                
                # 综合评分：向量相似度 * 0.6 + 质量分 * 0.4
                composite_score = similarity * 0.6 + row["quality_score"] * 0.4
                
                if similarity > 0.3:  # 最小相似度阈值
                    result = self._row_to_result(row)
                    result.similarity = similarity
                    results.append((result, composite_score))
            
            # 按综合评分排序
            results.sort(key=lambda x: x[1], reverse=True)
            
            conn.close()
            return [r[0] for r in results[:top_k]]
        except Exception as e:
            logger.error(f"向量检索失败: {e}，降级到关键词检索")
            return self._retrieve_with_keywords(query, top_k, min_score, min_quality, source_filter)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) as total FROM rag_qa_pairs")
            total = cursor.fetchone()["total"]
            
            cursor.execute("SELECT AVG(score) as avg_score FROM rag_qa_pairs")
            avg_score = cursor.fetchone()["avg_score"] or 0.0
            
            cursor.execute("SELECT AVG(quality_score) as avg_quality FROM rag_qa_pairs")
            avg_quality = cursor.fetchone()["avg_quality"] or 0.0
            
            cursor.execute("SELECT source, COUNT(*) as count FROM rag_qa_pairs GROUP BY source")
            by_source = {row["source"]: row["count"] for row in cursor.fetchall()}
            
            cursor.execute("SELECT COUNT(*) as count FROM rag_qa_pairs WHERE embedding IS NOT NULL")
            with_embedding = cursor.fetchone()["count"]
            
            return {
                "total": total,
                "avg_score": round(avg_score, 2),
                "avg_quality": round(avg_quality, 2),
                "by_source": by_source,
                "with_embedding": with_embedding,
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {
                "total": 0,
                "avg_score": 0.0,
                "avg_quality": 0.0,
                "by_source": {},
                "with_embedding": 0,
            }
        finally:
            conn.close()
    
    def _row_to_result(self, row: sqlite3.Row) -> RAGQAResult:
        """将数据库行转换为 RAGQAResult"""
        tags = json.loads(row["tags"]) if row["tags"] else []
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        
        return RAGQAResult(
            qa_id=row["id"],
            question=row["question"],
            sql=row["sql"],
            answer_preview=row["answer_preview"] or "",
            score=row["score"] or 0.0,
            quality_score=row["quality_score"] or 0.0,
            source=row["source"] or "unknown",
        )
    
    def delete_qa_pair(self, qa_id: str) -> bool:
        """删除问答对"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM rag_qa_pairs WHERE id = ?", (qa_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"已删除 RAG 问答对: {qa_id[:8]}...")
            return deleted
        except Exception as e:
            logger.error(f"删除 RAG 问答对失败: {e}")
            return False
        finally:
            conn.close()
