"""
查询分析服务。

提供：
- 问题改写：将用户问题重新表述得更清晰
- 表选取：分析需要使用的数据表
- 业务知识检索：从知识库中检索相关规则
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """查询分析器"""
    
    def __init__(
        self,
        data_db_path: Path,
        knowledge_db_path: Optional[Path] = None,
        llm_service = None,  # 新增：LLM 服务，用于智能表选择
        prompt_manager = None,  # 新增：Prompt管理器
    ):
        """
        初始化查询分析器。
        
        Args:
            data_db_path: 数据数据库路径
            knowledge_db_path: 业务知识库路径
            llm_service: LLM 服务实例，用于智能表选择
            prompt_manager: Prompt管理器，用于获取激活的prompt
        """
        self.data_db_path = Path(data_db_path)
        self.knowledge_db_path = Path(knowledge_db_path) if knowledge_db_path else None
        self.llm = llm_service
        self.prompt_manager = prompt_manager
        
        # 缓存表结构信息
        self._table_info_cache: Dict[str, Dict[str, Any]] = {}
        self._schema_description: str = ""  # 缓存 schema 描述
        self._load_table_info()
        
        # 分析结果缓存（避免重复分析相同问题）
        self._analysis_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_max_size = 100  # 最多缓存100个分析结果
    
    def _get_table_select_prompt(self) -> str:
        """获取表选择 Prompt"""
        default_prompt = """你是一个数据库专家。根据用户问题，从以下数据库表中选择最相关的表。

## 数据库表结构
{schema_description}

## 用户问题
{question}

## 任务
请分析用户问题，选择最相关的数据表（可以选多个）。

请以 JSON 格式返回，格式如下：
{{"tables": ["表名1", "表名2"], "reason": "选择原因"}}

只输出 JSON，不要有其他内容。如果没有相关表，返回 {{"tables": [], "reason": "原因"}}"""
        
        if self.prompt_manager:
            return self.prompt_manager.get_active_prompt_content(
                "table_select_prompt",
                fallback=default_prompt
            )
        return default_prompt
    
    def _get_data_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.data_db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _get_knowledge_conn(self) -> Optional[sqlite3.Connection]:
        """获取知识库连接"""
        if not self.knowledge_db_path or not self.knowledge_db_path.exists():
            return None
        conn = sqlite3.connect(str(self.knowledge_db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _load_table_info(self) -> None:
        """加载表结构信息到缓存，并生成 schema 描述供 LLM 使用"""
        try:
            conn = self._get_data_conn()
            cursor = conn.cursor()
            
            # 获取所有表名
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            schema_parts = []
            
            for table in tables:
                cursor.execute(f'PRAGMA table_info("{table}")')
                columns = []
                for col in cursor.fetchall():
                    columns.append({
                        "name": col["name"],
                        "type": col["type"],
                    })
                
                # 获取行数
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                row_count = cursor.fetchone()[0]
                
                self._table_info_cache[table] = {
                    "name": table,
                    "columns": columns,
                    "column_names": [c["name"] for c in columns],
                    "row_count": row_count,
                }
                
                # 生成该表的 schema 描述
                col_desc = ", ".join([f"{c['name']}({c['type']})" for c in columns[:10]])
                if len(columns) > 10:
                    col_desc += f" ... 等共 {len(columns)} 个字段"
                schema_parts.append(f"- {table} ({row_count}行): {col_desc}")
            
            # 缓存完整的 schema 描述
            self._schema_description = "\n".join(schema_parts)
            
            conn.close()
            logger.info(f"加载了 {len(self._table_info_cache)} 个表的结构信息")
        except Exception as e:
            logger.error(f"加载表结构信息失败: {e}")
    
    def get_table_info(self) -> Dict[str, Dict[str, Any]]:
        """获取所有表信息"""
        return self._table_info_cache
    
    def analyze_tables(self, question: str) -> List[Dict[str, Any]]:
        """
        分析问题可能涉及的表。
        
        基于关键词匹配和表名/列名相似度。
        """
        question_lower = question.lower()
        matched_tables = []
        
        # 常见业务词汇到表名的映射
        keyword_table_map = {
            # 销售相关
            "销售": ["sales", "orders", "order", "transactions"],
            "销量": ["sales", "orders", "order", "transactions"],
            "订单": ["orders", "order", "sales"],
            "交易": ["transactions", "orders", "sales"],
            "收入": ["sales", "revenue", "orders"],
            "营收": ["sales", "revenue", "orders"],
            "金额": ["sales", "orders", "transactions"],
            
            # 访问/事件相关 - 重要！
            "访问": ["gio_event", "events", "page_view", "visits"],
            "访问量": ["gio_event", "events", "page_view", "visits"],
            "浏览": ["gio_event", "events", "page_view"],
            "点击": ["gio_event", "events", "clicks"],
            "事件": ["gio_event", "events", "event_dic"],
            "页面": ["gio_event", "page_dic", "pages"],
            "PV": ["gio_event", "page_view"],
            "UV": ["gio_event", "visitors"],
            "DAU": ["gio_event", "users", "active_users"],
            "MAU": ["gio_event", "users", "active_users"],
            "活跃": ["gio_event", "users", "active_users"],
            "日活": ["gio_event", "users"],
            "月活": ["gio_event", "users"],
            "app": ["gio_event", "apps", "applications"],
            "APP": ["gio_event", "apps", "applications"],
            "MPA": ["gio_event"],  # 企业词汇也添加映射
            
            # 渠道/来源相关
            "渠道": ["gio_event", "channels", "sources", "data_source"],
            "来源": ["gio_event", "data_source", "sources"],
            "省份": ["gio_event", "regions", "locations"],
            
            # 经销商/门店相关
            "经销商": ["dealer_store_info", "dealers"],
            "门店": ["dealer_store_info", "stores", "shops"],
            "店铺": ["dealer_store_info", "stores"],
            
            # 产品相关
            "产品": ["products", "product", "items", "goods"],
            "商品": ["products", "product", "items", "goods"],
            "货品": ["products", "product", "items", "goods"],
            
            # 客户相关
            "客户": ["customers", "customer", "users", "clients"],
            "用户": ["users", "customers", "customer", "gio_event"],
            "会员": ["members", "customers", "users"],
            
            # 区域相关
            "区域": ["regions", "area", "locations", "gio_event"],
            "地区": ["regions", "area", "locations", "gio_event"],
            "城市": ["cities", "city", "locations"],
            
            # 时间相关
            "日期": ["gio_event", "sales", "dates", "calendar"],
            "时间": ["gio_event", "sales", "dates", "calendar", "time"],
            "按日": ["gio_event", "sales"],
            "按天": ["gio_event", "sales"],
            "按月": ["gio_event", "sales"],
            
            # 库存相关
            "库存": ["inventory", "stock"],
            "仓库": ["warehouse", "inventory"],
            
            # 员工相关
            "员工": ["employees", "staff", "workers"],
            
            # 统计/分析相关 - 通用匹配
            "统计": ["gio_event", "sales"],
            "趋势": ["gio_event", "sales"],
            "分析": ["gio_event", "sales"],
        }
        
        # 检查关键词（不区分大小写）
        for keyword, possible_tables in keyword_table_map.items():
            # 同时检查原问题和小写版本，支持大写关键词如 DAU, MPA
            if keyword.lower() in question_lower or keyword in question:
                for table_pattern in possible_tables:
                    for table_name, table_info in self._table_info_cache.items():
                        if table_pattern in table_name.lower():
                            if table_name not in [t["name"] for t in matched_tables]:
                                matched_tables.append({
                                    "name": table_name,
                                    "columns": table_info["column_names"][:5],  # 只显示前5列
                                    "row_count": table_info["row_count"],
                                    "match_reason": f"包含关键词 '{keyword}'",
                                })
        
        # 检查问题中是否直接提到表名
        for table_name, table_info in self._table_info_cache.items():
            if table_name.lower() in question_lower:
                if table_name not in [t["name"] for t in matched_tables]:
                    matched_tables.append({
                        "name": table_name,
                        "columns": table_info["column_names"][:5],
                        "row_count": table_info["row_count"],
                        "match_reason": "问题中直接提及",
                    })
        
        # 检查问题中是否提到列名
        for table_name, table_info in self._table_info_cache.items():
            for col in table_info["column_names"]:
                if col.lower() in question_lower or col.replace("_", " ").lower() in question_lower:
                    if table_name not in [t["name"] for t in matched_tables]:
                        matched_tables.append({
                            "name": table_name,
                            "columns": table_info["column_names"][:5],
                            "row_count": table_info["row_count"],
                            "match_reason": f"包含字段 '{col}'",
                        })
                        break
        
        # 【智能回退】如果关键词匹配没有结果，使用 LLM 进行智能表选择
        if not matched_tables and self.llm and self._schema_description:
            logger.info(f"关键词匹配无结果，启用 LLM 智能表选择: {question}")
            llm_selected = self._llm_select_tables(question)
            if llm_selected:
                matched_tables = llm_selected
        
        return matched_tables[:5]  # 最多返回5个表
    
    def _llm_select_tables(self, question: str) -> List[Dict[str, Any]]:
        """
        使用 LLM 智能选择相关的数据表。
        
        当关键词匹配失败时，让 LLM 根据 schema 理解问题语义来选择表。
        
        【关键修复】添加超时和错误处理，避免LLM调用阻塞整个服务。
        """
        if not self.llm:
            return []
        
        prompt = self._get_table_select_prompt().format(
            schema_description=self._schema_description,
            question=question,
        )
        
        try:
            # 【关键修复】同步调用 LLM，但添加超时和错误处理
            # 注意：这个方法会在线程池中执行（由API路由层处理），所以这里保持同步即可
            response = self.llm._client.chat.completions.create(
                model=self.llm.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
                timeout=10.0,  # 10秒超时
            )
            result_text = response.choices[0].message.content or ""
            
            # 解析 JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
                selected_tables = result.get("tables", [])
                reason = result.get("reason", "LLM 智能选择")
                
                matched = []
                for table_name in selected_tables:
                    if table_name in self._table_info_cache:
                        table_info = self._table_info_cache[table_name]
                        matched.append({
                            "name": table_name,
                            "columns": table_info["column_names"][:5],
                            "row_count": table_info["row_count"],
                            "match_reason": f"🤖 AI智能选择: {reason}",
                        })
                
                if matched:
                    logger.info(f"LLM 选择了表: {[m['name'] for m in matched]}")
                return matched
                
        except Exception as e:
            # 【关键修复】LLM调用失败不应该阻塞整个服务，只记录错误并返回空列表
            logger.warning(f"LLM 表选择失败（不影响主流程）: {e}")
        
        return []
    
    def get_relevant_knowledge(self, question: str) -> List[Dict[str, Any]]:
        """
        从业务知识库检索相关知识。
        
        Returns:
            包含 time_rules, terms, mappings 的列表
        """
        knowledge_items = []
        
        if not self.knowledge_db_path:
            return knowledge_items
        
        conn = self._get_knowledge_conn()
        if not conn:
            return knowledge_items
        
        try:
            cursor = conn.cursor()
            question_lower = question.lower()
            
            # 1. 检索时间规则
            cursor.execute("SELECT * FROM time_rules ORDER BY priority DESC")
            time_rules = cursor.fetchall()
            
            for rule in time_rules:
                keyword = rule["keyword"]
                if keyword in question or keyword in question_lower:
                    try:
                        config = json.loads(rule["rule_config"])
                        # 计算实际时间范围
                        time_desc = self._compute_time_description(rule["rule_type"], config)
                        knowledge_items.append({
                            "type": "time_rule",
                            "keyword": keyword,
                            "description": rule["description"] or time_desc,
                            "value": time_desc,
                        })
                    except:
                        pass
            
            # 2. 检索业务术语
            cursor.execute("SELECT * FROM business_terms")
            terms = cursor.fetchall()
            
            for term in terms:
                term_name = term["term"]
                if term_name in question or term_name.lower() in question_lower:
                    knowledge_items.append({
                        "type": "term",
                        "keyword": term_name,
                        "description": term["definition"],
                        "value": term["sql_expression"] if term["sql_expression"] else None,
                    })
            
            # 3. 检索字段映射
            cursor.execute("SELECT * FROM field_mappings")
            mappings = cursor.fetchall()
            
            for mapping in mappings:
                display_name = mapping["display_name"]
                if display_name in question or display_name.lower() in question_lower:
                    knowledge_items.append({
                        "type": "mapping",
                        "keyword": display_name,
                        "description": f"{mapping['table_name']}.{mapping['field_name']} = '{mapping['field_value']}'",
                        "value": mapping["field_value"],
                    })
            
            conn.close()
        except Exception as e:
            logger.error(f"检索业务知识失败: {e}")
            if conn:
                conn.close()
        
        return knowledge_items
    
    def _compute_time_description(self, rule_type: str, config: Dict) -> str:
        """计算时间规则的实际描述"""
        from datetime import timedelta
        
        now = datetime.now()
        
        if rule_type == "relative":
            days = config.get("days", 0)
            target_date = now + timedelta(days=days)
            return target_date.strftime("%Y年%m月%d日")
        
        elif rule_type == "最近N天":
            days = config.get("days", 7)
            start_date = now - timedelta(days=days - 1)
            return f"{start_date.strftime('%Y-%m-%d')} 至 {now.strftime('%Y-%m-%d')}"
        
        elif rule_type == "月":
            offset = config.get("offset", 0)
            year = now.year
            month = now.month + offset
            while month <= 0:
                month += 12
                year -= 1
            while month > 12:
                month -= 12
                year += 1
            return f"{year}年{month}月"
        
        elif rule_type == "季度":
            offset = config.get("offset", 0)
            current_quarter = (now.month - 1) // 3 + 1
            target_quarter = current_quarter + offset
            year = now.year
            while target_quarter <= 0:
                target_quarter += 4
                year -= 1
            while target_quarter > 4:
                target_quarter -= 4
                year += 1
            return f"{year}年Q{target_quarter}"
        
        elif rule_type == "同环比":
            compare_type = config.get("type", "")
            type_desc = {
                "yoy": "与去年同期对比",
                "mom": "与上月对比",
                "wow": "与上周对比",
            }
            return type_desc.get(compare_type, "对比分析")
        
        return str(config)
    
    def rewrite_question(self, question: str, knowledge: List[Dict[str, Any]]) -> str:
        """
        根据业务知识改写问题，使其更清晰。
        
        这是一个简单的模板替换实现，实际可以用 LLM 来做更智能的改写。
        """
        rewritten = question
        
        # 替换时间相关的词汇
        for item in knowledge:
            if item["type"] == "time_rule":
                keyword = item["keyword"]
                value = item["value"]
                if keyword in rewritten and value:
                    # 在问题后面追加具体时间说明
                    pass  # 保持原问题，具体时间在知识中展示
        
        # 如果问题太短，补充一些上下文
        if len(rewritten) < 10:
            rewritten = f"查询{rewritten}的相关数据"
        
        return rewritten
    
    def check_feasibility(self, question: str, tables: List[Dict[str, Any]], knowledge: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        检查问题是否可以被数据库回答。
        
        Returns:
            {
                "can_answer": bool,
                "confidence": float,  # 0-1
                "reason": str,
                "suggestions": List[str],
            }
        """
        # 提取问题中的核心需求关键词
        question_lower = question.lower()
        
        # 需要数据支撑的核心业务词
        business_keywords = [
            # 销售相关
            "销量", "销售额", "销售", "收入", "营收", "利润", "成本", "金额",
            "订单", "交易", "购买", "下单",
            # 访问/事件相关
            "访问", "访问量", "浏览", "点击", "事件", "页面",
            "PV", "UV", "DAU", "MAU",
            # 产品相关
            "产品", "商品", "货品", "SKU",
            # 客户/用户相关
            "客户", "用户", "会员", "顾客",
            # 库存相关
            "库存", "仓储", "出入库",
            # 人员相关
            "员工", "绩效", "提成",
            # 区域/渠道相关
            "区域", "门店", "渠道", "来源", "省份", "地区",
            # 经销商相关
            "经销商", "店铺",
        ]
        
        # 检测问题中包含哪些业务关键词
        found_keywords = [kw for kw in business_keywords if kw in question_lower]
        
        # 计算置信度
        confidence = 0.0
        reasons = []
        suggestions = []
        
        # 1. 如果有匹配的表，基础置信度 +0.5
        if tables:
            # 检查匹配的表是否真的相关（不是"候选表"）
            real_matches = [t for t in tables if t.get("match_reason") != "候选表"]
            if real_matches:
                confidence += 0.5
                reasons.append(f"找到 {len(real_matches)} 个相关数据表")
            else:
                reasons.append("没有找到与问题直接相关的数据表")
                suggestions.append("当前数据库可能不包含相关业务数据")
        else:
            reasons.append("没有找到任何匹配的数据表")
            suggestions.append("请检查数据库中是否有相关业务表")
        
        # 2. 如果有匹配的业务知识，置信度 +0.2
        if knowledge:
            confidence += 0.2
            reasons.append(f"参考了 {len(knowledge)} 条业务知识")
        
        # 3. 检查问题中的关键词是否能映射到表/字段
        if found_keywords:
            matched_count = 0
            unmatched_keywords = []
            
            for kw in found_keywords:
                # 检查这个关键词是否在某个表的匹配原因中
                kw_matched = False
                for table in tables:
                    if kw in table.get("match_reason", ""):
                        kw_matched = True
                        break
                
                if kw_matched:
                    matched_count += 1
                else:
                    unmatched_keywords.append(kw)
            
            if matched_count > 0:
                confidence += 0.3 * (matched_count / len(found_keywords))
            
            if unmatched_keywords:
                reasons.append(f"以下关键词未找到对应数据: {', '.join(unmatched_keywords)}")
                suggestions.append(f"数据库中可能缺少 {', '.join(unmatched_keywords)} 相关的表或字段")
        
        # 判断是否可以回答
        can_answer = confidence >= 0.3 and len(tables) > 0
        
        # 如果不能回答，生成友好的提示
        if not can_answer:
            if not tables:
                suggestions.insert(0, "建议先了解数据库中有哪些数据表")
            suggestions.append("您可以尝试询问数据库中现有的数据，如：'数据库有哪些表？'")
        
        return {
            "can_answer": can_answer,
            "confidence": round(confidence, 2),
            "reason": "；".join(reasons) if reasons else "分析完成",
            "suggestions": suggestions,
        }
    
    def get_available_capabilities(self) -> Dict[str, Any]:
        """
        获取当前数据库可以回答的问题类型。
        
        用于在无法回答时提示用户可以问什么。
        """
        capabilities = []
        
        # 分析每个表能回答什么问题
        for table_name, table_info in self._table_info_cache.items():
            columns = table_info["column_names"]
            table_desc = {
                "table": table_name,
                "can_query": [],
            }
            
            # 简单的列名到能力的映射
            capability_patterns = {
                "时间分析": ["date", "time", "created", "updated", "timestamp"],
                "数量统计": ["count", "quantity", "amount", "num"],
                "金额分析": ["price", "cost", "revenue", "profit", "amount", "total"],
                "分类统计": ["type", "category", "status", "level"],
                "用户分析": ["user", "customer", "member"],
                "地区分析": ["region", "city", "area", "location", "country"],
            }
            
            for cap_name, patterns in capability_patterns.items():
                for col in columns:
                    if any(p in col.lower() for p in patterns):
                        if cap_name not in table_desc["can_query"]:
                            table_desc["can_query"].append(cap_name)
                        break
            
            if table_desc["can_query"]:
                capabilities.append(table_desc)
        
        return {
            "tables_count": len(self._table_info_cache),
            "capabilities": capabilities,
        }

    def semantic_tokenize(self, question: str) -> List[Dict[str, Any]]:
        """
        语义分词：将用户问题拆解为语义块，并标注每个块的类型。
        
        类似喜马拉雅的"问数语义拆解"效果：
        "本周小说频道的专辑DAU趋势如何？环比？"
        →
        [
            {"text": "本周", "type": "time_rule", "knowledge": {...}},
            {"text": "小说频道", "type": "field_mapping", "knowledge": {...}},
            {"text": "专辑", "type": "term", "knowledge": {...}},
            {"text": "DAU趋势如何", "type": "chart_hint", "knowledge": {...}},
            {"text": "环比", "type": "comparison", "knowledge": {...}},
        ]
        """
        tokens = []
        remaining_text = question
        matched_positions = []  # 记录已匹配的位置，避免重复
        
        # 获取所有知识项
        conn = self._get_knowledge_conn()
        time_rules = []
        business_terms = []
        field_mappings = []
        
        if conn:
            try:
                cursor = conn.cursor()
                
                # 获取时间规则（按长度降序，优先匹配长的）
                cursor.execute("SELECT * FROM time_rules ORDER BY LENGTH(keyword) DESC")
                time_rules = [dict(row) for row in cursor.fetchall()]
                
                # 获取业务术语
                cursor.execute("SELECT * FROM business_terms ORDER BY LENGTH(term) DESC")
                business_terms = [dict(row) for row in cursor.fetchall()]
                
                # 获取字段映射
                cursor.execute("SELECT * FROM field_mappings ORDER BY LENGTH(display_name) DESC")
                field_mappings = [dict(row) for row in cursor.fetchall()]
                
                conn.close()
            except Exception as e:
                logger.error(f"获取知识库数据失败: {e}")
                if conn:
                    conn.close()
        
        # 图表类型关键词（复合词优先匹配，放在前面）
        chart_keywords = {
            # 复合词（优先匹配）
            "变化趋势": {"type": "line", "label": "折线图"},
            "趋势变化": {"type": "line", "label": "折线图"},
            "走势变化": {"type": "line", "label": "折线图"},
            "趋势走势": {"type": "line", "label": "折线图"},
            "分布情况": {"type": "pie", "label": "饼图"},
            "占比分布": {"type": "pie", "label": "饼图"},
            "分布占比": {"type": "pie", "label": "饼图"},
            "排名对比": {"type": "bar", "label": "柱状图"},
            "对比排名": {"type": "bar", "label": "柱状图"},
            # 单个词（后匹配）
            "趋势": {"type": "line", "label": "折线图"},
            "走势": {"type": "line", "label": "折线图"},
            "变化": {"type": "line", "label": "折线图"},
            "如何": {"type": "line", "label": "趋势分析"},
            "怎么样": {"type": "line", "label": "趋势分析"},
            "怎样": {"type": "line", "label": "趋势分析"},
            "对比": {"type": "bar", "label": "柱状图"},
            "比较": {"type": "bar", "label": "柱状图"},
            "排名": {"type": "bar", "label": "柱状图"},
            "排行": {"type": "bar", "label": "柱状图"},
            "Top": {"type": "bar", "label": "柱状图"},
            "top": {"type": "bar", "label": "柱状图"},
            "占比": {"type": "pie", "label": "饼图"},
            "分布": {"type": "pie", "label": "饼图"},
            "构成": {"type": "pie", "label": "饼图"},
            "比例": {"type": "pie", "label": "饼图"},
        }
        
        # 时间相关关键词（补充数据库中没有的）
        time_keywords = {
            "最近": {"label": "近期时间", "value": "recent"},
            "近期": {"label": "近期时间", "value": "recent"},
            "过去": {"label": "过去时间", "value": "past"},
            "历史": {"label": "历史数据", "value": "historical"},
        }
        
        # 同环比关键词
        comparison_keywords = {
            "环比": {"type": "mom", "label": "与上期对比"},
            "同比": {"type": "yoy", "label": "与同期对比"},
            "周环比": {"type": "wow", "label": "与上周对比"},
            "月环比": {"type": "mom", "label": "与上月对比"},
            "年同比": {"type": "yoy", "label": "与去年同期对比"},
        }
        
        # 1. 匹配时间规则
        for rule in time_rules:
            keyword = rule["keyword"]
            if keyword in question:
                start_idx = question.find(keyword)
                end_idx = start_idx + len(keyword)
                
                # 检查是否已被其他token覆盖
                if not self._is_position_matched(start_idx, end_idx, matched_positions):
                    try:
                        config = json.loads(rule["rule_config"])
                        time_desc = self._compute_time_description(rule["rule_type"], config)
                    except:
                        time_desc = rule["description"]
                    
                    tokens.append({
                        "text": keyword,
                        "type": "time_rule",
                        "type_label": "时间语义规则",
                        "start": start_idx,
                        "end": end_idx,
                        "knowledge": {
                            "description": rule["description"],
                            "value": time_desc,
                        },
                    })
                    matched_positions.append((start_idx, end_idx))
        
        # 1.5 匹配补充的时间关键词（数据库中没有的）
        for keyword, info in time_keywords.items():
            if keyword in question:
                start_idx = question.find(keyword)
                end_idx = start_idx + len(keyword)
                
                if not self._is_position_matched(start_idx, end_idx, matched_positions):
                    tokens.append({
                        "text": keyword,
                        "type": "time_rule",
                        "type_label": "时间语义规则",
                        "start": start_idx,
                        "end": end_idx,
                        "knowledge": {
                            "description": info["label"],
                            "value": info["value"],
                        },
                    })
                    matched_positions.append((start_idx, end_idx))
        
        # 1.6 使用正则表达式匹配复杂时间表达式（更全面的拆分）
        # 时间表达式模式（按长度降序，优先匹配长的）
        time_patterns = [
            (r"最近\d+[天周月年]", "最近N天/周/月/年", "time_rule"),
            (r"近\d+[天周月年]", "近N天/周/月/年", "time_rule"),
            (r"过去\d+[天周月年]", "过去N天/周/月/年", "time_rule"),
            (r"前\d+[天周月年]", "前N天/周/月/年", "time_rule"),
            (r"最近\d+日", "最近N日", "time_rule"),
            (r"近\d+日", "近N日", "time_rule"),
            (r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?", "具体日期", "time_rule"),
            (r"\d{4}[-/年]\d{1,2}[月]?", "年月", "time_rule"),
            (r"今[天日]", "今天", "time_rule"),
            (r"昨[天日]", "昨天", "time_rule"),
            (r"前[天日]", "前天", "time_rule"),
            (r"本[周月季年]", "本周/月/季/年", "time_rule"),
            (r"上[周月季年]", "上周/月/季/年", "time_rule"),
            (r"去[年月]", "去年/月", "time_rule"),
        ]
        
        for pattern, label, token_type in time_patterns:
            matches = re.finditer(pattern, question)
            for match in matches:
                start_idx = match.start()
                end_idx = match.end()
                matched_text = match.group()
                
                if not self._is_position_matched(start_idx, end_idx, matched_positions):
                    tokens.append({
                        "text": matched_text,
                        "type": token_type,
                        "type_label": "时间语义规则",
                        "start": start_idx,
                        "end": end_idx,
                        "knowledge": {
                            "description": label,
                            "value": matched_text,
                        },
                    })
                    matched_positions.append((start_idx, end_idx))
        
        # 1.7 匹配统计模式（"按...统计"、"按...分组"等，以及英文"by day"、"group by"等）
        stat_patterns = [
            # 中文模式
            (r"按(.+?)统计", "按维度统计", "dimension"),
            (r"按(.+?)分组", "按维度分组", "dimension"),
            (r"按(.+?)聚合", "按维度聚合", "dimension"),
            (r"按(.+?)汇总", "按维度汇总", "dimension"),
            (r"按(.+?)分类", "按维度分类", "dimension"),
            # 英文模式 - 需要更精确的匹配，避免误匹配
            (r"\bgroup\s+by\s+(\w+)\b", "按维度分组", "dimension"),  # "group by day"
            (r"\bby\s+(day|date|month|year|week|hour|minute)\b", "按维度分组", "dimension"),  # "by day", "by date" 等时间维度
        ]
        
        for pattern, label, token_type in stat_patterns:
            matches = re.finditer(pattern, question)
            for match in matches:
                # 匹配整个"按...统计"模式
                full_match_start = match.start()
                full_match_end = match.end()
                full_text = match.group(0)  # 整个匹配，如"按日期统计"
                dimension_text = match.group(1)  # 维度部分，如"日期"
                
                if not self._is_position_matched(full_match_start, full_match_end, matched_positions):
                    # 先标记整个模式，避免被其他规则覆盖
                    matched_positions.append((full_match_start, full_match_end))
                    
                    # 如果维度部分没有被其他规则匹配，单独标记维度
                    dim_start = match.start(1)
                    dim_end = match.end(1)
                    if not self._is_position_matched(dim_start, dim_end, matched_positions):
                        tokens.append({
                            "text": dimension_text,
                            "type": "dimension",
                            "type_label": "分析维度",
                            "start": dim_start,
                            "end": dim_end,
                            "knowledge": {
                                "description": f"{label}：{dimension_text}",
                                "value": dimension_text,
                            },
                        })
                        matched_positions.append((dim_start, dim_end))
        
        # 1.8 匹配数字+单位的时间表达式（如"7天"、"30天"），但排除已经被匹配的
        number_time_pattern = r"(\d+)([天日周月年])"
        matches = re.finditer(number_time_pattern, question)
        for match in matches:
            start_idx = match.start()
            end_idx = match.end()
            matched_text = match.group(0)  # 如"7天"
            number = match.group(1)  # 如"7"
            unit = match.group(2)  # 如"天"
            
            # 检查前面是否有"最近"、"近"等词（避免重复匹配）
            prev_start = max(0, start_idx - 2)
            prev_text = question[prev_start:start_idx]
            if prev_text not in ["最近", "近", "过去", "前"]:
                if not self._is_position_matched(start_idx, end_idx, matched_positions):
                    tokens.append({
                        "text": matched_text,
                        "type": "time_rule",
                        "type_label": "时间语义规则",
                        "start": start_idx,
                        "end": end_idx,
                        "knowledge": {
                            "description": f"{number}{unit}",
                            "value": matched_text,
                        },
                    })
                    matched_positions.append((start_idx, end_idx))
        
        # 2. 匹配同环比关键词
        for keyword, info in comparison_keywords.items():
            if keyword in question:
                start_idx = question.find(keyword)
                end_idx = start_idx + len(keyword)
                
                if not self._is_position_matched(start_idx, end_idx, matched_positions):
                    tokens.append({
                        "text": keyword,
                        "type": "comparison",
                        "type_label": "同环比语义规则",
                        "start": start_idx,
                        "end": end_idx,
                        "knowledge": {
                            "description": info["label"],
                            "value": info["type"],
                        },
                    })
                    matched_positions.append((start_idx, end_idx))
        
        # 3. 匹配业务术语
        for term in business_terms:
            term_name = term["term"]
            if term_name in question:
                start_idx = question.find(term_name)
                end_idx = start_idx + len(term_name)
                
                if not self._is_position_matched(start_idx, end_idx, matched_positions):
                    tokens.append({
                        "text": term_name,
                        "type": "term",
                        "type_label": "企业词汇知识",
                        "start": start_idx,
                        "end": end_idx,
                        "knowledge": {
                            "description": term["definition"],
                            "value": term.get("sql_expression"),
                        },
                    })
                    matched_positions.append((start_idx, end_idx))
        
        # 4. 匹配字段映射
        for mapping in field_mappings:
            display_name = mapping["display_name"]
            if display_name in question:
                start_idx = question.find(display_name)
                end_idx = start_idx + len(display_name)
                
                if not self._is_position_matched(start_idx, end_idx, matched_positions):
                    tokens.append({
                        "text": display_name,
                        "type": "field_mapping",
                        "type_label": "字段枚举知识",
                        "start": start_idx,
                        "end": end_idx,
                        "knowledge": {
                            "description": f"{mapping['table_name']}.{mapping['field_name']} = '{mapping['field_value']}'",
                            "value": mapping["field_value"],
                        },
                    })
                    matched_positions.append((start_idx, end_idx))
        
        # 5. 匹配图表类型关键词（按长度降序，优先匹配长的复合词）
        # 先按长度降序排序，确保复合词优先匹配
        sorted_chart_keywords = sorted(chart_keywords.items(), key=lambda x: len(x[0]), reverse=True)
        for keyword, info in sorted_chart_keywords:
            # 使用 finditer 找到所有匹配位置，避免只匹配第一个
            start_idx = question.find(keyword)
            while start_idx >= 0:
                end_idx = start_idx + len(keyword)
                
                if not self._is_position_matched(start_idx, end_idx, matched_positions):
                    tokens.append({
                        "text": keyword,
                        "type": "chart_hint",
                        "type_label": "自动图表展示",
                        "start": start_idx,
                        "end": end_idx,
                        "knowledge": {
                            "description": info["label"],
                            "value": info["type"],
                        },
                    })
                    matched_positions.append((start_idx, end_idx))
                    break  # 找到一个匹配就跳出，避免重复
                
                # 继续查找下一个匹配位置
                start_idx = question.find(keyword, start_idx + 1)
        
        # 6. 检测指标关键词（常见数据指标）- 支持大小写不敏感匹配
        metric_keywords = {
            "销量": "数量指标",
            "销售额": "金额指标",
            "收入": "金额指标",
            "营收": "金额指标",
            "利润": "金额指标",
            "金额": "金额指标",
            "订单": "数量指标",
            "订单数": "数量指标",
            "用户数": "数量指标",
            "访问量": "访问次数",
            "浏览量": "浏览次数",
            "点击量": "点击次数",
            "dau": "日活跃用户",
            "mau": "月活跃用户",
            "uv": "独立访客",
            "pv": "页面浏览量",
            "gmv": "成交总额",
            "转化率": "比率指标",
            "点击率": "比率指标",
            "跳出率": "比率指标",
            "日活": "日活跃用户",
            "月活": "月活跃用户",
        }
        
        question_lower = question.lower()
        for keyword, desc in metric_keywords.items():
            keyword_lower = keyword.lower()
            # 不区分大小写匹配
            if keyword_lower in question_lower:
                # 找到原问题中的实际位置（保持原始大小写）
                idx = question_lower.find(keyword_lower)
                if idx >= 0:
                    start_idx = idx
                    end_idx = start_idx + len(keyword)
                    original_text = question[start_idx:end_idx]  # 保留原始大小写
                    
                    if not self._is_position_matched(start_idx, end_idx, matched_positions):
                        tokens.append({
                            "text": original_text,
                            "type": "metric",
                            "type_label": "指标",
                            "start": start_idx,
                            "end": end_idx,
                            "knowledge": {
                                "description": desc,
                                "value": keyword.upper() if keyword.isascii() else keyword,
                            },
                        })
                        matched_positions.append((start_idx, end_idx))
        
        # 7. 检测排序语义关键词（按长度降序，优先匹配长的复合词）- 放在维度之前，避免被覆盖
        sort_keywords = {
            "最高的": {"type": "desc", "label": "降序排序"},
            "最高": {"type": "desc", "label": "降序排序"},
            "最大的": {"type": "desc", "label": "降序排序"},
            "最大": {"type": "desc", "label": "降序排序"},
            "最多的": {"type": "desc", "label": "降序排序"},
            "最多": {"type": "desc", "label": "降序排序"},
            "最低的": {"type": "asc", "label": "升序排序"},
            "最低": {"type": "asc", "label": "升序排序"},
            "最小的": {"type": "asc", "label": "升序排序"},
            "最小": {"type": "asc", "label": "升序排序"},
            "最少的": {"type": "asc", "label": "升序排序"},
            "最少": {"type": "asc", "label": "升序排序"},
            "排名": {"type": "desc", "label": "排名排序"},
            "排行": {"type": "desc", "label": "排名排序"},
            "Top": {"type": "desc", "label": "Top N排序"},
            "top": {"type": "desc", "label": "Top N排序"},
            "前": {"type": "desc", "label": "前N名"},
        }
        
        # 按长度降序排序，确保复合词优先匹配
        sorted_sort_keywords = sorted(sort_keywords.items(), key=lambda x: len(x[0]), reverse=True)
        question_lower = question.lower()
        for keyword, info in sorted_sort_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in question_lower:
                idx = question_lower.find(keyword_lower)
                if idx >= 0:
                    start_idx = idx
                    end_idx = start_idx + len(keyword)
                    original_text = question[start_idx:end_idx]  # 保留原始大小写
                    
                    if not self._is_position_matched(start_idx, end_idx, matched_positions):
                        tokens.append({
                            "text": original_text,
                            "type": "sort",
                            "type_label": "排序语义",
                            "start": start_idx,
                            "end": end_idx,
                            "knowledge": {
                                "description": info["label"],
                                "value": info["type"],
                            },
                        })
                        matched_positions.append((start_idx, end_idx))
                        break  # 找到一个匹配就跳出，避免重复
        
        # 8. 检测维度关键词（分析维度）- 放在排序关键词之后
        dimension_keywords = {
            "渠道": "流量来源维度",
            "来源": "流量来源维度",
            "城市": "地理维度",
            "地区": "地理维度",
            "省份": "地理维度",
            "区域": "地理维度",
            "经销商": "业务实体维度",
            "门店": "业务实体维度",
            "店铺": "业务实体维度",
            "品牌": "产品维度",
            "品类": "产品维度",
            "商品": "产品维度",
            "产品": "产品维度",
            "用户": "用户维度",
            "客户": "用户维度",
            "会员": "用户维度",
            "时间": "时间维度",
            "日期": "时间维度",
            "月份": "时间维度",
            "年份": "时间维度",
            "周": "时间维度",
            "季度": "时间维度",
            "页面": "行为维度",
            "事件": "行为维度",
            "设备": "设备维度",
            "平台": "平台维度",
        }
        
        for keyword, desc in dimension_keywords.items():
            if keyword in question:
                start_idx = question.find(keyword)
                end_idx = start_idx + len(keyword)
                
                if not self._is_position_matched(start_idx, end_idx, matched_positions):
                    tokens.append({
                        "text": keyword,
                        "type": "dimension",
                        "type_label": "分析维度",
                        "start": start_idx,
                        "end": end_idx,
                        "knowledge": {
                            "description": desc,
                            "value": keyword,
                        },
                    })
                    matched_positions.append((start_idx, end_idx))
        
        # 按位置排序
        tokens.sort(key=lambda x: x["start"])
        
        return tokens
    
    def _is_position_matched(self, start: int, end: int, matched_positions: List[Tuple[int, int]]) -> bool:
        """检查位置是否已被匹配"""
        for ms, me in matched_positions:
            # 如果有重叠
            if not (end <= ms or start >= me):
                return True
        return False

    def analyze(self, question: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        完整分析一个查询问题。
        
        Args:
            question: 用户问题
            use_cache: 是否使用缓存
        
        Returns:
            {
                "original_question": str,
                "rewritten_question": str,
                "selected_tables": List[Dict],
                "relevant_knowledge": List[Dict],
                "semantic_tokens": List[Dict],  # 新增：语义分词结果
                "analysis_time": str,
                "feasibility": Dict,
            }
        """
        # 检查缓存
        if use_cache:
            question_key = question.strip().lower()
            if question_key in self._analysis_cache:
                logger.debug(f"使用缓存的分析结果: {question[:50]}...")
                return self._analysis_cache[question_key]
        
        # 1. 语义分词
        semantic_tokens = self.semantic_tokenize(question)
        
        # 2. 检索相关业务知识
        knowledge = self.get_relevant_knowledge(question)
        
        # 3. 分析可能涉及的表
        tables = self.analyze_tables(question)
        
        # 4. 检查可行性
        feasibility = self.check_feasibility(question, tables, knowledge)
        
        # 5. 改写问题
        rewritten = self.rewrite_question(question, knowledge)
        
        result = {
            "original_question": question,
            "rewritten_question": rewritten,
            "selected_tables": tables,
            "relevant_knowledge": knowledge,
            "semantic_tokens": semantic_tokens,
            "feasibility": feasibility,
            "analysis_time": datetime.now().isoformat(),
        }
        
        # 更新缓存
        if use_cache:
            question_key = question.strip().lower()
            # 如果缓存已满，删除最旧的条目（FIFO）
            if len(self._analysis_cache) >= self._cache_max_size:
                oldest_key = next(iter(self._analysis_cache))
                del self._analysis_cache[oldest_key]
            self._analysis_cache[question_key] = result
        
        return result
    
    def clear_cache(self):
        """清空分析结果缓存"""
        self._analysis_cache.clear()
        logger.info("已清空分析结果缓存")


# 全局单例
_query_analyzer: Optional[QueryAnalyzer] = None


def get_query_analyzer() -> Optional[QueryAnalyzer]:
    """获取查询分析器单例"""
    return _query_analyzer


def init_query_analyzer(
    data_db_path: Path,
    knowledge_db_path: Optional[Path] = None,
    llm_service = None,
    prompt_manager = None,
) -> QueryAnalyzer:
    """初始化查询分析器"""
    global _query_analyzer
    _query_analyzer = QueryAnalyzer(
        data_db_path=data_db_path,
        knowledge_db_path=knowledge_db_path,
        llm_service=llm_service,
        prompt_manager=prompt_manager,
    )
    return _query_analyzer

