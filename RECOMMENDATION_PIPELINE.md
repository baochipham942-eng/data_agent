# 智能推荐链路设计

## 📋 推荐链路概览

基于你的项目实际情况，完整的智能推荐链路如下：

```
┌─────────────────────────────────────────────────────────────────┐
│                     智能推荐完整链路                               │
└─────────────────────────────────────────────────────────────────┘

阶段1: 数据收集与记忆
├─ 用户输入查询
├─ 记录查询历史 (UserProfileService.record_query)
├─ 记录对话上下文 (AgentMemory)
└─ 存储到 user_query_history 表

阶段2: 偏好学习
├─ 统计分析 (UserProfileService.learn_preferences)
│  ├─ 图表类型偏好统计
│  ├─ 维度使用频率统计
│  ├─ 时间范围偏好统计
│  └─ 查询类型分布统计
└─ 抽象用户画像
   ├─ preferred_chart_type
   ├─ preferred_time_range
   ├─ focus_dimensions
   └─ expertise_level

阶段3: 推荐生成
├─ 用户新提问触发
├─ 多源推荐策略
│  ├─ 基于内容的推荐 (Content-Based)
│  ├─ 协同过滤推荐 (Collaborative Filtering)
│  └─ 混合推荐 (Hybrid)
└─ 生成推荐列表

阶段4: 推荐应用
├─ 查询推荐
├─ 图表类型推荐
├─ 维度推荐
└─ 快捷操作推荐
```

## 🔄 详细链路说明

### 阶段1: 数据收集与记忆 (Data Collection & Memory)

**当前实现**：
- ✅ `UserProfileService.record_query()` - 记录用户查询
- ✅ `SqliteAgentMemory` - 存储对话记忆
- ✅ `user_query_history` 表 - 查询历史表

**数据流向**：
```
用户输入查询
    ↓
QueryAnalyzer 分析
    ├─ 提取 query_type (趋势/对比/分布等)
    ├─ 提取 dimensions (按省份/按日期等)
    ├─ 提取 metrics (访问量/转化率等)
    └─ 提取 time_range (最近7天/本周等)
    ↓
记录到 user_query_history
    ├─ user_id
    ├─ query_text
    ├─ query_type
    ├─ chart_type
    ├─ dimensions (JSON)
    ├─ metrics (JSON)
    └─ time_range
```

**代码位置**：
- `app/services/agent_memory.py:749` - `UserProfileService.record_query()`
- `app/services/query_analyzer.py` - 查询分析

### 阶段2: 偏好学习 (Preference Learning)

**当前实现**：
- ✅ `UserProfileService.learn_preferences()` - 从历史查询学习偏好
- ✅ 统计图表类型、维度、时间范围等
- ✅ 更新用户画像 (`user_profile` 表)

**学习过程**：
```
累积 N 条查询历史 (N >= 5)
    ↓
learn_preferences() 触发
    ↓
统计分析
    ├─ 图表类型偏好
    │   └─ 统计每种图表类型的使用次数
    ├─ 常用维度提取
    │   └─ Counter 统计，取 Top 5
    ├─ 时间范围偏好
    │   └─ 统计最常用的时间范围
    └─ 查询类型分布
        └─ 统计各类型查询的分布
    ↓
抽象为画像特征
    ├─ preferred_chart_type: "line" | "bar" | "pie"
    ├─ preferred_time_range: "最近7天" | "本周"
    ├─ focus_dimensions: ["省份", "日期", "渠道"]
    └─ expertise_level: "beginner" | "intermediate" | "expert"
    ↓
更新 user_profile 表
```

**代码位置**：
- `app/services/agent_memory.py:779` - `learn_preferences()`

### 阶段3: 推荐生成 (Recommendation Generation)

**当前状态**：⚠️ 部分实现，需要扩展

#### 3.1 基于内容的推荐 (Content-Based) ✅ 已实现

**实现方式**：
- 基于用户历史查询，推荐相似的查询
- 使用向量相似度匹配（`EmbeddingService`）

**推荐流程**：
```
用户新提问
    ↓
提取查询特征
    ├─ 语义分词 (QueryAnalyzer.semantic_tokenize)
    ├─ 提取维度、指标、时间范围
    └─ 向量化 (EmbeddingService.embed)
    ↓
检索相似历史查询
    ├─ 向量相似度搜索 (cosine_similarity)
    └─ 关键词匹配 (Jaccard 相似度)
    ↓
生成推荐列表
    └─ 返回 Top K 相似查询
```

**代码位置**：
- `app/services/rag_knowledge_base.py:377` - `retrieve_similar()`
- `app/services/embedding_service.py` - 向量嵌入

#### 3.2 协同过滤推荐 (Collaborative Filtering) ❌ 未实现

**你的链路提到的"协同过滤推荐"**：
- 当前项目**尚未实现**协同过滤
- 但可以基于现有数据进行扩展

**协同过滤思路**：
```
用户相似度计算
    ├─ 基于查询模式相似度
    │   ├─ 相似的用户关注的维度
    │   ├─ 相似的时间范围偏好
    │   └─ 相似的图表类型偏好
    └─ 基于行为相似度
        └─ 相似用户都喜欢哪些查询
    ↓
找出相似用户群
    ↓
推荐相似用户的偏好查询
```

**实现建议**：
1. 计算用户相似度矩阵
2. 找到 Top K 相似用户
3. 推荐相似用户的高频查询

**可以扩展的代码位置**：
- 新建 `app/services/collaborative_filter.py`
- 使用 `user_query_history` 表的数据

#### 3.3 混合推荐 (Hybrid) ❌ 未实现

**混合推荐策略**：
```
基于内容推荐 (权重: 0.4)
    ↓
协同过滤推荐 (权重: 0.3)
    ↓
基于画像推荐 (权重: 0.3)
    ├─ 基于 focus_dimensions 推荐维度
    ├─ 基于 preferred_chart_type 推荐图表
    └─ 基于 preferred_time_range 推荐时间
    ↓
加权融合
    ↓
生成最终推荐列表
```

### 阶段4: 推荐应用 (Recommendation Application)

**推荐应用场景**：

#### 4.1 查询推荐 ✅ 部分实现

**当前实现**：
- RAG 知识库检索相似查询（作为 Few-shot 示例）

**可扩展场景**：
- 在用户输入框下方显示推荐查询
- 基于当前对话上下文推荐后续查询
- 推荐用户历史常用的查询模板

#### 4.2 图表类型推荐 ✅ 已实现

**当前实现**：
- `AutoChart.tsx` 自动判断推荐图表类型
- 基于数据特征推荐（数据量、日期格式等）

**可扩展**：
- 结合用户偏好 (`preferred_chart_type`) 推荐
- 在生成图表时优先使用用户偏好类型

**代码位置**：
- `frontend/src/components/AutoChart.tsx:78` - 图表类型推荐

#### 4.3 维度推荐 ❌ 未实现

**推荐场景**：
- 用户查询后，推荐可以按哪些维度拆分
- 基于 `focus_dimensions` 推荐用户常关注的维度

#### 4.4 快捷操作推荐 ✅ 部分实现

**当前实现**：
- 快捷操作按钮（环比、对比、拆分等）

**代码位置**：
- `MULTI_TURN_OPTIMIZATION.md` - 快捷操作设计

## 🎯 你提出的链路分析

你提出的链路：
```
用户输入 → 记忆 → 学习 → 抽象画像 → 用户提问 → 协同过滤推荐
```

### ✅ 正确的地方：
1. **用户输入 → 记忆**：✅ 已实现
   - `record_query()` 记录到 `user_query_history`

2. **记忆 → 学习**：✅ 已实现
   - `learn_preferences()` 从历史查询学习

3. **学习 → 抽象画像**：✅ 已实现
   - 抽象为 `preferences`、`focus_dimensions` 等

4. **用户提问 → 推荐**：✅ 部分实现
   - RAG 检索相似查询（基于内容）
   - 动态 Prompt 使用画像（间接推荐）

### ⚠️ 需要补充的地方：
1. **协同过滤推荐**：❌ 未实现
   - 当前只有基于内容的推荐
   - 需要实现用户相似度计算

2. **推荐应用时机**：需要明确
   - 何时触发推荐？
   - 推荐显示在哪里？

## 🔧 完整推荐链路实现建议

### 推荐1: 完整的数据流链路

```
1. 用户输入查询
   ↓
2. 记录到 user_query_history
   ↓
3. 定期/实时触发 learn_preferences()
   ↓
4. 更新 user_profile (画像)
   ↓
5. 用户新提问时
   ├─ 获取用户画像
   ├─ 检索相似查询 (基于内容)
   ├─ 查找相似用户 (协同过滤)
   └─ 基于画像生成推荐
   ↓
6. 生成推荐列表
   ├─ 查询推荐 (Top 5)
   ├─ 维度推荐 (Top 3)
   ├─ 图表推荐 (1个)
   └─ 快捷操作推荐
   ↓
7. 前端展示推荐
```

### 推荐2: 推荐触发时机

**实时推荐**：
- 用户输入时，实时推荐相关查询（自动完成）

**上下文推荐**：
- 查询结果展示后，推荐后续操作
  - 快捷操作按钮
  - 推荐维度拆分
  - 推荐对比分析

**主动推荐**：
- 用户进入系统时，推荐常用查询
- 基于画像推荐个性化查询模板

### 推荐3: 推荐算法组合

**当前可用**：
- ✅ 基于内容的推荐（向量相似度）
- ✅ 基于画像的推荐（用户偏好）

**需要实现**：
- ❌ 协同过滤推荐
- ❌ 混合推荐策略

## 📊 推荐链路架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      推荐系统架构                              │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐
│  用户输入查询  │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────────────────────┐
│           数据收集层 (Data Collection)            │
│  ┌───────────────────────────────────────────┐  │
│  │ UserProfileService.record_query()         │  │
│  │  - 记录查询文本、类型、维度、指标          │  │
│  │  - 存储到 user_query_history 表            │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────┐
│          偏好学习层 (Preference Learning)         │
│  ┌───────────────────────────────────────────┐  │
│  │ UserProfileService.learn_preferences()    │  │
│  │  - 统计分析图表类型偏好                    │  │
│  │  - 提取常用维度 (Top 5)                   │  │
│  │  - 统计时间范围偏好                        │  │
│  │  - 抽象为画像特征                          │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │ UserProfileService.create_or_update_      │  │
│  │   profile()                               │  │
│  │  - 更新 user_profile 表                    │  │
│  │  - 存储 preferences, focus_dimensions     │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────┐
│         推荐生成层 (Recommendation Engine)        │
│                                                    │
│  ┌───────────────────────────────────────────┐  │
│  │ 基于内容的推荐 (Content-Based) ✅          │  │
│  │  - EmbeddingService.embed()               │  │
│  │  - RAGKnowledgeBase.retrieve_similar()    │  │
│  │  - 向量相似度 + 关键词匹配                 │  │
│  └───────────────────────────────────────────┘  │
│                                                    │
│  ┌───────────────────────────────────────────┐  │
│  │ 基于画像的推荐 (Profile-Based) ✅          │  │
│  │  - 基于 preferred_chart_type              │  │
│  │  - 基于 focus_dimensions                  │  │
│  │  - 基于 preferred_time_range              │  │
│  └───────────────────────────────────────────┘  │
│                                                    │
│  ┌───────────────────────────────────────────┐  │
│  │ 协同过滤推荐 (Collaborative) ❌            │  │
│  │  - 计算用户相似度矩阵                      │  │
│  │  - 找到相似用户群                          │  │
│  │  - 推荐相似用户的查询                      │  │
│  └───────────────────────────────────────────┘  │
│                                                    │
│  ┌───────────────────────────────────────────┐  │
│  │ 混合推荐策略 (Hybrid) ❌                   │  │
│  │  - 加权融合多种推荐结果                    │  │
│  │  - 去重和排序                              │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────┐
│          推荐应用层 (Recommendation UI)          │
│  ┌───────────────────────────────────────────┐  │
│  │ 查询推荐                                   │  │
│  │  - 自动完成建议                            │  │
│  │  - 相关查询推荐                            │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │ 图表类型推荐 ✅                            │  │
│  │  - AutoChart 自动判断                      │  │
│  │  - 结合用户偏好                            │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │ 维度推荐                                   │  │
│  │  - 基于 focus_dimensions                   │  │
│  │  - 推荐可拆分维度                          │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │ 快捷操作推荐 ✅                            │  │
│  │  - 环比、对比、拆分等                      │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## 🔍 当前实现状态总结

| 链路环节 | 实现状态 | 代码位置 |
|---------|---------|---------|
| 数据收集 | ✅ 已实现 | `UserProfileService.record_query()` |
| 偏好学习 | ✅ 已实现 | `UserProfileService.learn_preferences()` |
| 抽象画像 | ✅ 已实现 | `user_profile` 表 |
| 基于内容推荐 | ✅ 已实现 | `RAGKnowledgeBase.retrieve_similar()` |
| 基于画像推荐 | ✅ 部分实现 | `DynamicPromptBuilder` (间接) |
| 协同过滤推荐 | ❌ 未实现 | 需要新建 |
| 混合推荐 | ❌ 未实现 | 需要新建 |
| 推荐应用 | ✅ 部分实现 | `AutoChart`, 快捷操作 |

## 🚀 下一步实现建议

### 优先级1: 协同过滤推荐 (高优先级)

**实现文件**：`app/services/collaborative_filter.py`

**核心功能**：
```python
class CollaborativeFilter:
    async def find_similar_users(
        self, 
        user_id: str, 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """找到相似用户"""
        # 1. 计算用户查询向量
        # 2. 计算用户相似度矩阵
        # 3. 返回 Top K 相似用户
        
    async def recommend_queries(
        self,
        user_id: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """推荐相似用户的查询"""
        # 1. 找到相似用户
        # 2. 获取相似用户的高频查询
        # 3. 过滤掉用户已有的查询
        # 4. 返回推荐列表
```

### 优先级2: 推荐服务统一接口 (高优先级)

**实现文件**：`app/services/recommendation_service.py`

**核心功能**：
```python
class RecommendationService:
    async def get_query_recommendations(
        self,
        user_id: str,
        current_query: Optional[str] = None,
        limit: int = 5
    ) -> List[Recommendation]:
        """获取查询推荐"""
        # 1. 基于内容推荐
        # 2. 协同过滤推荐
        # 3. 基于画像推荐
        # 4. 混合融合
        # 5. 返回推荐列表
        
    async def get_chart_recommendations(
        self,
        user_id: str,
        data_features: Dict[str, Any]
    ) -> str:
        """获取图表类型推荐"""
        
    async def get_dimension_recommendations(
        self,
        user_id: str,
        available_dimensions: List[str]
    ) -> List[str]:
        """获取维度推荐"""
```

### 优先级3: 前端推荐展示 (中优先级)

**实现组件**：
- `QueryRecommendations.tsx` - 查询推荐组件
- `DimensionRecommendations.tsx` - 维度推荐组件
- 集成到 `ChatInterface.tsx`

## 📝 总结

**你的链路基本正确**，但需要补充：

1. ✅ **用户输入 → 记忆 → 学习 → 抽象画像**：已完整实现
2. ⚠️ **协同过滤推荐**：未实现，需要新增
3. ⚠️ **推荐应用**：部分实现，需要扩展

**完整推荐链路应该是**：
```
用户输入 → 记忆 → 学习 → 抽象画像 → 用户提问 → 
[基于内容推荐 + 协同过滤推荐 + 基于画像推荐] → 
混合融合 → 推荐列表 → 前端展示
```




