"""
多轮澄清服务。

提供：
- 问题清晰度判断
- 澄清问题生成
- 用户补充信息处理
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ClarificationType(str, Enum):
    """澄清类型"""
    TIME_AMBIGUOUS = "time_ambiguous"
    METRIC_AMBIGUOUS = "metric_ambiguous"
    DIMENSION_AMBIGUOUS = "dimension_ambiguous"
    SCOPE_AMBIGUOUS = "scope_ambiguous"
    AGGREGATION_AMBIGUOUS = "aggregation_ambiguous"
    COMPARISON_AMBIGUOUS = "comparison_ambiguous"


@dataclass
class ClarificationIssue:
    """澄清问题"""
    type: ClarificationType
    description: str
    question: str
    options: List[str] = field(default_factory=list)
    default_option: Optional[str] = None


@dataclass
class ClarificationResult:
    """澄清结果"""
    is_clear: bool
    confidence: float
    issues: List[ClarificationIssue] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    enhanced_question: Optional[str] = None


class ClarificationService:
    """多轮澄清服务"""
    
    AMBIGUOUS_TIME_WORDS = [
        "最近", "近期", "之前", "以前", "过去", "一段时间",
        "这段时间", "那段时间", "前阵子", "刚才", "最新",
    ]
    
    CLEAR_TIME_PATTERNS = [
        r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?",
        r"\d{4}[-/年]\d{1,2}[月]?",
        r"今[天日]", r"昨[天日]", r"前[天日]",
        r"本[周月季年]", r"上[周月季年]", r"去年",
        r"最近\d+[天周月年]", r"近\d+[天周月年]",
        r"过去\d+[天周月年]",
    ]
    
    AMBIGUOUS_METRIC_WORDS = [
        "数据", "情况", "表现", "效果", "结果", "指标", "数字",
    ]
    
    AMBIGUOUS_SCOPE_WORDS = [
        "所有", "全部", "整体", "总体", "大概", "大约", "差不多",
    ]
    
    COMPARISON_WORDS = [
        "比较", "对比", "比", "vs", "VS", "和...相比", "与...相比",
        "更高", "更低", "更多", "更少", "变化", "增长", "下降",
    ]
    
    def __init__(self, business_knowledge=None):
        self.business_knowledge = business_knowledge
    
    def analyze(self, question: str, context: Optional[Dict[str, Any]] = None) -> ClarificationResult:
        """分析问题清晰度"""
        issues = []
        suggestions = []
        
        time_issue = self._check_time_clarity(question)
        if time_issue:
            issues.append(time_issue)
        
        metric_issue = self._check_metric_clarity(question, context)
        if metric_issue:
            issues.append(metric_issue)
        
        dimension_issue = self._check_dimension_clarity(question, context)
        if dimension_issue:
            issues.append(dimension_issue)
        
        scope_issue = self._check_scope_clarity(question, context)
        if scope_issue:
            issues.append(scope_issue)
        
        aggregation_issue = self._check_aggregation_clarity(question)
        if aggregation_issue:
            issues.append(aggregation_issue)
        
        comparison_issue = self._check_comparison_clarity(question)
        if comparison_issue:
            issues.append(comparison_issue)
        
        confidence = self._calculate_confidence(question, issues)
        is_clear = len(issues) == 0 or confidence >= 0.7
        
        if not is_clear:
            suggestions = self._generate_suggestions(question, issues)
        
        return ClarificationResult(
            is_clear=is_clear,
            confidence=confidence,
            issues=issues,
            suggestions=suggestions,
        )
    
    def _check_time_clarity(self, question: str) -> Optional[ClarificationIssue]:
        """检查时间表达清晰度"""
        for pattern in self.CLEAR_TIME_PATTERNS:
            if re.search(pattern, question):
                return None
        
        for word in self.AMBIGUOUS_TIME_WORDS:
            if word in question:
                return ClarificationIssue(
                    type=ClarificationType.TIME_AMBIGUOUS,
                    description=f"时间表达「{word}」不够明确",
                    question=f"请问「{word}」具体是指哪个时间范围？",
                    options=[
                        "今天", "最近7天", "最近30天",
                        "本月", "上月", "本季度", "自定义时间范围",
                    ],
                    default_option="最近7天",
                )
        return None
    
    def _check_metric_clarity(
        self, question: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[ClarificationIssue]:
        """检查指标清晰度"""
        for word in self.AMBIGUOUS_METRIC_WORDS:
            if word in question:
                specific_metrics = context.get("available_metrics", []) if context else []
                has_specific = any(m.lower() in question.lower() for m in specific_metrics)
                
                if not has_specific:
                    return ClarificationIssue(
                        type=ClarificationType.METRIC_AMBIGUOUS,
                        description=f"「{word}」不够具体，需要明确查看哪些指标",
                        question="您想查看哪些具体指标？",
                        options=specific_metrics[:5] if specific_metrics else [
                            "销售额", "订单数", "用户数", "转化率", "其他",
                        ],
                    )
        return None
    
    def _check_dimension_clarity(
        self, question: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[ClarificationIssue]:
        """检查维度/分组清晰度"""
        group_patterns = [r"按(.+?)分[组类]", r"分[组类]统计", r"各(.+?)的"]
        
        for pattern in group_patterns:
            if re.search(pattern, question):
                return None
        
        summary_words = ["汇总", "统计", "分析", "趋势", "分布"]
        if any(word in question for word in summary_words):
            available_dims = context.get("available_dimensions", []) if context else []
            
            if available_dims:
                return ClarificationIssue(
                    type=ClarificationType.DIMENSION_AMBIGUOUS,
                    description="需要明确数据的分组/分析维度",
                    question="您希望按什么维度进行分析？",
                    options=available_dims[:5] + ["不分组，查看总数"],
                )
        return None
    
    def _check_scope_clarity(
        self, question: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[ClarificationIssue]:
        """检查范围清晰度"""
        for word in self.AMBIGUOUS_SCOPE_WORDS:
            if word in question:
                filter_patterns = [
                    r"[只仅].*?的", r"筛选", r"条件[是为]",
                    r"[>=<]", r"大于", r"小于", r"等于",
                ]
                has_filter = any(re.search(p, question) for p in filter_patterns)
                
                if not has_filter:
                    return ClarificationIssue(
                        type=ClarificationType.SCOPE_AMBIGUOUS,
                        description=f"「{word}」范围可能过大，是否需要添加筛选条件？",
                        question="是否需要限定数据范围？",
                        options=[
                            "查看全部数据", "只看特定区域", "只看特定产品",
                            "只看特定用户群", "添加其他筛选条件",
                        ],
                    )
        return None
    
    def _check_aggregation_clarity(self, question: str) -> Optional[ClarificationIssue]:
        """检查聚合方式清晰度"""
        value_words = ["销售额", "金额", "数量", "价格", "成本", "利润"]
        agg_words = ["总", "平均", "最大", "最小", "求和", "均值", "合计"]
        
        has_value = any(word in question for word in value_words)
        has_agg = any(word in question for word in agg_words)
        
        if has_value and not has_agg:
            count_patterns = [r"多少", r"有几", r"共\d*个?"]
            if any(re.search(p, question) for p in count_patterns):
                return None
            
            return ClarificationIssue(
                type=ClarificationType.AGGREGATION_AMBIGUOUS,
                description="需要明确数据的聚合方式",
                question="您需要的是？",
                options=[
                    "总和（累计值）", "平均值", "最大值", "最小值", "计数（数量）",
                ],
                default_option="总和（累计值）",
            )
        return None
    
    def _check_comparison_clarity(self, question: str) -> Optional[ClarificationIssue]:
        """检查比较对象清晰度"""
        has_comparison = any(word in question for word in self.COMPARISON_WORDS)
        
        if has_comparison:
            compare_patterns = [
                r"和(.+?)比", r"与(.+?)比", r"比(.+?)[的更]",
                r"环比", r"同比", r"日环比", r"周环比", r"月环比",
            ]
            has_clear_target = any(re.search(p, question) for p in compare_patterns)
            
            if not has_clear_target:
                return ClarificationIssue(
                    type=ClarificationType.COMPARISON_AMBIGUOUS,
                    description="需要明确比较对象",
                    question="您想和什么进行比较？",
                    options=[
                        "环比（与上一周期比）", "同比（与去年同期比）",
                        "与目标值比较", "不同维度之间比较", "不需要比较",
                    ],
                )
        return None
    
    def _calculate_confidence(self, question: str, issues: List[ClarificationIssue]) -> float:
        """计算问题清晰度置信度"""
        base_confidence = 0.8
        length_bonus = min(len(question) / 50, 0.1)
        issue_penalty = len(issues) * 0.15
        has_numbers = bool(re.search(r'\d+', question))
        number_bonus = 0.05 if has_numbers else 0
        
        confidence = base_confidence + length_bonus + number_bonus - issue_penalty
        return max(0.0, min(1.0, confidence))
    
    def _generate_suggestions(
        self, question: str, issues: List[ClarificationIssue]
    ) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        for issue in issues:
            if issue.type == ClarificationType.TIME_AMBIGUOUS:
                suggestions.append('建议明确时间范围，如"最近7天"、"本月"、"2024年1月"等')
            elif issue.type == ClarificationType.METRIC_AMBIGUOUS:
                suggestions.append('建议指定具体指标，如"销售额"、"订单数"、"用户数"等')
            elif issue.type == ClarificationType.DIMENSION_AMBIGUOUS:
                suggestions.append('建议明确分析维度，如"按区域"、"按产品类别"、"按月份"等')
            elif issue.type == ClarificationType.SCOPE_AMBIGUOUS:
                suggestions.append('建议添加筛选条件，缩小数据范围')
            elif issue.type == ClarificationType.AGGREGATION_AMBIGUOUS:
                suggestions.append('建议明确聚合方式，如"总和"、"平均值"、"最大值"等')
            elif issue.type == ClarificationType.COMPARISON_AMBIGUOUS:
                suggestions.append('建议明确比较对象，如"环比"、"同比"或具体的比较项')
        
        return suggestions
    
    def enhance_question(
        self, original_question: str, clarifications: Dict[str, Any]
    ) -> str:
        """根据用户的澄清回答增强问题"""
        enhanced = original_question
        
        if "time_range" in clarifications:
            enhanced = f"{enhanced}，时间范围：{clarifications['time_range']}"
        
        if "metrics" in clarifications:
            metrics = clarifications["metrics"]
            if isinstance(metrics, list):
                metrics = "、".join(metrics)
            enhanced = f"{enhanced}，查看指标：{metrics}"
        
        if "dimensions" in clarifications:
            dimensions = clarifications["dimensions"]
            if isinstance(dimensions, list):
                dimensions = "、".join(dimensions)
            enhanced = f"{enhanced}，按{dimensions}分组"
        
        if "aggregation" in clarifications:
            enhanced = f"{enhanced}，计算{clarifications['aggregation']}"
        
        if "comparison" in clarifications:
            enhanced = f"{enhanced}，{clarifications['comparison']}"
        
        return enhanced
    
    def get_clarification_prompt(self, issues: List[ClarificationIssue]) -> str:
        """生成澄清提示语"""
        if not issues:
            return ""
        
        prompt_parts = ["为了更准确地回答您的问题，我需要确认以下信息：\n"]
        
        for i, issue in enumerate(issues, 1):
            prompt_parts.append(f"{i}. {issue.question}")
            if issue.options:
                options_str = " / ".join(issue.options[:5])
                prompt_parts.append(f"   可选：{options_str}")
            prompt_parts.append("")
        
        return "\n".join(prompt_parts)


def check_question_clarity(
    question: str, context: Optional[Dict[str, Any]] = None
) -> ClarificationResult:
    """检查问题清晰度"""
    service = ClarificationService()
    return service.analyze(question, context)

