"""
RAG 自动学习器：从高分反馈中生成 RAG 条目。

功能：
- 从高分案例中提取问答对
- 质量评估
- 去重检查
- 结构化存储到 RAG 知识库
"""

import logging
import re
from typing import Any, Dict, Optional

from app.services.rag_knowledge_base import RAGKnowledgeBase, RAGQAResult

logger = logging.getLogger(__name__)


class RAGLearner:
    """
    RAG 自动学习器：从高分反馈中生成 RAG 条目。
    """
    
    def __init__(
        self,
        rag_kb: RAGKnowledgeBase,
        *,
        min_score: float = 4.0,
        min_quality: float = 0.7,
    ):
        """
        初始化 RAG 学习器。
        
        Args:
            rag_kb: RAG 知识库实例
            min_score: 最小评分阈值
            min_quality: 最小质量评分阈值
        """
        self.rag_kb = rag_kb
        self.min_score = min_score
        self.min_quality = min_quality
    
    async def learn_from_feedback(
        self,
        conversation_id: str,
        question: str,
        sql: Optional[str],
        answer: str,
        score: Optional[float] = None,  # 综合评分（向后兼容）
        expert_rating: Optional[int] = None,  # 专家评分 (1-5)
        user_rating: Optional[int] = None,  # 用户评分 (1-5)
        llm_score: Optional[float] = None,  # LLM评估评分 (1-5)
        source: str = "feedback",
    ) -> Optional[str]:
        """
        从反馈中学习并生成 RAG 条目。
        
        Args:
            conversation_id: 会话 ID
            question: 用户问题
            sql: 生成的 SQL
            answer: AI 回答
            score: 综合评分（向后兼容，如果提供则优先使用）
            expert_rating: 专家评分 (1-5)，权重最高
            user_rating: 用户评分 (1-5)
            llm_score: LLM评估评分 (1-5)
            source: 来源（'feedback', 'expert', 'auto'）
            
        Returns:
            qa_id: 如果成功学习并存储，返回 qa_id，否则返回 None
        """
        # 计算综合评分（综合考虑专家评分、用户评分、LLM评分）
        final_score = self._calculate_composite_score(
            score=score,
            expert_rating=expert_rating,
            user_rating=user_rating,
            llm_score=llm_score,
        )
        
        if not sql or final_score < self.min_score:
            logger.debug(f"评分不足或缺少SQL，跳过学习: score={final_score:.2f}")
            return None
        
        # 1. 提取和清理 SQL
        cleaned_sql = self._extract_and_clean_sql(sql)
        if not cleaned_sql:
            logger.warning("无法提取有效的 SQL，跳过学习")
            return None
        
        # 2. 提取答案预览
        answer_preview = self._extract_answer_preview(answer)
        
        # 3. 质量评估
        quality_score = self._assess_quality(question, cleaned_sql, answer)
        if quality_score < self.min_quality:
            logger.debug(f"质量评分不足，跳过学习: quality={quality_score:.2f}")
            return None
        
        # 4. 去重检查
        duplicate = self.rag_kb.find_duplicate(question, cleaned_sql)
        if duplicate:
            logger.info(f"发现重复问答对，更新评分: {duplicate.qa_id[:8]}...")
            # 更新评分（取更高的评分）
            new_score = max(duplicate.score, final_score)
            self.rag_kb.update_score(duplicate.qa_id, new_score, quality_score)
            return duplicate.qa_id
        
        # 5. 提取标签和分类
        tags = self._extract_tags(question, cleaned_sql)
        category = self._categorize_question(question)
        
        # 6. 存储到 RAG 知识库
        try:
            qa_id = self.rag_kb.add_qa_pair(
                question=question,
                sql=cleaned_sql,
                answer_preview=answer_preview,
                score=final_score,
                quality_score=quality_score,
                source=source,
                conversation_id=conversation_id,
                tags=tags,
                category=category,
                metadata={
                    "original_sql": sql,
                    "original_answer": answer[:500],  # 只保存前500字符
                    "expert_rating": expert_rating,  # 保存专家评分
                    "user_rating": user_rating,  # 保存用户评分
                    "llm_score": llm_score,  # 保存LLM评分
                },
            )
            logger.info(f"✅ RAG 学习成功: {qa_id[:8]}... (score={final_score:.2f}, quality={quality_score:.2f}, expert={expert_rating}, user={user_rating}, llm={llm_score})")
            return qa_id
        except Exception as e:
            logger.error(f"存储 RAG 条目失败: {e}")
            return None
    
    def _extract_and_clean_sql(self, sql: str) -> Optional[str]:
        """提取和清理 SQL"""
        if not sql:
            return None
        
        # 移除代码块标记
        sql = re.sub(r'```sql\s*', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'```\s*', '', sql)
        
        # 提取 SELECT 语句
        sql_match = re.search(
            r'(SELECT\s+.+?(?:;|$))',
            sql,
            re.IGNORECASE | re.DOTALL
        )
        if sql_match:
            cleaned = sql_match.group(1).strip()
            # 移除末尾的分号
            cleaned = cleaned.rstrip(';').strip()
            return cleaned
        
        # 如果没有匹配到，尝试清理后直接使用
        cleaned = sql.strip()
        if cleaned.upper().startswith('SELECT'):
            return cleaned.rstrip(';').strip()
        
        return None
    
    def _extract_answer_preview(self, answer: str, max_length: int = 200) -> str:
        """提取答案预览"""
        if not answer:
            return ""
        
        # 移除 SQL 代码块
        preview = re.sub(r'```sql\s*.*?```', '', answer, flags=re.IGNORECASE | re.DOTALL)
        
        # 移除多余的空白
        preview = ' '.join(preview.split())
        
        # 截断到最大长度
        if len(preview) > max_length:
            preview = preview[:max_length] + "..."
        
        return preview
    
    def _assess_quality(
        self,
        question: str,
        sql: str,
        answer: str,
    ) -> float:
        """
        评估问答对的质量。
        
        评估维度：
        1. 问题清晰度（长度、完整性）
        2. SQL 有效性（是否包含 SELECT，是否有 WHERE 等）
        3. 答案相关性（是否回答了问题）
        
        Returns:
            质量评分 0.0 - 1.0
        """
        score = 0.0
        
        # 1. 问题清晰度 (0-0.3)
        question_score = 0.0
        if len(question.strip()) >= 5:
            question_score += 0.1
        if len(question.strip()) >= 10:
            question_score += 0.1
        if '?' in question or '？' in question or any(w in question for w in ['如何', '什么', '多少', '哪些']):
            question_score += 0.1
        score += min(question_score, 0.3)
        
        # 2. SQL 有效性 (0-0.4)
        sql_score = 0.0
        sql_upper = sql.upper()
        if sql_upper.strip().startswith('SELECT'):
            sql_score += 0.2
        if 'FROM' in sql_upper:
            sql_score += 0.1
        if 'WHERE' in sql_upper or 'GROUP BY' in sql_upper or 'ORDER BY' in sql_upper:
            sql_score += 0.1
        # SQL 长度合理性（不要太短，也不要太长）
        sql_len = len(sql)
        if 20 <= sql_len <= 500:
            sql_score += 0.1
        score += min(sql_score, 0.4)
        
        # 3. 答案相关性 (0-0.3)
        answer_score = 0.0
        if answer and len(answer.strip()) > 10:
            answer_score += 0.1
        # 检查答案是否包含数据（数字、表格等）
        if re.search(r'\d+', answer):
            answer_score += 0.1
        if '表' in answer or '结果' in answer or '数据' in answer:
            answer_score += 0.1
        score += min(answer_score, 0.3)
        
        return round(score, 2)
    
    def _calculate_composite_score(
        self,
        score: Optional[float] = None,
        expert_rating: Optional[int] = None,
        user_rating: Optional[int] = None,
        llm_score: Optional[float] = None,
    ) -> float:
        """
        计算综合评分，综合考虑专家评分、用户评分、LLM评分。
        
        评分权重：
        - 专家评分：权重 0.5（最高优先级）
        - LLM评分：权重 0.3
        - 用户评分：权重 0.2
        
        如果提供了score参数（向后兼容），则直接使用。
        
        Args:
            score: 综合评分（向后兼容）
            expert_rating: 专家评分 (1-5)
            user_rating: 用户评分 (1-5)
            llm_score: LLM评估评分 (1-5)
            
        Returns:
            综合评分 (1.0 - 5.0)
        """
        # 如果提供了score，直接使用（向后兼容）
        if score is not None:
            return float(score)
        
        # 收集所有可用的评分
        scores = []
        weights = []
        
        # 专家评分权重最高
        if expert_rating is not None:
            scores.append(float(expert_rating))
            weights.append(0.5)
        
        # LLM评分权重中等
        if llm_score is not None:
            scores.append(float(llm_score))
            weights.append(0.3)
        
        # 用户评分权重较低
        if user_rating is not None:
            scores.append(float(user_rating))
            weights.append(0.2)
        
        # 如果没有评分，返回0
        if not scores:
            return 0.0
        
        # 加权平均
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0
        
        composite = sum(s * w for s, w in zip(scores, weights)) / total_weight
        return round(composite, 2)
    
    def _extract_tags(self, question: str, sql: str) -> list[str]:
        """提取标签"""
        tags = []
        
        # 基于问题的关键词
        question_lower = question.lower()
        if any(kw in question_lower for kw in ['访问', '访问量', 'pv', 'uv']):
            tags.append('访问分析')
        if any(kw in question_lower for kw in ['销售', '订单', '收入']):
            tags.append('销售分析')
        if any(kw in question_lower for kw in ['趋势', '变化', '走势']):
            tags.append('趋势分析')
        if any(kw in question_lower for kw in ['分布', '占比', '比例']):
            tags.append('分布分析')
        if any(kw in question_lower for kw in ['排名', 'top', '最高', '最低']):
            tags.append('排名分析')
        
        # 基于 SQL 的关键词
        sql_upper = sql.upper()
        if 'COUNT' in sql_upper:
            tags.append('计数查询')
        if 'SUM' in sql_upper or 'AVG' in sql_upper:
            tags.append('聚合查询')
        if 'GROUP BY' in sql_upper:
            tags.append('分组查询')
        if 'JOIN' in sql_upper:
            tags.append('关联查询')
        
        return list(set(tags))  # 去重
    
    def _categorize_question(self, question: str) -> str:
        """分类问题"""
        question_lower = question.lower()
        
        if any(kw in question_lower for kw in ['访问', '访问量', 'pv', 'uv', 'dau', 'mau']):
            return '访问分析'
        elif any(kw in question_lower for kw in ['销售', '订单', '收入', '营收']):
            return '销售分析'
        elif any(kw in question_lower for kw in ['用户', '客户', '会员']):
            return '用户分析'
        elif any(kw in question_lower for kw in ['产品', '商品', '货品']):
            return '产品分析'
        elif any(kw in question_lower for kw in ['渠道', '来源', '来源']):
            return '渠道分析'
        elif any(kw in question_lower for kw in ['区域', '城市', '省份', '地区']):
            return '区域分析'
        else:
            return '通用查询'

