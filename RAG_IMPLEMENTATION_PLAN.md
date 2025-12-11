# RAG 实现计划

## 📋 实现阶段

### 阶段 1：创建 RAG 知识库基础结构 (2-3天)

**目标**：
- 创建 RAG 知识库数据库表结构
- 实现基础的 CRUD 操作
- 实现简单的高分案例提取和存储

**实现内容**：
1. ✅ 创建 `RAGKnowledgeBase` 服务类
2. ✅ 数据库表结构设计
3. ✅ 基础的数据存储和检索方法
4. ✅ 从高分反馈中提取问答对
5. ✅ 简单的关键词检索（先不涉及向量）

**文件**：
- `app/services/rag_knowledge_base.py` - RAG 知识库服务
- 数据库表：`rag_qa_pairs`

### 阶段 2：实现向量化检索 (3-5天)

**目标**：
- 集成向量嵌入服务
- 实现向量相似度检索
- 混合检索（向量 + 关键词）

**实现内容**：
1. ✅ 创建 `EmbeddingService` 服务
2. ✅ 集成向量嵌入（支持 OpenAI 或本地模型）
3. ✅ 向量存储和索引
4. ✅ 向量相似度搜索
5. ✅ 混合检索策略

**文件**：
- `app/services/embedding_service.py` - 向量嵌入服务
- 扩展 `rag_knowledge_base.py` 支持向量检索

### 阶段 3：实现自动学习优化 (2-3天)

**目标**：
- 增强学习机制
- 质量评估和去重
- 自动更新和清理

**实现内容**：
1. ✅ 创建 `RAGLearner` 服务
2. ✅ 从高分反馈中自动提取和结构化
3. ✅ 质量评估机制
4. ✅ 去重和相似度检查
5. ✅ 自动更新评分和清理低质量条目

**文件**：
- `app/services/rag_learner.py` - RAG 自动学习器
- 集成到现有的 `FeedbackLearner`

### 阶段 4：集成到 SQL 生成流程 (2天)

**目标**：
- 在 SQL 生成时优先检索 RAG 知识库
- 作为 Few-shot 示例注入 Prompt
- 性能优化和缓存

**实现内容**：
1. ✅ 修改 SQL 生成流程
2. ✅ RAG 检索与 Few-shot 示例整合
3. ✅ 优化 Prompt 构建
4. ✅ 缓存机制
5. ✅ 性能优化

**文件**：
- 修改 `app/services/sql_enhancer.py`
- 修改 `app/services/query_analyzer.py`

## 🎯 实现策略

### 技术选型

**向量嵌入**：
- 优先：本地模型（sentence-transformers），降低成本
- 备选：OpenAI embeddings（如果本地模型效果不佳）
- 备选：DeepSeek embeddings（如果支持）

**向量存储**：
- SQLite + vector extension（如果可用）
- 或者：直接存储 BLOB + 计算相似度

**检索策略**：
- 混合检索：向量相似度 + 关键词匹配
- 质量过滤：只使用高分示例
- Top-K 排序：相似度 + 质量分

## 📊 数据库设计

```sql
CREATE TABLE rag_qa_pairs (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    sql TEXT NOT NULL,
    answer_preview TEXT,
    
    -- 向量嵌入（可选，阶段2）
    embedding BLOB,
    
    -- 质量评分
    score REAL DEFAULT 0.0,  -- 原始评分
    quality_score REAL DEFAULT 0.0,  -- 质量评分
    
    -- 来源信息
    source TEXT,  -- 'feedback', 'expert', 'auto'
    conversation_id TEXT,
    
    -- 标签和分类
    tags TEXT,  -- JSON array
    category TEXT,
    
    -- 元数据
    metadata TEXT,  -- JSON
    usage_count INTEGER DEFAULT 0,
    last_used_at DATETIME,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_rag_score ON rag_qa_pairs(score DESC);
CREATE INDEX idx_rag_quality ON rag_qa_pairs(quality_score DESC);
CREATE INDEX idx_rag_source ON rag_qa_pairs(source);
CREATE INDEX idx_rag_category ON rag_qa_pairs(category);
CREATE INDEX idx_rag_created ON rag_qa_pairs(created_at DESC);
```

## 🔄 学习流程

```
用户反馈/评测
    ↓
评分 >= 4.0?
    ↓ 是
提取问答对
    ↓
质量评估
    ↓
质量 >= 0.7?
    ↓ 是
去重检查
    ↓
存储到 RAG 知识库
    ↓
标记来源和评分
```

## 🔍 检索流程

```
用户问题
    ↓
检索 RAG 知识库
    ↓
向量相似度搜索 + 关键词匹配
    ↓
质量过滤（只取高质量）
    ↓
Top-K 排序（相似度 + 质量分）
    ↓
格式化 Few-shot 示例
    ↓
注入 SQL 生成 Prompt
```









