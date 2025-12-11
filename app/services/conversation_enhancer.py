"""
多轮对话增强服务。

提供：
1. 指代消解 - 理解 "再加上"、"换成" 等上下文引用
2. SQL 上下文 - 基于上次 SQL 进行修改
3. 追问处理 - 基于上次结果追问
"""

import re
import json
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """对话上下文"""
    conversation_id: str
    last_question: Optional[str] = None
    last_sql: Optional[str] = None
    last_result_summary: Optional[str] = None
    last_columns: List[str] = field(default_factory=list)
    last_tables: List[str] = field(default_factory=list)
    turn_count: int = 0
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "last_question": self.last_question,
            "last_sql": self.last_sql,
            "last_result_summary": self.last_result_summary,
            "last_columns": self.last_columns,
            "last_tables": self.last_tables,
            "turn_count": self.turn_count,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class RewrittenQuery:
    """改写后的查询"""
    original: str
    rewritten: str
    intent: str  # new_query, followup, correction
    context_used: bool
    modifications: List[str] = field(default_factory=list)


class ConversationEnhancer:
    """多轮对话增强器"""
    
    # 默认 Prompt（作为fallback）
    DEFAULT_REWRITE_PROMPT = """你是一个数据分析助手。用户的问题可能引用了之前的对话上下文。
请将用户的问题改写成一个完整、独立的问题。

## 对话上下文
上一个问题: {last_question}
上一个 SQL: 
```sql
{last_sql}
```
上次结果摘要: {last_result_summary}
涉及的列: {last_columns}
涉及的表: {last_tables}

## 用户新问题
{new_question}

## 意图类型
{intent}

## 改写要求
1. 如果是追问（followup），在上次查询基础上添加新的维度或条件
2. 如果是修正（correction），替换上次查询中的错误部分
3. 保持问题的完整性，使其无需上下文也能理解
4. 不要改变用户的原始意图

请输出改写后的完整问题。只输出问题本身，不要有任何解释。

改写后的问题:"""

    DEFAULT_SQL_MODIFY_PROMPT = """你是一个 SQL 专家。请根据用户的要求修改已有的 SQL 查询。

## 原 SQL
```sql
{original_sql}
```

## 用户要求
{modification_request}

## 数据库表结构
{schema_context}

## 修改要求
1. 保持原有查询的主体结构
2. 只修改用户要求的部分
3. 确保 SQL 语法正确
4. 如果需要添加新的列或表，请使用正确的表名和列名

请输出修改后的完整 SQL。只输出 SQL，不要有任何解释。

修改后的 SQL:"""

    def __init__(self, llm_service=None, sql_validator=None, prompt_manager=None):
        """
        初始化对话增强器。
        
        Args:
            llm_service: LLM 服务
            sql_validator: SQL 校验器
            prompt_manager: Prompt管理器（可选）
        """
        self.llm = llm_service
        self.validator = sql_validator
        self.prompt_manager = prompt_manager
        self._contexts: Dict[str, ConversationContext] = {}
    
    def _get_rewrite_prompt(self) -> str:
        """获取问题改写 Prompt"""
        if self.prompt_manager:
            return self.prompt_manager.get_active_prompt_content(
                "rewrite_prompt",
                fallback=self.DEFAULT_REWRITE_PROMPT
            )
        return self.DEFAULT_REWRITE_PROMPT
    
    def _get_sql_modify_prompt(self) -> str:
        """获取 SQL 修改 Prompt"""
        if self.prompt_manager:
            return self.prompt_manager.get_active_prompt_content(
                "sql_modify_prompt",
                fallback=self.DEFAULT_SQL_MODIFY_PROMPT
            )
        return self.DEFAULT_SQL_MODIFY_PROMPT
    
    def get_context(self, conversation_id: str) -> Optional[ConversationContext]:
        """获取对话上下文"""
        return self._contexts.get(conversation_id)
    
    def update_context(
        self,
        conversation_id: str,
        question: str,
        sql: Optional[str] = None,
        result_data: Optional[List[Dict]] = None,
    ) -> ConversationContext:
        """
        更新对话上下文。
        
        Args:
            conversation_id: 对话 ID
            question: 用户问题
            sql: 生成的 SQL
            result_data: 查询结果数据
        """
        context = self._contexts.get(conversation_id) or ConversationContext(
            conversation_id=conversation_id
        )
        
        context.last_question = question
        context.last_sql = sql
        context.turn_count += 1
        context.updated_at = datetime.now()
        
        # 从 SQL 中提取表名和列名
        if sql:
            context.last_tables = self._extract_tables(sql)
            context.last_columns = self._extract_columns(sql)
        
        # 生成结果摘要
        if result_data:
            context.last_result_summary = self._summarize_result(result_data)
        
        self._contexts[conversation_id] = context
        return context
    
    def clear_context(self, conversation_id: str) -> None:
        """清除对话上下文"""
        if conversation_id in self._contexts:
            del self._contexts[conversation_id]
    
    async def rewrite_query(
        self,
        question: str,
        conversation_id: str,
        intent: str,
    ) -> RewrittenQuery:
        """
        改写用户查询。
        
        Args:
            question: 用户原始问题
            conversation_id: 对话 ID
            intent: 意图类型
            
        Returns:
            改写后的查询
        """
        context = self.get_context(conversation_id)
        
        # 如果是新查询或没有上下文，直接返回原问题
        if intent == "new_query" or not context or not context.last_sql:
            return RewrittenQuery(
                original=question,
                rewritten=question,
                intent=intent,
                context_used=False,
            )
        
        # 使用规则进行基础改写
        rule_rewritten, modifications = self._rule_based_rewrite(question, context, intent)
        
        if rule_rewritten != question:
            return RewrittenQuery(
                original=question,
                rewritten=rule_rewritten,
                intent=intent,
                context_used=True,
                modifications=modifications,
            )
        
        # 使用 LLM 进行改写
        if self.llm:
            llm_rewritten = await self._llm_rewrite(question, context, intent)
            if llm_rewritten and llm_rewritten != question:
                return RewrittenQuery(
                    original=question,
                    rewritten=llm_rewritten,
                    intent=intent,
                    context_used=True,
                    modifications=["LLM 改写"],
                )
        
        return RewrittenQuery(
            original=question,
            rewritten=question,
            intent=intent,
            context_used=False,
        )
    
    async def modify_sql(
        self,
        original_sql: str,
        modification_request: str,
        schema_context: str = "",
    ) -> Optional[str]:
        """
        基于用户请求修改 SQL。
        
        Args:
            original_sql: 原始 SQL
            modification_request: 修改请求
            schema_context: 数据库 schema 上下文
            
        Returns:
            修改后的 SQL
        """
        if not self.llm:
            return None
        
        prompt = self._get_sql_modify_prompt().format(
            original_sql=original_sql,
            modification_request=modification_request,
            schema_context=schema_context or "未提供",
        )
        
        try:
            modified_sql = await self._call_llm(prompt)
            modified_sql = self._clean_sql(modified_sql)
            
            # 验证修改后的 SQL
            if self.validator:
                validation = self.validator.validate(modified_sql)
                if not validation.is_valid:
                    logger.warning(f"修改后的 SQL 验证失败: {validation.error_message}")
                    return None
            
            return modified_sql
            
        except Exception as e:
            logger.error(f"SQL 修改失败: {e}")
            return None
    
    def _rule_based_rewrite(
        self,
        question: str,
        context: ConversationContext,
        intent: str,
    ) -> Tuple[str, List[str]]:
        """基于规则的改写"""
        rewritten = question
        modifications = []
        
        # 处理追问
        if intent == "followup":
            # 环比分析
            if re.search(r"环比", question):
                rewritten = "在之前的查询基础上，计算环比增长率"
                modifications.append("添加环比计算")
                if context.last_question:
                    rewritten = f"基于「{context.last_question}」的结果，计算环比增长率"
            
            # 同比分析
            elif re.search(r"同比", question):
                rewritten = "在之前的查询基础上，计算同比增长率"
                modifications.append("添加同比计算")
                if context.last_question:
                    rewritten = f"基于「{context.last_question}」的结果，计算同比增长率"
            
            # 对比分析
            elif re.search(r"对比|比较", question):
                rewritten = "对比之前查询结果与不同时间段的数据"
                modifications.append("添加对比分析")
                if context.last_question:
                    rewritten = f"对比「{context.last_question}」的结果与其他时间段的数据"
            
            # "再加上 X" -> "查询 [上次内容] 并添加 X"
            elif re.search(r"(再)?加(上|个)(.+)", question):
                match = re.search(r"(再)?加(上|个)(.+)", question)
                if match:
                    addition = match.group(3)
                    rewritten = f"在之前的查询基础上添加{addition}"
                    modifications.append(f"添加: {addition}")
            
            # "按 X 拆分/分组" -> "将上次结果按 X 拆分"
            elif re.search(r"按(.+?)(拆分|分组|维度)", question):
                match = re.search(r"按(.+?)(拆分|分组|维度)", question)
                if match:
                    dimension = match.group(1)
                    rewritten = f"将之前的查询按{dimension}进行分组"
                    modifications.append(f"分组维度: {dimension}")
            
            # "换成 X" -> "将上次结果的 Y 换成 X"
            elif re.search(r"换成(.+)", question):
                match = re.search(r"换成(.+)", question)
                if match:
                    new_value = match.group(1)
                    rewritten = f"将之前查询的指标换成{new_value}"
                    modifications.append(f"替换为: {new_value}")
            
            # 默认追问改写
            else:
                if context.last_question:
                    rewritten = f"基于「{context.last_question}」的结果，{question}"
                else:
                    rewritten = f"在之前的查询基础上，{question}"
        
        # 处理修正
        elif intent == "correction":
            # "应该是 X 不是 Y"
            match = re.search(r"应该是(.+?)不是(.+)", question)
            if match:
                correct = match.group(1)
                wrong = match.group(2)
                rewritten = f"修正：将之前查询中的{wrong}改为{correct}"
                modifications.append(f"修正: {wrong} -> {correct}")
        
        # 如果改写了，补充上下文
        if rewritten != question and context.last_question:
            rewritten = f"上一个问题是「{context.last_question}」。{rewritten}"
        
        return rewritten, modifications
    
    async def _llm_rewrite(
        self,
        question: str,
        context: ConversationContext,
        intent: str,
    ) -> Optional[str]:
        """使用 LLM 改写"""
        prompt = self._get_rewrite_prompt().format(
            last_question=context.last_question or "无",
            last_sql=context.last_sql or "无",
            last_result_summary=context.last_result_summary or "无",
            last_columns=", ".join(context.last_columns) if context.last_columns else "无",
            last_tables=", ".join(context.last_tables) if context.last_tables else "无",
            new_question=question,
            intent=intent,
        )
        
        try:
            return await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"LLM 改写失败: {e}")
            return None
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        messages = [{"role": "user", "content": prompt}]
        
        def sync_call():
            response = self.llm._client.chat.completions.create(
                model=self.llm.model,
                messages=messages,
                temperature=0.3,
                max_tokens=500,
            )
            return response.choices[0].message.content or ""
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, sync_call)
        return result.strip()
    
    def _clean_sql(self, sql: str) -> str:
        """清理 SQL"""
        sql = sql.strip()
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        sql = re.sub(r'^sql\s*', '', sql, flags=re.IGNORECASE)
        return sql.strip()
    
    def _extract_tables(self, sql: str) -> List[str]:
        """从 SQL 中提取表名"""
        tables = []
        patterns = [
            r'FROM\s+(\w+)',
            r'JOIN\s+(\w+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.extend(matches)
        return list(set(tables))
    
    def _extract_columns(self, sql: str) -> List[str]:
        """从 SQL 中提取列名"""
        # 提取 SELECT 和 GROUP BY 中的列
        columns = []
        
        # SELECT 部分
        select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_part = select_match.group(1)
            # 简单解析，按逗号分割
            for col in select_part.split(','):
                col = col.strip()
                # 处理别名
                if ' AS ' in col.upper():
                    col = col.upper().split(' AS ')[0].strip()
                # 移除函数包装
                col_match = re.search(r'\(([^)]+)\)', col)
                if col_match:
                    col = col_match.group(1)
                if col and col != '*':
                    columns.append(col.split('.')[-1])  # 移除表前缀
        
        # GROUP BY 部分
        group_match = re.search(r'GROUP\s+BY\s+(.+?)(?:ORDER|HAVING|LIMIT|$)', sql, re.IGNORECASE)
        if group_match:
            for col in group_match.group(1).split(','):
                col = col.strip().split('.')[-1]
                if col:
                    columns.append(col)
        
        return list(set(columns))
    
    def _summarize_result(self, result_data: List[Dict], max_rows: int = 3) -> str:
        """生成结果摘要"""
        if not result_data:
            return "无数据"
        
        total_rows = len(result_data)
        columns = list(result_data[0].keys()) if result_data else []
        
        summary_parts = [f"共 {total_rows} 条记录"]
        summary_parts.append(f"列: {', '.join(columns)}")
        
        # 前几行数据预览
        if total_rows <= max_rows:
            preview = result_data
        else:
            preview = result_data[:max_rows]
        
        for i, row in enumerate(preview, 1):
            values = [f"{k}={v}" for k, v in list(row.items())[:3]]
            summary_parts.append(f"第{i}行: {', '.join(values)}")
        
        return "; ".join(summary_parts)


# 全局单例
_conversation_enhancer: Optional[ConversationEnhancer] = None


def init_conversation_enhancer(
    llm_service=None,
    sql_validator=None,
    prompt_manager=None,
) -> ConversationEnhancer:
    """初始化对话增强器"""
    global _conversation_enhancer
    _conversation_enhancer = ConversationEnhancer(llm_service, sql_validator, prompt_manager)
    return _conversation_enhancer


def get_conversation_enhancer() -> Optional[ConversationEnhancer]:
    return _conversation_enhancer

