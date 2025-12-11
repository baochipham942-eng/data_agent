"""
SQL 增强服务。

提供：
1. SQL 自纠错 - 执行失败时自动修复
2. SQL 预校验 - 执行前检查语法和表/列名
3. Few-shot 动态选择 - 基于相似度检索历史案例
"""

import re
import json
import sqlite3
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SQLValidationResult:
    """SQL 校验结果"""
    is_valid: bool
    error_type: Optional[str] = None  # syntax, table_not_found, column_not_found, etc.
    error_message: Optional[str] = None
    suggestions: List[str] = None
    
    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []


@dataclass
class SQLFixResult:
    """SQL 修复结果"""
    success: bool
    original_sql: str
    fixed_sql: Optional[str] = None
    fix_description: Optional[str] = None
    attempts: int = 0


class SQLValidator:
    """SQL 预校验器"""
    
    def __init__(self, db_path: Path):
        """
        初始化 SQL 校验器。
        
        Args:
            db_path: 数据库路径
        """
        self.db_path = Path(db_path)
        self._schema_cache: Dict[str, List[str]] = {}
        self._load_schema()
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _load_schema(self) -> None:
        """加载数据库 schema 到缓存"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # 获取所有表名
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                cursor.execute(f'PRAGMA table_info("{table}")')
                columns = [col["name"] for col in cursor.fetchall()]
                self._schema_cache[table.lower()] = [c.lower() for c in columns]
            
            conn.close()
            logger.info(f"SQL 校验器加载了 {len(self._schema_cache)} 个表的 schema")
        except Exception as e:
            logger.error(f"加载 schema 失败: {e}")
    
    def refresh_schema(self) -> None:
        """刷新 schema 缓存"""
        self._schema_cache.clear()
        self._load_schema()
    
    def validate(self, sql: str) -> SQLValidationResult:
        """
        校验 SQL 语句。
        
        检查项：
        1. 基本语法
        2. 表名是否存在
        3. 列名是否存在
        """
        sql = sql.strip()
        
        if not sql:
            return SQLValidationResult(
                is_valid=False,
                error_type="empty",
                error_message="SQL 语句为空",
            )
        
        # 1. 语法检查（使用 SQLite 的 EXPLAIN）
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(f"EXPLAIN {sql}")
            conn.close()
        except sqlite3.OperationalError as e:
            error_msg = str(e)
            
            # 解析错误类型
            if "no such table" in error_msg:
                table_match = re.search(r"no such table: (\w+)", error_msg)
                table_name = table_match.group(1) if table_match else "unknown"
                
                # 提供建议
                suggestions = self._suggest_similar_table(table_name)
                
                return SQLValidationResult(
                    is_valid=False,
                    error_type="table_not_found",
                    error_message=f"表 '{table_name}' 不存在",
                    suggestions=suggestions,
                )
            
            elif "no such column" in error_msg:
                col_match = re.search(r"no such column: (\w+\.)?(\w+)", error_msg)
                col_name = col_match.group(2) if col_match else "unknown"
                
                # 提供建议
                suggestions = self._suggest_similar_column(col_name, sql)
                
                return SQLValidationResult(
                    is_valid=False,
                    error_type="column_not_found",
                    error_message=f"列 '{col_name}' 不存在",
                    suggestions=suggestions,
                )
            
            elif "syntax error" in error_msg.lower():
                return SQLValidationResult(
                    is_valid=False,
                    error_type="syntax",
                    error_message=f"SQL 语法错误: {error_msg}",
                )
            
            else:
                return SQLValidationResult(
                    is_valid=False,
                    error_type="other",
                    error_message=error_msg,
                )
        
        except Exception as e:
            return SQLValidationResult(
                is_valid=False,
                error_type="unknown",
                error_message=str(e),
            )
        
        return SQLValidationResult(is_valid=True)
    
    def _suggest_similar_table(self, table_name: str) -> List[str]:
        """建议相似的表名"""
        table_lower = table_name.lower()
        suggestions = []
        
        for existing_table in self._schema_cache.keys():
            # 简单的相似度计算（包含关系或编辑距离小）
            if table_lower in existing_table or existing_table in table_lower:
                suggestions.append(f"是否要查询 '{existing_table}' 表？")
            elif self._levenshtein_distance(table_lower, existing_table) <= 3:
                suggestions.append(f"是否要查询 '{existing_table}' 表？")
        
        if not suggestions:
            available = list(self._schema_cache.keys())[:5]
            suggestions.append(f"可用的表: {', '.join(available)}")
        
        return suggestions[:3]
    
    def _suggest_similar_column(self, col_name: str, sql: str) -> List[str]:
        """建议相似的列名"""
        col_lower = col_name.lower()
        suggestions = []
        
        # 从 SQL 中提取涉及的表
        tables_in_sql = self._extract_tables_from_sql(sql)
        
        for table in tables_in_sql:
            if table.lower() in self._schema_cache:
                columns = self._schema_cache[table.lower()]
                for col in columns:
                    if col_lower in col or col in col_lower:
                        suggestions.append(f"表 '{table}' 中是否要使用列 '{col}'？")
                    elif self._levenshtein_distance(col_lower, col) <= 2:
                        suggestions.append(f"表 '{table}' 中是否要使用列 '{col}'？")
        
        return suggestions[:3]
    
    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        """从 SQL 中提取表名"""
        tables = []
        
        # 匹配 FROM 和 JOIN 后的表名
        patterns = [
            r'FROM\s+(\w+)',
            r'JOIN\s+(\w+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.extend(matches)
        
        return list(set(tables))
    
    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """计算编辑距离"""
        if len(s1) < len(s2):
            return SQLValidator._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def get_schema_context(self) -> str:
        """获取 schema 上下文字符串"""
        context_parts = []
        for table, columns in self._schema_cache.items():
            context_parts.append(f"表 {table}: {', '.join(columns)}")
        return "\n".join(context_parts)


class SQLAutoFixer:
    """SQL 自动修复器"""
    
    DEFAULT_FIX_PROMPT = """你是一个 SQL 专家。用户的 SQL 执行出错了，请帮助修复。

## 数据库 Schema
{schema_context}

## 原始 SQL
```sql
{original_sql}
```

## 错误信息
{error_message}

## 修复建议
{suggestions}

请分析错误原因并提供修复后的 SQL。只输出修复后的 SQL，不要有任何解释。如果无法修复，输出 "CANNOT_FIX"。

修复后的 SQL:
"""
    
    def __init__(
        self,
        llm_service,
        sql_validator: SQLValidator,
        max_retries: int = 2,
        prompt_manager=None,
    ):
        """
        初始化 SQL 自动修复器。
        
        Args:
            llm_service: LLM 服务
            sql_validator: SQL 校验器
            max_retries: 最大重试次数
            prompt_manager: Prompt管理器（可选）
        """
        self.llm = llm_service
        self.validator = sql_validator
        self.max_retries = max_retries
        self.prompt_manager = prompt_manager
    
    def _get_fix_prompt(self) -> str:
        """获取 SQL 修复 Prompt"""
        if self.prompt_manager:
            return self.prompt_manager.get_active_prompt_content(
                "sql_fix_prompt",
                fallback=self.DEFAULT_FIX_PROMPT
            )
        return self.DEFAULT_FIX_PROMPT
    
    async def fix_sql(
        self,
        sql: str,
        error_message: str,
        validation_result: Optional[SQLValidationResult] = None,
    ) -> SQLFixResult:
        """
        尝试修复 SQL。
        
        Args:
            sql: 原始 SQL
            error_message: 错误信息
            validation_result: 校验结果（可选）
            
        Returns:
            修复结果
        """
        if not validation_result:
            validation_result = self.validator.validate(sql)
        
        # 构造修复 prompt
        prompt = self._get_fix_prompt().format(
            schema_context=self.validator.get_schema_context(),
            original_sql=sql,
            error_message=error_message,
            suggestions="\n".join(validation_result.suggestions) if validation_result.suggestions else "无",
        )
        
        for attempt in range(self.max_retries):
            try:
                # 调用 LLM 修复
                fixed_sql = await self._call_llm(prompt)
                
                if not fixed_sql or "CANNOT_FIX" in fixed_sql.upper():
                    logger.warning(f"LLM 无法修复 SQL (attempt {attempt + 1})")
                    continue
                
                # 清理 SQL
                fixed_sql = self._clean_sql(fixed_sql)
                
                # 验证修复后的 SQL
                new_validation = self.validator.validate(fixed_sql)
                
                if new_validation.is_valid:
                    logger.info(f"SQL 修复成功 (attempt {attempt + 1})")
                    return SQLFixResult(
                        success=True,
                        original_sql=sql,
                        fixed_sql=fixed_sql,
                        fix_description=f"修复了 {validation_result.error_type} 错误",
                        attempts=attempt + 1,
                    )
                else:
                    # 修复后仍有问题，更新 prompt 继续尝试
                    prompt = self._get_fix_prompt().format(
                        schema_context=self.validator.get_schema_context(),
                        original_sql=fixed_sql,
                        error_message=new_validation.error_message,
                        suggestions="\n".join(new_validation.suggestions) if new_validation.suggestions else "无",
                    )
                    
            except Exception as e:
                logger.error(f"SQL 修复失败 (attempt {attempt + 1}): {e}")
        
        return SQLFixResult(
            success=False,
            original_sql=sql,
            attempts=self.max_retries,
        )
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        import asyncio
        
        messages = [
            {"role": "user", "content": prompt},
        ]
        
        def sync_call():
            response = self.llm._client.chat.completions.create(
                model=self.llm.model,
                messages=messages,
                temperature=0.1,
                max_tokens=500,
            )
            return response.choices[0].message.content or ""
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, sync_call)
        return result
    
    def _clean_sql(self, sql: str) -> str:
        """清理 SQL 输出"""
        sql = sql.strip()
        
        # 移除 markdown 代码块
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        
        # 移除 sql 标记
        sql = re.sub(r'^sql\s*', '', sql, flags=re.IGNORECASE)
        
        return sql.strip()


class FewShotSelector:
    """Few-shot 动态选择器（支持 RAG 知识库优先检索）"""
    
    def __init__(
        self,
        agent_memory,
        rag_knowledge_base=None,  # RAG 知识库实例（可选）
        top_k: int = 3,
    ):
        """
        初始化 Few-shot 选择器。
        
        Args:
            agent_memory: Agent Memory 实例
            rag_knowledge_base: RAG 知识库实例（可选，优先使用）
            top_k: 返回的案例数量
        """
        self.memory = agent_memory
        self.rag_kb = rag_knowledge_base
        self.top_k = top_k
    
    async def select_examples(
        self,
        question: str,
        min_similarity: float = 0.3,
        return_debug_info: bool = False,  # 是否返回调试信息
    ) -> List[Dict[str, Any]]:
        """
        根据问题选择相似的历史案例。
        
        优先级：
        1. RAG 知识库（高质量示例）
        2. Agent Memory（历史案例）
        
        Args:
            question: 用户问题
            min_similarity: 最小相似度阈值
            return_debug_info: 是否返回调试信息（RAG/Memory使用情况）
            
        Returns:
            相似案例列表（如果return_debug_info=True，返回包含调试信息的字典）
        """
        examples = []
        debug_info = {
            "rag_used": False,
            "rag_count": 0,
            "memory_used": False,
            "memory_count": 0,
        }
        
        # 1. 优先从 RAG 知识库检索（高质量示例）
        if self.rag_kb:
            try:
                rag_results = self.rag_kb.retrieve_similar(
                    query=question,
                    top_k=self.top_k,
                    min_score=3.5,  # 只取高质量示例
                    min_quality=0.7,
                )
                
                debug_info["rag_used"] = True
                debug_info["rag_count"] = len(rag_results)
                
                for rag_result in rag_results:
                    # 更新使用计数
                    self.rag_kb.update_usage(rag_result.qa_id)
                    
                    examples.append({
                        "question": rag_result.question,
                        "sql": rag_result.sql,
                        "similarity": rag_result.similarity,
                        "source": "rag",  # 标记来源
                        "score": rag_result.score,
                        "quality_score": rag_result.quality_score,
                    })
                
                # 如果 RAG 知识库已经提供了足够的示例，直接返回
                if len(examples) >= self.top_k:
                    examples.sort(key=lambda x: x.get("similarity", 0), reverse=True)
                    if return_debug_info:
                        return {
                            "examples": examples[:self.top_k],
                            "debug_info": debug_info,
                        }
                    return examples[:self.top_k]
            except Exception as e:
                logger.warning(f"从 RAG 知识库检索失败: {e}，降级到 Memory 检索")
        
        # 2. 从 Memory 中补充（如果 RAG 知识库示例不足）
        from vanna.core.tool import ToolContext
        
        class MockContext(ToolContext):
            def __init__(self):
                pass
        
        context = MockContext()
        
        memory_examples_count = 0
        try:
            similar_usages = await self.memory.search_similar_usage(
                question=question,
                context=context,
                tool_name_filter="run_sql",
                limit=self.top_k * 2,  # 多取一些，后面筛选
            )
            
            # 筛选高质量案例（避免与 RAG 重复）
            existing_questions = {ex["question"].lower() for ex in examples}
            
            for result in similar_usages:
                if len(examples) >= self.top_k:
                    break
                
                memory = result.memory
                similarity = result.similarity
                
                if similarity >= min_similarity:
                    # 提取 SQL
                    args = memory.args
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except:
                            args = {}
                    
                    sql = args.get("sql", "") if isinstance(args, dict) else ""
                    if sql and memory.question.lower() not in existing_questions:
                        examples.append({
                            "question": memory.question,
                            "sql": sql,
                            "similarity": similarity,
                            "source": "memory",
                        })
                        existing_questions.add(memory.question.lower())
                        memory_examples_count += 1
            
            if memory_examples_count > 0:
                debug_info["memory_used"] = True
                debug_info["memory_count"] = memory_examples_count
        except Exception as e:
            logger.warning(f"从 Memory 检索失败: {e}")
        
        # 按相似度排序
        examples.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        
        if return_debug_info:
            return {
                "examples": examples[:self.top_k],
                "debug_info": debug_info,
            }
        
        return examples[:self.top_k]
    
    def format_examples(self, examples: List[Dict[str, Any]]) -> str:
        """
        格式化案例为 prompt 字符串。
        
        Args:
            examples: 案例列表
            
        Returns:
            格式化后的字符串
        """
        if not examples:
            return ""
        
        parts = ["以下是一些相似问题的示例：\n"]
        
        for i, ex in enumerate(examples, 1):
            parts.append(f"示例 {i}:")
            parts.append(f"问题: {ex['question']}")
            parts.append(f"SQL: {ex['sql']}")
            parts.append("")
        
        return "\n".join(parts)
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（基于词重叠的 Jaccard 相似度）"""
        if not text1 or not text2:
            return 0.0
        
        # 分词（简单按空格和标点分割）
        def tokenize(text: str) -> set:
            text = text.lower()
            # 中文按字分割，英文按单词分割
            tokens = set()
            for char in text:
                if '\u4e00' <= char <= '\u9fff':
                    tokens.add(char)
            words = re.findall(r'\w+', text)
            tokens.update(words)
            return tokens
        
        tokens1 = tokenize(text1)
        tokens2 = tokenize(text2)
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        
        return len(intersection) / len(union)


class IntentClassifier:
    """意图分类器"""
    
    INTENTS = {
        "new_query": "新查询",
        "followup": "追问（基于上次结果）",
        "correction": "修正（修改上次查询）",
        "clarification": "澄清（补充信息）",
        "chitchat": "闲聊",
    }
    
    DEFAULT_CLASSIFY_PROMPT = """你是一个智能助手，需要判断用户的意图类型。

## 上下文
{context}

## 用户输入
{user_input}

## 意图类型
1. new_query: 全新的数据查询问题
2. followup: 基于上次结果的追问，如"再加上地区维度"、"按月份拆分"
3. correction: 修正上次查询，如"不对，应该是销售额不是销量"
4. clarification: 补充澄清信息，如"是北京的数据"
5. chitchat: 闲聊或非数据查询问题

请只输出意图类型的英文标识（如 new_query），不要有任何其他内容。

意图:"""
    
    # 规则匹配模式
    FOLLOWUP_PATTERNS = [
        r"再加上",
        r"加个",
        r"按.*拆分",
        r"按.*维度",
        r"改成按",
        r"换成",
        r"那.*呢",
        r"还有.*呢",
        r"其他.*呢",
        r"分别",
    ]
    
    CORRECTION_PATTERNS = [
        r"不对",
        r"错了",
        r"应该是",
        r"不是.*是",
        r"搞错了",
    ]
    
    CHITCHAT_PATTERNS = [
        r"^你好",
        r"^谢谢",
        r"^好的",
        r"^明白",
        r"^嗯",
        r"^哦",
        r"你是谁",
        r"你能做什么",
    ]
    
    def __init__(self, llm_service=None, use_llm: bool = False, prompt_manager=None):
        """
        初始化意图分类器。
        
        Args:
            llm_service: LLM 服务（可选）
            use_llm: 是否使用 LLM 进行分类
            prompt_manager: Prompt管理器（可选）
        """
        self.llm = llm_service
        self.use_llm = use_llm and llm_service is not None
        self.prompt_manager = prompt_manager
    
    def _get_classify_prompt(self) -> str:
        """获取意图分类 Prompt"""
        if self.prompt_manager:
            return self.prompt_manager.get_active_prompt_content(
                "intent_classify_prompt",
                fallback=self.DEFAULT_CLASSIFY_PROMPT
            )
        return self.DEFAULT_CLASSIFY_PROMPT
    
    def classify(
        self,
        user_input: str,
        last_query: Optional[str] = None,
        last_sql: Optional[str] = None,
        last_result: Optional[str] = None,
    ) -> Tuple[str, float]:
        """
        分类用户意图。
        
        Args:
            user_input: 用户输入
            last_query: 上次查询问题
            last_sql: 上次 SQL
            last_result: 上次结果
            
        Returns:
            (意图类型, 置信度)
        """
        # 1. 先用规则匹配
        intent, confidence = self._rule_based_classify(user_input, last_sql)
        
        if confidence >= 0.8:
            return intent, confidence
        
        # 2. 如果规则不确定且启用 LLM，使用 LLM 分类
        if self.use_llm and confidence < 0.6:
            llm_intent = self._llm_classify(user_input, last_query, last_sql)
            if llm_intent:
                return llm_intent, 0.7
        
        return intent, confidence
    
    def _rule_based_classify(
        self,
        user_input: str,
        last_sql: Optional[str],
    ) -> Tuple[str, float]:
        """基于规则的分类"""
        text = user_input.lower()
        
        # 闲聊检测
        for pattern in self.CHITCHAT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return "chitchat", 0.9
        
        # 如果没有上下文，一定是新查询
        if not last_sql:
            return "new_query", 0.95
        
        # 修正检测
        for pattern in self.CORRECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return "correction", 0.85
        
        # 追问检测（包括快捷操作）
        for pattern in self.FOLLOWUP_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return "followup", 0.85
        
        # 检测快捷操作关键词
        quick_action_patterns = [
            r"环比",
            r"同比", 
            r"对比",
            r"比较",
            r"拆分",
            r"细分",
            r"按.*拆分",
            r"按.*分组",
        ]
        for pattern in quick_action_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return "followup", 0.9  # 快捷操作有更高的置信度
        
        # 检测是否是完整的新问题（包含查询动词和对象）
        query_verbs = ["查", "看", "统计", "分析", "显示", "列出", "找", "多少", "哪些", "什么"]
        has_query_verb = any(v in text for v in query_verbs)
        
        if has_query_verb and len(text) > 10:
            return "new_query", 0.7
        
        # 短句且有上下文，可能是追问
        if len(text) < 15 and last_sql:
            return "followup", 0.6
        
        return "new_query", 0.5
    
    def _llm_classify(
        self,
        user_input: str,
        last_query: Optional[str],
        last_sql: Optional[str],
    ) -> Optional[str]:
        """使用 LLM 分类"""
        if not self.llm:
            return None
        
        context = ""
        if last_query:
            context += f"上次问题: {last_query}\n"
        if last_sql:
            context += f"上次 SQL: {last_sql}\n"
        if not context:
            context = "无历史上下文"
        
        prompt = self._get_classify_prompt().format(
            context=context,
            user_input=user_input,
        )
        
        try:
            response = self.llm._client.chat.completions.create(
                model=self.llm.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=20,
            )
            
            result = response.choices[0].message.content.strip().lower()
            
            if result in self.INTENTS:
                return result
            
        except Exception as e:
            logger.error(f"LLM 意图分类失败: {e}")
        
        return None


# 全局单例
_sql_validator: Optional[SQLValidator] = None
_sql_fixer: Optional[SQLAutoFixer] = None
_few_shot_selector: Optional[FewShotSelector] = None
_intent_classifier: Optional[IntentClassifier] = None


def init_sql_enhancer(
    db_path: Path,
    llm_service=None,
    agent_memory=None,
    prompt_manager=None,
    rag_knowledge_base=None,  # RAG 知识库实例（可选）
    embedding_service=None,  # Embedding 服务实例（可选）
) -> Dict[str, Any]:
    """
    初始化 SQL 增强服务。
    
    Args:
        db_path: 数据库路径
        llm_service: LLM 服务
        agent_memory: Agent Memory
        prompt_manager: Prompt管理器（可选）
        rag_knowledge_base: RAG 知识库实例（可选）
        embedding_service: Embedding 服务实例（可选）
    
    Returns:
        包含各组件的字典
    """
    global _sql_validator, _sql_fixer, _few_shot_selector, _intent_classifier
    
    _sql_validator = SQLValidator(db_path)
    
    if llm_service:
        _sql_fixer = SQLAutoFixer(llm_service, _sql_validator, prompt_manager=prompt_manager)
        _intent_classifier = IntentClassifier(llm_service, use_llm=True, prompt_manager=prompt_manager)
    else:
        _intent_classifier = IntentClassifier(use_llm=False, prompt_manager=prompt_manager)
    
    if agent_memory:
        _few_shot_selector = FewShotSelector(
            agent_memory,
            rag_knowledge_base=rag_knowledge_base,
        )
    
    return {
        "validator": _sql_validator,
        "fixer": _sql_fixer,
        "few_shot": _few_shot_selector,
        "intent": _intent_classifier,
    }


def get_sql_validator() -> Optional[SQLValidator]:
    return _sql_validator


def get_sql_fixer() -> Optional[SQLAutoFixer]:
    return _sql_fixer


def get_few_shot_selector() -> Optional[FewShotSelector]:
    return _few_shot_selector


def get_intent_classifier() -> Optional[IntentClassifier]:
    return _intent_classifier

