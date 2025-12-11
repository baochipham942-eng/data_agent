# RAG 评分和 Memory 页面更新

## ✅ 已完成的功能

### 1. RAG 评分综合考虑专家评分 ✅

**修改内容**：
- 修改了 `RAGLearner.learn_from_feedback()` 方法，新增参数：
  - `expert_rating`: 专家评分 (1-5)
  - `user_rating`: 用户评分 (1-5)
  - `llm_score`: LLM评估评分 (1-5)
- 实现了 `_calculate_composite_score()` 方法，加权计算综合评分：
  - **专家评分权重：0.5**（最高优先级）
  - **LLM评分权重：0.3**
  - **用户评分权重：0.2**

**评分计算示例**：
```python
# 示例1：专家5分，用户4分，LLM4.5分
综合评分 = (5 * 0.5 + 4.5 * 0.3 + 4 * 0.2) / (0.5 + 0.3 + 0.2) = 4.65

# 示例2：只有专家5分和LLM4.0分
综合评分 = (5 * 0.5 + 4.0 * 0.3) / (0.5 + 0.3) = 4.625
```

**集成位置**：
- ✅ `FeedbackLearner.learn_from_feedback()` - 传递专家评分给RAGLearner
- ✅ `app/routes/feedback.py` - 专家评分提交时传递专家评分
- ✅ `app/routes/feedback.py` - LLM评估时也获取并传递已有的专家评分

### 2. Memory 页面增加 RAG 高分案例 Tab ✅

**后端API**：
- ✅ `/api/memory/rag/high-score` - 获取RAG知识库高分案例
- ✅ `/api/memory/rag/stats` - 获取RAG知识库统计信息

**前端实现**：
- ✅ 添加了 `RAGHighScoreCase` 类型定义
- ✅ 添加了 `fetchRAGHighScoreCases()` 和 `fetchRAGStats()` API调用
- ✅ 在 `MemoryPage` 中添加了第三个 Tab："RAG 高分案例"
- ✅ 添加了 `ragColumns` 表格列定义，显示：
  - 时间
  - 问题
  - SQL
  - 评分（综合评分、专家评分、质量评分）
  - 来源（专家/反馈/自动）
  - 使用次数
- ✅ 统计卡片中增加了 "RAG 高分案例" 统计

**表格列说明**：
- **时间**：创建时间
- **问题**：用户问题
- **SQL**：对应的SQL查询（可hover查看完整SQL）
- **评分**：
  - 综合评分（金色标签）
  - 专家评分（紫色标签，如果有）
  - 质量评分（青色标签）
- **来源**：
  - 专家（紫色标签）
  - 反馈（蓝色标签）
  - 自动（默认标签）
- **使用次数**：该案例被FewShotSelector使用的次数

## 📊 数据流

### 评分综合计算流程

```
专家评分提交
    ↓
FeedbackLearner.learn_from_feedback(expert_rating=5)
    ↓
计算综合评分（专家权重0.5）
    ↓
RAGLearner.learn_from_feedback(
    expert_rating=5,
    user_rating=4,  # 如果有
    llm_score=4.5,  # 如果有
)
    ↓
_calculate_composite_score()
    ↓
加权平均 = (5*0.5 + 4*0.2 + 4.5*0.3) / 1.0 = 4.65
    ↓
存储到 RAG 知识库（score=4.65）
```

### Memory 页面数据加载

```
MemoryPage 加载
    ↓
并行请求：
  - fetchMemoryStats() → Agent Memory统计
  - fetchRecentToolMemories() → SQL学习记录
  - fetchRecentTextMemories() → Schema记忆
  - fetchRAGHighScoreCases() → RAG高分案例
  - fetchRAGStats() → RAG统计信息
    ↓
显示在3个Tab中：
  - SQL 学习记录
  - Schema 记忆
  - RAG 高分案例（新增）
```

## 🎯 评分维度总结

### RAG 使用的评分包含的维度

1. **原始评分（score）**：
   - 来源：综合评分（加权平均）
   - 权重分配：
     - 专家评分：50%
     - LLM评分：30%
     - 用户评分：20%
   - 范围：1.0 - 5.0
   - 用途：决定是否学习（默认阈值 ≥ 4.0）

2. **质量评分（quality_score）**：
   - 维度1：问题清晰度（0-0.3分）
     - 长度检查
     - 疑问词检查
   - 维度2：SQL有效性（0-0.4分）
     - SELECT语句检查
     - FROM子句检查
     - WHERE/GROUP BY/ORDER BY检查
     - 长度合理性检查
   - 维度3：答案相关性（0-0.3分）
     - 答案长度检查
     - 数据内容检查
     - 关键词检查
   - 范围：0.0 - 1.0
   - 用途：质量过滤（默认阈值 ≥ 0.7）

## 📝 使用说明

### 查看 RAG 高分案例

1. 打开 "学习记忆" 页面
2. 点击 "RAG 高分案例" Tab
3. 查看所有高分案例（评分 ≥ 4.0，质量 ≥ 0.7）
4. 可以看到：
   - 问题、SQL、评分详情
   - 专家评分、用户评分、LLM评分
   - 使用次数（被FewShotSelector使用的次数）

### 评分权重说明

- **专家评分权重最高（0.5）**：因为专家评分更可靠
- **LLM评分权重中等（0.3）**：LLM评估有一定参考价值
- **用户评分权重较低（0.2）**：用户评分可能不够专业

如果只有部分评分，权重会按比例调整。例如：
- 只有专家评分和LLM评分：权重为 0.5/(0.5+0.3) = 0.625 和 0.3/(0.5+0.3) = 0.375

## 🔧 相关文件

- `app/services/rag_learner.py` - RAG学习器（综合评分计算）
- `app/services/llm_judge.py` - 反馈学习器（传递专家评分）
- `app/routes/feedback.py` - 反馈路由（专家评分提交）
- `app/routes/memory.py` - Memory路由（RAG高分案例API）
- `frontend/src/components/MemoryPage.tsx` - Memory页面（RAG Tab）
- `frontend/src/utils/api.ts` - API调用（RAG相关）









