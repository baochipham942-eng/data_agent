"""
增强版评测体系。

基于火山引擎 Data Agent 评测体系设计，提供：
1. 多维度评测指标
2. 分析与洞察维度
3. 可视化呈现维度
4. 鲁棒性维度
5. 自动化评测流程
"""

import json
import asyncio
import sqlite3
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class EvaluationLevel(Enum):
    """评测等级"""
    PASS = "pass"  # 达标级
    INDUSTRIAL = "industrial"  # 工业可用级
    PROFESSIONAL = "professional"  # 专业研究级


@dataclass
class DimensionScore:
    """单维度评分"""
    name: str  # 维度名称
    score: float  # 得分 (0-5)
    max_score: float = 5.0
    weight: float = 1.0  # 权重
    reasoning: str = ""  # 评分理由
    sub_scores: Dict[str, float] = field(default_factory=dict)  # 子项评分


@dataclass
class EnhancedEvaluationResult:
    """增强版评测结果"""
    conversation_id: str
    
    # 维度1: 分析与洞察
    analysis_insight: DimensionScore = None
    
    # 维度2: 可视化呈现
    visualization: DimensionScore = None
    
    # 维度3: 鲁棒性
    robustness: DimensionScore = None
    
    # 综合评分
    overall_score: float = 0.0
    evaluation_level: EvaluationLevel = EvaluationLevel.PASS
    
    # 元数据
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    evaluated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def calculate_overall(self) -> float:
        """计算综合得分"""
        scores = []
        weights = []
        
        if self.analysis_insight:
            scores.append(self.analysis_insight.score)
            weights.append(self.analysis_insight.weight)
        
        if self.visualization:
            scores.append(self.visualization.score)
            weights.append(self.visualization.weight)
        
        if self.robustness:
            scores.append(self.robustness.score)
            weights.append(self.robustness.weight)
        
        if not scores:
            return 0.0
        
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0
        
        self.overall_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        
        # 确定评测等级
        if self.overall_score >= 4.0:
            self.evaluation_level = EvaluationLevel.PROFESSIONAL
        elif self.overall_score >= 3.0:
            self.evaluation_level = EvaluationLevel.INDUSTRIAL
        else:
            self.evaluation_level = EvaluationLevel.PASS
        
        return self.overall_score
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "conversation_id": self.conversation_id,
            "analysis_insight": {
                "name": self.analysis_insight.name,
                "score": self.analysis_insight.score,
                "max_score": self.analysis_insight.max_score,
                "weight": self.analysis_insight.weight,
                "reasoning": self.analysis_insight.reasoning,
                "sub_scores": self.analysis_insight.sub_scores,
            } if self.analysis_insight else None,
            "visualization": {
                "name": self.visualization.name,
                "score": self.visualization.score,
                "max_score": self.visualization.max_score,
                "weight": self.visualization.weight,
                "reasoning": self.visualization.reasoning,
                "sub_scores": self.visualization.sub_scores,
            } if self.visualization else None,
            "robustness": {
                "name": self.robustness.name,
                "score": self.robustness.score,
                "max_score": self.robustness.max_score,
                "weight": self.robustness.weight,
                "reasoning": self.robustness.reasoning,
                "sub_scores": self.robustness.sub_scores,
            } if self.robustness else None,
            "overall_score": self.overall_score,
            "evaluation_level": self.evaluation_level.value,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "recommendations": self.recommendations,
            "evaluated_at": self.evaluated_at,
        }


class EnhancedEvaluator:
    """增强版评测器"""
    
    EVALUATION_PROMPT = """你是一个专业的数据分析评测专家。请对以下对话进行多维度评测。

## 用户问题
{question}

## 生成的SQL
{sql}

## 查询结果摘要
{result_summary}

## AI回答
{answer}

## 评测维度
请从以下三个维度进行评测，每个维度满分5分：

### 维度1: 分析与洞察 (权重40%)
- **业务指令理解能力**: 是否正确理解用户的业务需求 (0-5)
- **用户意图遵循能力**: SQL是否准确反映用户意图 (0-5)
- **数据价值挖掘能力**: 是否从数据中发现有价值的信息 (0-5)
- **分析推理能力**: 分析逻辑是否清晰合理 (0-5)
- **结论推导生成能力**: 结论是否准确、有依据 (0-5)

### 维度2: 可视化呈现 (权重30%)
- **信息提炼能力**: 是否突出关键信息 (0-5)
- **场景适配能力**: 呈现方式是否适合问题类型 (0-5)
- **用户理解适配能力**: 表达是否易于理解 (0-5)

### 维度3: 鲁棒性 (权重30%)
- **成功率**: 是否成功完成任务 (0-5)
- **稳定一致性**: 输出是否规范一致 (0-5)

请按以下JSON格式返回评测结果：
{{
    "analysis_insight": {{
        "business_understanding": {{"score": 0-5, "reason": "评分理由"}},
        "intent_following": {{"score": 0-5, "reason": "评分理由"}},
        "value_discovery": {{"score": 0-5, "reason": "评分理由"}},
        "reasoning_ability": {{"score": 0-5, "reason": "评分理由"}},
        "conclusion_generation": {{"score": 0-5, "reason": "评分理由"}}
    }},
    "visualization": {{
        "info_extraction": {{"score": 0-5, "reason": "评分理由"}},
        "scenario_adaptation": {{"score": 0-5, "reason": "评分理由"}},
        "user_understanding": {{"score": 0-5, "reason": "评分理由"}}
    }},
    "robustness": {{
        "success_rate": {{"score": 0-5, "reason": "评分理由"}},
        "consistency": {{"score": 0-5, "reason": "评分理由"}}
    }},
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["不足1", "不足2"],
    "recommendations": ["建议1", "建议2"]
}}

只输出JSON，不要有其他内容。"""

    def __init__(self, llm_service=None):
        self.llm = llm_service
    
    async def evaluate(
        self,
        conversation_id: str,
        question: str,
        sql: Optional[str],
        result_summary: str,
        answer: str,
    ) -> EnhancedEvaluationResult:
        """执行多维度评测"""
        result = EnhancedEvaluationResult(conversation_id=conversation_id)
        
        if not self.llm:
            # 没有 LLM 时使用规则评测
            return self._rule_based_evaluation(result, question, sql, answer)
        
        try:
            evaluation_data = await self._llm_evaluation(question, sql, result_summary, answer)
            result = self._parse_evaluation(result, evaluation_data)
        except Exception as e:
            logger.error(f"LLM 评测失败: {e}")
            result = self._rule_based_evaluation(result, question, sql, answer)
        
        result.calculate_overall()
        return result
    
    async def _llm_evaluation(
        self,
        question: str,
        sql: Optional[str],
        result_summary: str,
        answer: str,
    ) -> Dict[str, Any]:
        """使用 LLM 进行评测"""
        prompt = self.EVALUATION_PROMPT.format(
            question=question,
            sql=sql or "未生成SQL",
            result_summary=result_summary or "无结果",
            answer=answer or "无回答",
        )
        
        response = await self._call_llm(prompt)
        
        # 提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            return json.loads(json_match.group())
        
        raise ValueError("无法解析 LLM 响应")
    
    def _parse_evaluation(
        self,
        result: EnhancedEvaluationResult,
        data: Dict[str, Any]
    ) -> EnhancedEvaluationResult:
        """解析评测结果"""
        # 解析分析与洞察维度
        if "analysis_insight" in data:
            ai_data = data["analysis_insight"]
            sub_scores = {}
            scores = []
            reasoning_parts = []
            
            for key, value in ai_data.items():
                if isinstance(value, dict):
                    score = value.get("score", 3)
                    sub_scores[key] = score
                    scores.append(score)
                    if value.get("reason"):
                        reasoning_parts.append(f"{key}: {value['reason']}")
            
            avg_score = sum(scores) / len(scores) if scores else 3.0
            
            result.analysis_insight = DimensionScore(
                name="分析与洞察",
                score=avg_score,
                weight=0.4,
                reasoning="; ".join(reasoning_parts[:3]),
                sub_scores=sub_scores,
            )
        
        # 解析可视化呈现维度
        if "visualization" in data:
            viz_data = data["visualization"]
            sub_scores = {}
            scores = []
            reasoning_parts = []
            
            for key, value in viz_data.items():
                if isinstance(value, dict):
                    score = value.get("score", 3)
                    sub_scores[key] = score
                    scores.append(score)
                    if value.get("reason"):
                        reasoning_parts.append(f"{key}: {value['reason']}")
            
            avg_score = sum(scores) / len(scores) if scores else 3.0
            
            result.visualization = DimensionScore(
                name="可视化呈现",
                score=avg_score,
                weight=0.3,
                reasoning="; ".join(reasoning_parts[:2]),
                sub_scores=sub_scores,
            )
        
        # 解析鲁棒性维度
        if "robustness" in data:
            rob_data = data["robustness"]
            sub_scores = {}
            scores = []
            reasoning_parts = []
            
            for key, value in rob_data.items():
                if isinstance(value, dict):
                    score = value.get("score", 3)
                    sub_scores[key] = score
                    scores.append(score)
                    if value.get("reason"):
                        reasoning_parts.append(f"{key}: {value['reason']}")
            
            avg_score = sum(scores) / len(scores) if scores else 3.0
            
            result.robustness = DimensionScore(
                name="鲁棒性",
                score=avg_score,
                weight=0.3,
                reasoning="; ".join(reasoning_parts[:2]),
                sub_scores=sub_scores,
            )
        
        # 解析优缺点和建议
        result.strengths = data.get("strengths", [])
        result.weaknesses = data.get("weaknesses", [])
        result.recommendations = data.get("recommendations", [])
        
        return result
    
    def _rule_based_evaluation(
        self,
        result: EnhancedEvaluationResult,
        question: str,
        sql: Optional[str],
        answer: str,
    ) -> EnhancedEvaluationResult:
        """基于规则的评测（后备方案）"""
        # 分析与洞察
        ai_score = 3.0
        ai_sub_scores = {}
        
        # 检查是否生成了 SQL
        if sql:
            ai_sub_scores["intent_following"] = 4.0
            ai_score += 0.5
        else:
            ai_sub_scores["intent_following"] = 2.0
            ai_score -= 0.5
        
        # 检查回答长度和质量
        if answer:
            if len(answer) > 200:
                ai_sub_scores["conclusion_generation"] = 4.0
                ai_score += 0.3
            elif len(answer) > 50:
                ai_sub_scores["conclusion_generation"] = 3.0
            else:
                ai_sub_scores["conclusion_generation"] = 2.0
                ai_score -= 0.3
        
        result.analysis_insight = DimensionScore(
            name="分析与洞察",
            score=min(max(ai_score, 1.0), 5.0),
            weight=0.4,
            reasoning="基于规则评测",
            sub_scores=ai_sub_scores,
        )
        
        # 可视化呈现
        viz_score = 3.0
        if answer and ("数据" in answer or "结果" in answer):
            viz_score = 3.5
        
        result.visualization = DimensionScore(
            name="可视化呈现",
            score=viz_score,
            weight=0.3,
            reasoning="基于规则评测",
        )
        
        # 鲁棒性
        rob_score = 4.0 if sql and answer else 2.0
        result.robustness = DimensionScore(
            name="鲁棒性",
            score=rob_score,
            weight=0.3,
            reasoning="基于任务完成情况",
        )
        
        return result
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        if not self.llm:
            return ""
        
        messages = [{"role": "user", "content": prompt}]
        
        def sync_call():
            response = self.llm._client.chat.completions.create(
                model=self.llm.model,
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
            )
            return response.choices[0].message.content or ""
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_call)


class EvaluationReportGenerator:
    """评测报告生成器"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self) -> None:
        """初始化数据库表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS enhanced_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                overall_score REAL,
                evaluation_level TEXT,
                analysis_insight_score REAL,
                visualization_score REAL,
                robustness_score REAL,
                strengths TEXT,
                weaknesses TEXT,
                recommendations TEXT,
                full_result TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(conversation_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_evaluation(self, result: EnhancedEvaluationResult) -> None:
        """保存评测结果"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO enhanced_evaluations (
                conversation_id, overall_score, evaluation_level,
                analysis_insight_score, visualization_score, robustness_score,
                strengths, weaknesses, recommendations, full_result, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.conversation_id,
            result.overall_score,
            result.evaluation_level.value,
            result.analysis_insight.score if result.analysis_insight else None,
            result.visualization.score if result.visualization else None,
            result.robustness.score if result.robustness else None,
            json.dumps(result.strengths, ensure_ascii=False),
            json.dumps(result.weaknesses, ensure_ascii=False),
            json.dumps(result.recommendations, ensure_ascii=False),
            json.dumps(result.to_dict(), ensure_ascii=False),
            result.evaluated_at,
        ))
        
        conn.commit()
        conn.close()
    
    def get_evaluation(self, conversation_id: str) -> Optional[EnhancedEvaluationResult]:
        """获取评测结果"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT full_result FROM enhanced_evaluations WHERE conversation_id = ?",
            (conversation_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        try:
            data = json.loads(row["full_result"])
            return self._dict_to_result(data)
        except:
            return None
    
    def _dict_to_result(self, data: Dict[str, Any]) -> EnhancedEvaluationResult:
        """将字典转换为结果对象"""
        result = EnhancedEvaluationResult(
            conversation_id=data.get("conversation_id", ""),
            overall_score=data.get("overall_score", 0.0),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            recommendations=data.get("recommendations", []),
            evaluated_at=data.get("evaluated_at", ""),
        )
        
        # 设置评测等级
        level_str = data.get("evaluation_level", "pass")
        result.evaluation_level = EvaluationLevel(level_str)
        
        # 解析各维度
        if data.get("analysis_insight"):
            ai_data = data["analysis_insight"]
            result.analysis_insight = DimensionScore(
                name=ai_data.get("name", "分析与洞察"),
                score=ai_data.get("score", 0),
                max_score=ai_data.get("max_score", 5.0),
                weight=ai_data.get("weight", 0.4),
                reasoning=ai_data.get("reasoning", ""),
                sub_scores=ai_data.get("sub_scores", {}),
            )
        
        if data.get("visualization"):
            viz_data = data["visualization"]
            result.visualization = DimensionScore(
                name=viz_data.get("name", "可视化呈现"),
                score=viz_data.get("score", 0),
                max_score=viz_data.get("max_score", 5.0),
                weight=viz_data.get("weight", 0.3),
                reasoning=viz_data.get("reasoning", ""),
                sub_scores=viz_data.get("sub_scores", {}),
            )
        
        if data.get("robustness"):
            rob_data = data["robustness"]
            result.robustness = DimensionScore(
                name=rob_data.get("name", "鲁棒性"),
                score=rob_data.get("score", 0),
                max_score=rob_data.get("max_score", 5.0),
                weight=rob_data.get("weight", 0.3),
                reasoning=rob_data.get("reasoning", ""),
                sub_scores=rob_data.get("sub_scores", {}),
            )
        
        return result
    
    def generate_aggregate_report(self, days: int = 7) -> Dict[str, Any]:
        """生成聚合评测报告"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 统计总体情况
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                AVG(overall_score) as avg_score,
                AVG(analysis_insight_score) as avg_ai_score,
                AVG(visualization_score) as avg_viz_score,
                AVG(robustness_score) as avg_rob_score,
                SUM(CASE WHEN evaluation_level = 'professional' THEN 1 ELSE 0 END) as professional_count,
                SUM(CASE WHEN evaluation_level = 'industrial' THEN 1 ELSE 0 END) as industrial_count,
                SUM(CASE WHEN evaluation_level = 'pass' THEN 1 ELSE 0 END) as pass_count
            FROM enhanced_evaluations
            WHERE created_at >= datetime('now', ?)
        """, (f'-{days} days',))
        
        row = cursor.fetchone()
        
        # 获取常见问题
        cursor.execute("""
            SELECT weaknesses FROM enhanced_evaluations
            WHERE created_at >= datetime('now', ?)
        """, (f'-{days} days',))
        
        all_weaknesses = []
        for r in cursor.fetchall():
            try:
                weaknesses = json.loads(r["weaknesses"])
                all_weaknesses.extend(weaknesses)
            except:
                pass
        
        # 统计常见问题
        weakness_counts = {}
        for w in all_weaknesses:
            weakness_counts[w] = weakness_counts.get(w, 0) + 1
        
        top_weaknesses = sorted(weakness_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        conn.close()
        
        return {
            "period_days": days,
            "total_evaluations": row["total"] if row else 0,
            "average_score": round(row["avg_score"] or 0, 2),
            "dimension_scores": {
                "analysis_insight": round(row["avg_ai_score"] or 0, 2),
                "visualization": round(row["avg_viz_score"] or 0, 2),
                "robustness": round(row["avg_rob_score"] or 0, 2),
            },
            "level_distribution": {
                "professional": row["professional_count"] if row else 0,
                "industrial": row["industrial_count"] if row else 0,
                "pass": row["pass_count"] if row else 0,
            },
            "top_weaknesses": [{"issue": w, "count": c} for w, c in top_weaknesses],
        }


# 全局服务实例
_enhanced_evaluator: Optional[EnhancedEvaluator] = None
_evaluation_report_generator: Optional[EvaluationReportGenerator] = None


def init_enhanced_evaluation(
    llm_service=None,
    db_path: Optional[Path] = None,
) -> Tuple[EnhancedEvaluator, Optional[EvaluationReportGenerator]]:
    """初始化增强版评测服务"""
    global _enhanced_evaluator, _evaluation_report_generator
    
    _enhanced_evaluator = EnhancedEvaluator(llm_service)
    
    if db_path:
        _evaluation_report_generator = EvaluationReportGenerator(db_path)
    
    return _enhanced_evaluator, _evaluation_report_generator


def get_enhanced_evaluator() -> Optional[EnhancedEvaluator]:
    return _enhanced_evaluator


def get_evaluation_report_generator() -> Optional[EvaluationReportGenerator]:
    return _evaluation_report_generator









