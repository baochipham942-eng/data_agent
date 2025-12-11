"""
LLM as Judge 评估服务。

提供 AI 自动评估能力：
- 评估 SQL 语义正确性
- 评估回答完整性和准确性
- 生成改进建议
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from vanna.integrations.openai import OpenAILlmService

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """评估结果"""
    # 各维度评分 (1-5)
    sql_correctness: int  # SQL 正确性
    result_interpretation: int  # 结果解读准确性
    answer_completeness: int  # 回答完整性
    expression_clarity: int  # 表达清晰度
    
    # 总分
    overall_score: float
    
    # 详细反馈
    strengths: List[str]  # 优点
    weaknesses: List[str]  # 不足
    suggestions: List[str]  # 改进建议
    
    # 元信息
    confidence: float  # 置信度 0-1
    reasoning: str  # 评估推理过程


DEFAULT_JUDGE_SYSTEM_PROMPT = """你是一个专业的数据分析质量评估专家。你的任务是评估 AI 数据分析助手的回答质量。

请根据以下维度进行评分（1-5分）：

1. **SQL 正确性** (sql_correctness)
   - 1分: SQL 完全错误或无法执行
   - 2分: SQL 能执行但逻辑错误，无法回答用户问题
   - 3分: SQL 基本正确但有小问题（如字段名不准确、缺少条件等）
   - 4分: SQL 正确且高效
   - 5分: SQL 优秀，考虑了边界情况和性能

2. **结果解读** (result_interpretation)
   - 1分: 解读完全错误或与数据不符
   - 2分: 解读有重大错误
   - 3分: 解读基本正确但缺乏深度
   - 4分: 解读准确且有一定洞察
   - 5分: 解读精准、有深度洞察和业务价值

3. **回答完整性** (answer_completeness)
   - 1分: 完全没有回答用户问题
   - 2分: 只回答了部分问题
   - 3分: 回答了主要问题但缺少细节
   - 4分: 回答完整
   - 5分: 回答完整且主动提供相关补充信息

4. **表达清晰度** (expression_clarity)
   - 1分: 表达混乱难以理解
   - 2分: 表达有歧义
   - 3分: 表达基本清晰
   - 4分: 表达清晰易懂
   - 5分: 表达专业、结构化、易于理解

请以 JSON 格式输出评估结果：
```json
{
  "sql_correctness": 4,
  "result_interpretation": 4,
  "answer_completeness": 5,
  "expression_clarity": 4,
  "strengths": ["SQL 查询逻辑正确", "数据解读准确"],
  "weaknesses": ["缺少对异常值的说明"],
  "suggestions": ["可以补充数据趋势分析", "建议说明数据的置信度"],
  "confidence": 0.85,
  "reasoning": "该回答正确理解了用户查询各省份访问量的需求..."
}
```
"""

JUDGE_USER_TEMPLATE = """## 用户问题
{user_question}

## 数据库 Schema 上下文
{schema_context}

## AI 生成的 SQL
```sql
{generated_sql}
```

## SQL 执行结果
{sql_result}

## AI 的分析回答
{ai_response}

---

请评估这个回答的质量，输出 JSON 格式的评估结果。"""


class LLMJudge:
    """LLM 评估器"""
    
    def __init__(
        self,
        llm_service: OpenAILlmService,
        *,
        timeout: float = 30.0,
        prompt_manager=None,
    ):
        """
        初始化 LLM Judge。
        
        Args:
            llm_service: LLM 服务
            timeout: 请求超时时间
            prompt_manager: Prompt管理器（可选）
        """
        self.llm = llm_service
        self.timeout = timeout
        self.prompt_manager = prompt_manager
    
    def _get_judge_prompt(self) -> str:
        """获取 Judge Prompt"""
        if self.prompt_manager:
            return self.prompt_manager.get_active_prompt_content(
                "judge_prompt",
                fallback=DEFAULT_JUDGE_SYSTEM_PROMPT
            )
        return DEFAULT_JUDGE_SYSTEM_PROMPT
    
    async def evaluate(
        self,
        user_question: str,
        generated_sql: Optional[str],
        sql_result: Optional[str],
        ai_response: str,
        schema_context: str = "",
    ) -> EvaluationResult:
        """
        评估 AI 回答质量。
        
        Args:
            user_question: 用户原始问题
            generated_sql: AI 生成的 SQL
            sql_result: SQL 执行结果（JSON 或文本）
            ai_response: AI 的分析回答
            schema_context: 数据库 schema 上下文
            
        Returns:
            EvaluationResult: 评估结果
        """
        # 构造评估 prompt
        user_prompt = JUDGE_USER_TEMPLATE.format(
            user_question=user_question,
            schema_context=schema_context or "（未提供 schema 信息）",
            generated_sql=generated_sql or "（未生成 SQL）",
            sql_result=self._format_sql_result(sql_result),
            ai_response=ai_response or "（无回答）",
        )
        
        try:
            # 调用 LLM 进行评估
            response = await self._call_llm(
                system_prompt=self._get_judge_prompt(),
                user_prompt=user_prompt,
            )
            
            # 解析响应
            result = self._parse_response(response)
            return result
            
        except Exception as e:
            logger.error(f"LLM Judge 评估失败: {e}")
            # 返回默认评估结果
            return EvaluationResult(
                sql_correctness=3,
                result_interpretation=3,
                answer_completeness=3,
                expression_clarity=3,
                overall_score=3.0,
                strengths=[],
                weaknesses=["评估过程发生错误"],
                suggestions=[],
                confidence=0.0,
                reasoning=f"评估失败: {str(e)}",
            )
    
    def _format_sql_result(self, sql_result: Optional[str]) -> str:
        """格式化 SQL 结果"""
        if not sql_result:
            return "（无执行结果）"
        
        # 如果结果太长，截断
        if len(sql_result) > 2000:
            return sql_result[:2000] + "\n... (结果已截断)"
        
        return sql_result
    
    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM"""
        import asyncio
        
        # 使用 OpenAI 兼容的方式调用
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        # 检查是否有异步客户端
        client = self.llm._client
        
        # 在线程池中运行同步调用
        def sync_call():
            response = client.chat.completions.create(
                model=self.llm.model,
                messages=messages,
                temperature=0.3,  # 低温度提高一致性
                max_tokens=1500,
            )
            return response.choices[0].message.content or ""
        
        # 使用 asyncio 在线程池中执行同步调用
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, sync_call)
        return result
    
    def _parse_response(self, response: str) -> EvaluationResult:
        """解析 LLM 响应"""
        logger.info(f"LLM Judge 原始响应: {response[:500]}...")
        
        # 提取 JSON - 尝试多种方式
        json_str = None
        
        # 方式1: ```json ... ```
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end > start:
                json_str = response[start:end].strip()
        
        # 方式2: ``` ... ```
        if not json_str and "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end > start:
                json_str = response[start:end].strip()
        
        # 方式3: 直接查找 { ... }
        if not json_str:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                json_str = json_match.group(0)
        
        # 方式4: 整个响应作为 JSON
        if not json_str:
            json_str = response.strip()
        
        data = {}
        parse_error = None
        
        # 尝试解析 JSON
        for attempt, fix_func in enumerate([
            lambda s: s,  # 原样
            lambda s: s.replace("'", '"'),  # 单引号替换
            lambda s: re.sub(r',\s*}', '}', s.replace("'", '"')),  # 移除尾逗号
            lambda s: re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s),  # 移除控制字符
        ]):
            try:
                fixed_str = fix_func(json_str)
                data = json.loads(fixed_str)
                logger.info(f"JSON 解析成功 (attempt {attempt + 1})")
                break
            except json.JSONDecodeError as e:
                parse_error = e
                continue
        
        if not data:
            logger.error(f"JSON 解析完全失败: {parse_error}, 响应: {json_str[:300]}")
            # 尝试从文本中提取评分
            data = self._extract_scores_from_text(response)
        
        # 提取评分
        sql_correctness = self._safe_int(data.get("sql_correctness"), None)
        result_interpretation = self._safe_int(data.get("result_interpretation"), None)
        answer_completeness = self._safe_int(data.get("answer_completeness"), None)
        expression_clarity = self._safe_int(data.get("expression_clarity"), None)
        
        # 检查是否所有评分都有效
        scores = [sql_correctness, result_interpretation, answer_completeness, expression_clarity]
        valid_scores = [s for s in scores if s is not None]
        
        if len(valid_scores) == 0:
            logger.warning("未能从响应中提取任何有效评分")
            # 返回带有特殊标记的默认值
            return EvaluationResult(
                sql_correctness=3,
                result_interpretation=3,
                answer_completeness=3,
                expression_clarity=3,
                overall_score=3.0,
                strengths=[],
                weaknesses=["无法解析评估结果"],
                suggestions=["请检查 LLM 响应格式"],
                confidence=0.0,
                reasoning=f"解析失败，原始响应: {response[:200]}...",
            )
        
        # 用有效评分的平均值填充缺失值
        avg_score = sum(valid_scores) / len(valid_scores)
        sql_correctness = sql_correctness if sql_correctness is not None else int(avg_score)
        result_interpretation = result_interpretation if result_interpretation is not None else int(avg_score)
        answer_completeness = answer_completeness if answer_completeness is not None else int(avg_score)
        expression_clarity = expression_clarity if expression_clarity is not None else int(avg_score)
        
        # 计算总分
        overall_score = (
            sql_correctness + result_interpretation + 
            answer_completeness + expression_clarity
        ) / 4.0
        
        logger.info(f"评分结果: SQL={sql_correctness}, 解读={result_interpretation}, "
                   f"完整={answer_completeness}, 清晰={expression_clarity}, 总分={overall_score}")
        
        return EvaluationResult(
            sql_correctness=sql_correctness,
            result_interpretation=result_interpretation,
            answer_completeness=answer_completeness,
            expression_clarity=expression_clarity,
            overall_score=round(overall_score, 2),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            suggestions=data.get("suggestions", []),
            confidence=min(1.0, max(0.0, data.get("confidence", 0.7))),
            reasoning=data.get("reasoning", ""),
        )
    
    def _extract_scores_from_text(self, text: str) -> Dict[str, Any]:
        """从纯文本中提取评分（当 JSON 解析失败时的后备方案）"""
        import re
        data = {}
        
        # 尝试匹配类似 "SQL 正确性: 4" 或 "sql_correctness: 4" 的模式
        patterns = [
            (r'sql[_\s]*correctness[:\s]+(\d)', 'sql_correctness'),
            (r'SQL[正确性]*[:\s：]+(\d)', 'sql_correctness'),
            (r'result[_\s]*interpretation[:\s]+(\d)', 'result_interpretation'),
            (r'结果?解[读读][:\s：]+(\d)', 'result_interpretation'),
            (r'answer[_\s]*completeness[:\s]+(\d)', 'answer_completeness'),
            (r'回答[完整性]*[:\s：]+(\d)', 'answer_completeness'),
            (r'expression[_\s]*clarity[:\s]+(\d)', 'expression_clarity'),
            (r'表达[清晰度]*[:\s：]+(\d)', 'expression_clarity'),
        ]
        
        for pattern, key in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data[key] = int(match.group(1))
        
        logger.info(f"从文本提取的评分: {data}")
        return data
    
    @staticmethod
    def _safe_int(value: Any, default: Optional[int]) -> Optional[int]:
        """安全转换为整数"""
        if value is None:
            return default
        try:
            v = int(value)
            return max(1, min(5, v))  # 限制在 1-5
        except (TypeError, ValueError):
            return default


class FeedbackLearner:
    """
    反馈学习器：基于用户评分和 LLM 评估结果进行学习。
    
    功能：
    1. 高分案例自动加入 Memory
    2. 高分案例自动加入 RAG 知识库（新增）
    3. 低分案例分析弱项
    4. 生成 Few-shot 示例
    """
    
    def __init__(
        self,
        agent_memory,
        llm_judge: Optional[LLMJudge] = None,
        rag_learner=None,  # RAGLearner 实例（可选）
        *,
        high_score_threshold: float = 4.0,
        low_score_threshold: float = 2.5,
    ):
        """
        初始化反馈学习器。
        
        Args:
            agent_memory: Agent Memory 实例
            llm_judge: LLM Judge 实例（可选）
            rag_learner: RAG 学习器实例（可选）
            high_score_threshold: 高分阈值，超过此分数的案例会被学习
            low_score_threshold: 低分阈值，低于此分数的案例会被分析
        """
        self.memory = agent_memory
        self.judge = llm_judge
        self.rag_learner = rag_learner  # RAG 学习器
        self.high_score_threshold = high_score_threshold
        self.low_score_threshold = low_score_threshold
    
    async def learn_from_feedback(
        self,
        conversation_id: str,
        user_question: str,
        generated_sql: Optional[str],
        ai_response: str,
        user_rating: Optional[int] = None,
        expert_rating: Optional[int] = None,  # 专家评分（新增）
        llm_evaluation: Optional[EvaluationResult] = None,
    ) -> Dict[str, Any]:
        """
        从反馈中学习。
        
        Args:
            conversation_id: 会话 ID
            user_question: 用户问题
            generated_sql: 生成的 SQL
            ai_response: AI 回答
            user_rating: 用户评分 (1-5)
            llm_evaluation: LLM 评估结果
            
        Returns:
            学习结果
        """
        result = {
            "conversation_id": conversation_id,
            "learned": False,
            "action": None,
            "details": {},
        }
        
        # 计算综合评分（综合考虑专家评分、用户评分、LLM评分）
        scores = []
        if expert_rating:
            scores.append(expert_rating)
        if user_rating:
            scores.append(user_rating)
        if llm_evaluation:
            scores.append(llm_evaluation.overall_score)
        
        if not scores:
            result["action"] = "skipped"
            result["details"]["reason"] = "无评分数据"
            return result
        
        avg_score = sum(scores) / len(scores)
        result["details"]["average_score"] = avg_score
        result["details"]["expert_rating"] = expert_rating
        result["details"]["user_rating"] = user_rating
        result["details"]["llm_score"] = llm_evaluation.overall_score if llm_evaluation else None
        
        # 高分案例：加入 Memory 和 RAG 知识库
        if avg_score >= self.high_score_threshold and generated_sql:
            await self._learn_high_score_case(
                user_question, generated_sql, ai_response, avg_score
            )
            result["learned"] = True
            result["action"] = "added_to_memory"
            
            # 同时学习到 RAG 知识库
            rag_qa_id = None
            if self.rag_learner:
                try:
                    # 确定来源：优先专家评分
                    source = "expert" if expert_rating else ("feedback" if user_rating else "auto")
                    rag_qa_id = await self.rag_learner.learn_from_feedback(
                        conversation_id=conversation_id,
                        question=user_question,
                        sql=generated_sql,
                        answer=ai_response,
                        expert_rating=expert_rating,  # 传递专家评分
                        user_rating=user_rating,  # 传递用户评分
                        llm_score=llm_evaluation.overall_score if llm_evaluation else None,  # 传递LLM评分
                        source=source,
                    )
                    if rag_qa_id:
                        result["details"]["rag_qa_id"] = rag_qa_id
                        result["details"]["message"] = f"高分案例已加入 Memory 和 RAG 知识库（评分: {avg_score:.1f}）"
                    else:
                        result["details"]["message"] = f"高分案例已加入 Memory（评分: {avg_score:.1f}，RAG 学习跳过）"
                except Exception as e:
                    logger.warning(f"RAG 学习失败，但已保存到 Memory: {e}")
                    result["details"]["message"] = f"高分案例已加入 Memory（评分: {avg_score:.1f}，RAG 学习失败）"
            else:
                result["details"]["message"] = f"高分案例已加入 Memory（评分: {avg_score:.1f}）"
        
        # 低分案例：分析弱项
        elif avg_score <= self.low_score_threshold:
            analysis = self._analyze_low_score_case(
                user_question, generated_sql, ai_response, llm_evaluation
            )
            result["action"] = "analyzed_weakness"
            result["details"]["analysis"] = analysis
        
        else:
            result["action"] = "no_action"
            result["details"]["message"] = f"评分中等（{avg_score:.1f}），无需特殊处理"
        
        return result
    
    async def _learn_high_score_case(
        self,
        question: str,
        sql: str,
        response: str,
        score: float,
    ) -> None:
        """学习高分案例"""
        from vanna.core.tool import ToolContext
        
        # 创建一个模拟的 context
        class MockContext(ToolContext):
            def __init__(self):
                pass
        
        context = MockContext()
        
        # 保存到 Memory
        await self.memory.save_tool_usage(
            question=question,
            tool_name="RunSqlTool",
            args={"sql": sql},
            context=context,
            success=True,
            metadata={
                "source": "feedback_learning",
                "score": score,
                "response_preview": response[:200] if response else "",
            },
        )
        
        logger.info(f"高分案例已学习: score={score}, question={question[:50]}...")
    
    def _analyze_low_score_case(
        self,
        question: str,
        sql: Optional[str],
        response: str,
        evaluation: Optional[EvaluationResult],
    ) -> Dict[str, Any]:
        """分析低分案例"""
        analysis = {
            "question": question,
            "issues": [],
            "category": "unknown",
        }
        
        if evaluation:
            # 基于各维度评分识别问题
            if evaluation.sql_correctness <= 2:
                analysis["issues"].append("SQL 生成质量差")
                analysis["category"] = "sql_generation"
            
            if evaluation.result_interpretation <= 2:
                analysis["issues"].append("数据解读不准确")
                analysis["category"] = "interpretation"
            
            if evaluation.answer_completeness <= 2:
                analysis["issues"].append("回答不完整")
                analysis["category"] = "completeness"
            
            if evaluation.expression_clarity <= 2:
                analysis["issues"].append("表达不清晰")
                analysis["category"] = "clarity"
            
            analysis["weaknesses"] = evaluation.weaknesses
            analysis["suggestions"] = evaluation.suggestions
        
        else:
            # 基于简单规则分析
            if not sql:
                analysis["issues"].append("未能生成 SQL")
                analysis["category"] = "sql_generation"
            elif not response:
                analysis["issues"].append("未能生成回答")
                analysis["category"] = "response_generation"
        
        return analysis


class AutoOptimizer:
    """
    自动优化器：基于评测数据自动优化 Agent。
    
    功能：
    1. 识别系统性弱项
    2. 生成 Few-shot 示例
    3. 动态调整 System Prompt
    """
    
    def __init__(
        self,
        agent_memory,
        llm_service: OpenAILlmService,
    ):
        self.memory = agent_memory
        self.llm = llm_service
        self._weakness_stats: Dict[str, int] = {}
        self._improvement_suggestions: List[str] = []
    
    def record_weakness(self, category: str) -> None:
        """记录弱项"""
        self._weakness_stats[category] = self._weakness_stats.get(category, 0) + 1
    
    def get_weakness_report(self) -> Dict[str, Any]:
        """获取弱项报告"""
        total = sum(self._weakness_stats.values())
        if total == 0:
            return {"total_issues": 0, "categories": {}}
        
        report = {
            "total_issues": total,
            "categories": {},
        }
        
        for category, count in sorted(
            self._weakness_stats.items(), 
            key=lambda x: x[1], 
            reverse=True
        ):
            report["categories"][category] = {
                "count": count,
                "percentage": round(count / total * 100, 1),
            }
        
        return report
    
    async def generate_fewshot_examples(
        self,
        category: str,
        limit: int = 3,
    ) -> List[Dict[str, str]]:
        """
        为特定类别生成 Few-shot 示例。
        
        Args:
            category: 问题类别
            limit: 示例数量
            
        Returns:
            Few-shot 示例列表
        """
        from vanna.core.tool import ToolContext
        
        class MockContext(ToolContext):
            def __init__(self):
                pass
        
        context = MockContext()
        
        # 从 Memory 中搜索高质量的相关案例
        results = await self.memory.search_similar_usage(
            question=f"示例问题关于{category}",
            context=context,
            limit=limit * 2,
            similarity_threshold=0.3,
        )
        
        # 筛选高分案例
        examples = []
        for r in results:
            metadata = r.memory.metadata or {}
            if metadata.get("source") == "feedback_learning":
                examples.append({
                    "question": r.memory.question,
                    "sql": r.memory.args.get("sql", ""),
                })
                if len(examples) >= limit:
                    break
        
        return examples
    
    def suggest_prompt_improvements(self) -> List[str]:
        """基于弱项报告建议 Prompt 改进"""
        suggestions = []
        report = self.get_weakness_report()
        
        if not report["categories"]:
            return ["当前无明显弱项，建议继续收集评测数据"]
        
        # 根据弱项类别给出建议
        for category, data in report["categories"].items():
            if data["percentage"] < 10:
                continue
            
            if category == "sql_generation":
                suggestions.append(
                    "SQL 生成是主要弱项，建议：\n"
                    "1. 在 System Prompt 中增加更多 SQL 语法说明\n"
                    "2. 添加常见查询模式的 Few-shot 示例\n"
                    "3. 确保 Schema 信息完整加载到 Memory"
                )
            
            elif category == "interpretation":
                suggestions.append(
                    "数据解读准确性需要提升，建议：\n"
                    "1. 增加对数据异常值的处理说明\n"
                    "2. 要求 AI 在回答中引用具体数字\n"
                    "3. 添加数据解读的示例"
                )
            
            elif category == "completeness":
                suggestions.append(
                    "回答完整性需要改进，建议：\n"
                    "1. 在 Prompt 中要求检查是否回答了用户所有问题\n"
                    "2. 添加「总结」步骤\n"
                    "3. 要求列出关键发现"
                )
            
            elif category == "clarity":
                suggestions.append(
                    "表达清晰度需要提升，建议：\n"
                    "1. 要求使用结构化格式（标题、列表）\n"
                    "2. 限制回答长度，避免冗余\n"
                    "3. 要求使用简洁的中文表达"
                )
        
        return suggestions

