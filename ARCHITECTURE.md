# Vanna Data Agent 功能架构文档

## 📋 项目概述

**Vanna Data Agent Demo** 是一个现代化的数据分析 Agent 应用，基于 Vanna 框架构建，支持自然语言查询、SQL 生成、数据可视化和对话日志管理。

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层 (Frontend)                      │
│  React + TypeScript + Ant Design + ECharts                  │
│  - 聊天界面 (ChatInterface)                                  │
│  - 数据可视化 (AutoChart, DataChart)                         │
│  - 推理过程展示 (ThoughtChain)                               │
│  - 语义分词展示 (SemanticTokens)                             │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/SSE
┌──────────────────────▼──────────────────────────────────────┐
│                    API 路由层 (Routes)                        │
│  FastAPI Router                                             │
│  - /api/vanna/v2/chat_sse (SSE 流式聊天)                    │
│  - /api/analysis/* (查询分析)                                │
│  - /api/knowledge/* (知识库管理)                             │
│  - /api/prompt/* (Prompt 配置)                               │
│  - /api/memory/* (记忆管理)                                  │
│  - /api/feedback/* (反馈评分)                                │
│  - /api/logs/* (日志管理)                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   中间件层 (Middleware)                       │
│  - LoggingMiddleware (日志记录)                              │
│  - ErrorHandlerMiddleware (统一错误处理)                     │
│  - PersonalizedContextMiddleware (个性化上下文)              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   核心服务层 (Services)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Vanna Agent (核心 Agent)                            │  │
│  │  - LLM Service (DeepSeek API)                        │  │
│  │  - Tool Registry (工具注册)                          │  │
│  │    ├─ RunSqlTool (SQL 执行)                          │  │
│  │    └─ VisualizeDataTool (数据可视化)                 │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  查询分析服务 (QueryAnalyzer)                         │  │
│  │  - 语义分词 (Semantic Tokenization)                  │  │
│  │  - 问题改写 (Question Rewriting)                     │  │
│  │  - 表选择 (Table Selection)                          │  │
│  │  - 业务知识匹配 (Knowledge Matching)                 │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  业务知识库 (BusinessKnowledge)                       │  │
│  │  - 时间规则 (Time Rules)                             │  │
│  │  - 业务术语 (Business Terms)                         │  │
│  │  - 字段映射 (Field Mappings)                         │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Prompt 管理 (PromptManager)                          │  │
│  │  - Prompt 版本管理                                    │  │
│  │  - 动态 Prompt 构建                                   │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  RAG 知识库 (RAGKnowledgeBase)                        │  │
│  │  - 向量嵌入 (EmbeddingService)                       │  │
│  │  - 相似度检索                                         │  │
│  │  - 自动学习 (RAGLearner)                             │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  用户管理 (EnhancedUserResolver)                      │  │
│  │  - 用户识别                                           │  │
│  │  - 用户画像                                           │  │
│  │  - 权限管理 (ToolPermissionManager)                   │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   数据存储层 (Data Layer)                     │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  data.db         │  │  system.db       │                │
│  │  (业务数据)       │  │  (系统数据)       │                │
│  │  - gio_event     │  │  - prompts       │                │
│  │  - sales         │  │  - time_rules    │                │
│  │  - ...           │  │  - business_terms│                │
│  └──────────────────┘  │  - field_mappings│                │
│                        │  - rag_qa_pairs  │                │
│  ┌──────────────────┐  │  - user_profiles │                │
│  │  logs.db         │  │  - ...           │                │
│  │  (日志数据)       │  └──────────────────┘                │
│  │  - conversations │                                       │
│  │  - messages      │  ┌──────────────────┐                │
│  │  - ...           │  │  vanna_data/     │                │
│  └──────────────────┘  │  (查询结果)       │                │
│                        │  - CSV 文件       │                │
│                        └──────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

## 📦 核心模块详解

### 1. 前端层 (Frontend)

#### 1.1 主要组件

**聊天界面组件**
- `ChatInterface.tsx` - 主聊天界面，支持流式消息展示
- `MessageContent.tsx` - 消息内容渲染
- `MessageActions.tsx` - 消息操作（复制、点赞、点踩等）
- `ThoughtChain.tsx` - AI 推理过程可视化
- `SemanticTokens.tsx` - 语义分词可视化展示

**数据可视化组件**
- `AutoChart.tsx` - 自动图表生成（根据数据自动选择图表类型）
- `DataChart.tsx` - 数据图表展示（ECharts 封装）
- `DataTable.tsx` - 数据表格展示

**管理页面组件**
- `DatabasePage.tsx` - 数据库管理页面
- `KnowledgePage.tsx` - 知识库管理页面
- `PromptPage.tsx` - Prompt 配置页面
- `MemoryPage.tsx` - 记忆管理页面
- `EvaluatePage.tsx` - 评测页面
- `TestingPage.tsx` - 测试页面

**其他组件**
- `SqlBlock.tsx` - SQL 代码块展示
- `AnalysisSummary.tsx` - 分析结果总结
- `QuickActions.tsx` - 快捷操作
- `WelcomeScreen.tsx` - 欢迎界面

#### 1.2 技术栈
- **框架**: React 19 + TypeScript
- **UI 库**: Ant Design 6
- **图表**: ECharts + echarts-for-react
- **构建工具**: Vite
- **状态管理**: React Hooks (useState, useCallback)

### 2. API 路由层 (Routes)

#### 2.1 聊天相关路由 (`app/routes/chat.py`)
- `POST /api/vanna/v2/chat_sse` - SSE 流式聊天接口
- `GET /chat` - 新版聊天界面
- `GET /classic` - 经典聊天界面
- `GET /app` - 前端应用入口

#### 2.2 查询分析路由 (`app/routes/analysis.py`)
- `POST /api/analysis/analyze` - 问题分析（语义分词、表选择、知识匹配）
- `POST /api/analysis/rewrite` - 问题改写
- `POST /api/analysis/tables` - 表选择
- `POST /api/analysis/knowledge` - 业务知识匹配

#### 2.3 知识库管理路由 (`app/routes/knowledge.py`)
- `GET /api/knowledge/time_rules` - 获取时间规则
- `POST /api/knowledge/time_rules` - 创建时间规则
- `GET /api/knowledge/business_terms` - 获取业务术语
- `POST /api/knowledge/business_terms` - 创建业务术语
- `GET /api/knowledge/field_mappings` - 获取字段映射
- `POST /api/knowledge/field_mappings` - 创建字段映射

#### 2.4 Prompt 管理路由 (`app/routes/prompt.py`)
- `GET /api/prompt/configs` - 获取 Prompt 配置列表
- `GET /api/prompt/configs/{id}` - 获取特定 Prompt 配置
- `POST /api/prompt/configs` - 创建 Prompt 配置
- `PUT /api/prompt/configs/{id}` - 更新 Prompt 配置
- `POST /api/prompt/activate` - 激活 Prompt 版本

#### 2.5 记忆管理路由 (`app/routes/memory.py`)
- `GET /api/memory/items` - 获取记忆项列表
- `GET /api/memory/items/{id}` - 获取特定记忆项
- `DELETE /api/memory/items/{id}` - 删除记忆项

#### 2.6 反馈评分路由 (`app/routes/feedback.py`)
- `POST /api/feedback/rate` - 评分反馈
- `GET /api/feedback/stats` - 反馈统计

#### 2.7 日志管理路由 (`app/routes/logs.py`)
- `GET /api/logs/conversations` - 获取对话列表
- `GET /api/logs/conversations/{id}` - 获取对话详情
- `DELETE /api/logs/conversations/{id}` - 删除对话

### 3. 核心服务层 (Services)

#### 3.1 Vanna Agent (`main.py`)
- **LLM Service**: DeepSeek API 集成
- **Tool Registry**: 工具注册和管理
  - `RunSqlTool`: SQL 查询执行工具
  - `VisualizeDataTool`: 数据可视化工具
- **User Resolver**: 用户识别和权限管理
- **Agent Memory**: 对话记忆管理

#### 3.2 查询分析服务 (`app/services/query_analyzer.py`)

**核心功能**:
1. **语义分词 (Semantic Tokenization)**
   - 识别时间规则（最近7天、本周等）
   - 识别指标（访问量、转化率等）
   - 识别维度（按日期、按省份等）
   - 识别图表提示（趋势、对比等）
   - 识别业务术语和字段映射

2. **问题改写 (Question Rewriting)**
   - 使用 LLM 改写用户问题，使其更清晰
   - 提取关键信息

3. **表选择 (Table Selection)**
   - 根据问题语义选择相关数据表
   - 提供选择理由

4. **业务知识匹配 (Knowledge Matching)**
   - 匹配相关的业务知识
   - 提供上下文信息

#### 3.3 业务知识库 (`app/services/business_knowledge.py`)

**知识类型**:
- **时间规则 (Time Rules)**: 自然语言时间表达规则
- **业务术语 (Business Terms)**: 业务领域术语定义
- **字段映射 (Field Mappings)**: 显示名称到数据库字段的映射

#### 3.4 Prompt 管理 (`app/services/prompt_manager.py`)

**功能**:
- Prompt 版本管理
- 动态 Prompt 构建
- Prompt 激活和切换
- Prompt 缓存

#### 3.5 RAG 知识库 (`app/services/rag_knowledge_base.py`)

**功能**:
- 向量嵌入和存储
- 相似度检索
- 混合检索（向量 + 关键词）
- 自动学习机制

#### 3.6 用户管理 (`app/services/enhanced_user_resolver.py`)

**功能**:
- 多源用户识别（请求头、Cookie、查询参数）
- 用户画像管理
- 用户组和权限管理
- 个性化上下文注入

#### 3.7 SQL 增强 (`app/services/sql_enhancer.py`)

**功能**:
- SQL 优化建议
- SQL 验证
- SQL 格式化

#### 3.8 对话增强 (`app/services/conversation_enhancer.py`)

**功能**:
- 对话上下文管理
- 多轮对话支持
- 对话摘要生成

### 4. 中间件层 (Middleware)

#### 4.1 日志中间件 (`app/middleware/logging.py`)
- 请求日志记录
- 响应日志记录
- 性能监控

#### 4.2 错误处理中间件 (`app/middleware/error_handler.py`)
- 统一异常捕获
- 错误响应格式化
- 错误日志记录

#### 4.3 个性化上下文中间件 (`app/middleware/personalized_context.py`)
- 用户画像注入
- 个性化上下文构建

### 5. 数据存储层

#### 5.1 业务数据库 (`data/data.db`)
- **gio_event**: 事件数据表
- **sales**: 销售数据表
- **dealer_store_info**: 经销商信息表
- 其他业务数据表

#### 5.2 系统数据库 (`logs/system.db`)
- **prompts**: Prompt 配置表
- **time_rules**: 时间规则表
- **business_terms**: 业务术语表
- **field_mappings**: 字段映射表
- **rag_qa_pairs**: RAG 问答对表
- **user_profiles**: 用户画像表
- **conversations**: 对话记录表
- **messages**: 消息记录表

#### 5.3 日志数据库 (`logs/logs.db`)
- **conversations**: 对话日志
- **messages**: 消息日志
- **feedback**: 反馈记录

#### 5.4 查询结果存储 (`vanna_data/`)
- CSV 格式的查询结果文件
- 按会话 ID 组织

## 🔄 核心工作流程

### 1. 用户查询处理流程

```
用户输入自然语言问题
    ↓
前端发送请求到 /api/vanna/v2/chat_sse
    ↓
中间件处理（日志、错误处理、个性化上下文）
    ↓
查询分析服务 (QueryAnalyzer)
    ├─ 语义分词 (识别时间、指标、维度等)
    ├─ 问题改写 (使用 LLM 优化问题)
    ├─ 表选择 (选择相关数据表)
    └─ 知识匹配 (匹配业务知识)
    ↓
Vanna Agent 处理
    ├─ 动态 Prompt 构建 (根据用户画像)
    ├─ LLM 生成 SQL
    ├─ 执行 SQL (RunSqlTool)
    └─ 生成可视化 (VisualizeDataTool)
    ↓
SSE 流式返回结果
    ├─ 推理步骤更新
    ├─ SQL 展示
    ├─ 数据表格
    └─ 图表可视化
    ↓
前端实时展示
    ├─ ThoughtChain (推理过程)
    ├─ SqlBlock (SQL 代码)
    ├─ DataTable (数据表格)
    └─ AutoChart (图表)
```

### 2. 语义分词流程

```
用户问题: "最近7天按日期统计访问量的变化趋势"
    ↓
语义分词处理
    ├─ "最近7天" → time_rule (时间规则)
    ├─ "按日期统计" → dimension (分析维度)
    ├─ "访问量" → metric (指标)
    └─ "变化趋势" → chart_hint (图表提示)
    ↓
生成语义分词结果
    ↓
前端可视化展示 (SemanticTokens 组件)
```

### 3. RAG 学习流程

```
用户反馈 (高分评分)
    ↓
RAG Learner 提取
    ├─ 提取问答对
    ├─ 质量评估
    └─ 去重检查
    ↓
向量化处理
    ├─ 生成嵌入向量
    └─ 存储到 RAG 知识库
    ↓
后续查询时检索
    ├─ 向量相似度搜索
    └─ 作为 Few-shot 示例注入 Prompt
```

## 🎯 核心特性

### 1. 智能对话
- ✅ 自然语言查询
- ✅ 流式响应 (SSE)
- ✅ 多轮对话支持
- ✅ 推理过程可视化

### 2. 数据可视化
- ✅ 自动图表类型选择
- ✅ 支持多种图表类型（折线图、柱状图、饼图等）
- ✅ 交互式图表（缩放、悬停等）

### 3. 语义理解
- ✅ 语义分词
- ✅ 问题改写
- ✅ 表选择
- ✅ 业务知识匹配

### 4. 知识管理
- ✅ 时间规则管理
- ✅ 业务术语管理
- ✅ 字段映射管理
- ✅ RAG 知识库

### 5. 个性化
- ✅ 用户画像
- ✅ 动态 Prompt
- ✅ 权限管理
- ✅ 个性化上下文

### 6. 学习优化
- ✅ 反馈学习
- ✅ RAG 自动学习
- ✅ SQL 优化建议
- ✅ 对话记忆

## 📊 技术栈总结

### 后端
- **框架**: FastAPI
- **AI 框架**: Vanna
- **LLM**: DeepSeek API
- **数据库**: SQLite
- **向量存储**: SQLite + 向量嵌入

### 前端
- **框架**: React 19 + TypeScript
- **UI 库**: Ant Design 6
- **图表**: ECharts
- **构建**: Vite
- **状态管理**: React Hooks

### 部署
- **服务器**: Uvicorn
- **端口**: 8000
- **协议**: HTTP/SSE

## 🔧 配置说明

### 环境变量
- `DEEPSEEK_API_KEY`: DeepSeek API 密钥（必需）
- `DEEPSEEK_MODEL`: 模型名称（默认: deepseek-chat）
- `DEEPSEEK_BASE_URL`: API 地址（默认: https://api.deepseek.com）
- `DATA_DB_PATH`: 业务数据库路径
- `LOGS_DB_PATH`: 日志数据库路径
- `SYSTEM_DB_PATH`: 系统数据库路径
- `VANNA_DATA_DIR`: 查询结果存储目录

## 📝 开发指南

### 启动服务
```bash
./start.sh
# 或
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 前端开发
```bash
cd frontend
npm install
npm run dev
```

### 运行测试
```bash
pytest
```

## 🚀 未来规划

- [ ] 支持更多数据库类型（MySQL、PostgreSQL 等）
- [ ] 增强 RAG 检索能力
- [ ] 支持更多图表类型
- [ ] 增强多轮对话能力
- [ ] 支持自定义工具扩展
- [ ] 性能优化和缓存增强






