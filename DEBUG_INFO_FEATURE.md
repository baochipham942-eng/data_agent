# 评测详情页调试信息展示功能

## ✅ 已完成

### 1. 前端展示
- ✅ 在评测详情页添加了调试信息展示区域
- ✅ 显示 RAG 使用情况（是否使用、使用的示例数量）
- ✅ 显示 Memory 使用情况（是否使用、使用的示例数量）
- ✅ 显示使用的 Few-shot 示例列表（来源：RAG/Memory）

### 2. 后端支持
- ✅ 修改了 `FewShotSelector.select_examples()` 方法，支持返回调试信息
- ✅ 修改了会话详情 API，从 `extra_json` 中提取调试信息

## ✅ 已实现：调试信息记录

### 已完成的修改

#### 1. ✅ 修改了 `app/middleware/logging.py`

- ✅ 修改了 `register_logging_middleware` 函数，接受 `few_shot_selector` 参数
- ✅ 在保存 assistant 消息时，调用 `FewShotSelector.select_examples(return_debug_info=True)` 获取调试信息
- ✅ 将调试信息保存到 `extra_json` 中，包括：
  - `debug_info`: RAG 和 Memory 使用情况
  - `few_shot_examples`: 使用的 Few-shot 示例列表（最多3个）

#### 2. ✅ 修改了 `main.py`

- ✅ 在注册 logging middleware 时，传递 `few_shot_selector` 实例

#### 3. ✅ 修改了 `app/services/sql_enhancer.py`

- ✅ 更新了 `init_sql_enhancer` 函数，接受 `rag_knowledge_base` 参数
- ✅ 在初始化 `FewShotSelector` 时传递 RAG 知识库实例

### 实现细节

在 `logging_middleware` 中，当保存 assistant 消息时：
1. 获取用户问题（`user_msg`）
2. 如果 `few_shot_selector` 可用且用户问题存在，调用 `select_examples(return_debug_info=True)`
3. 提取调试信息：
   - `debug_info.rag_used`: 是否使用了 RAG
   - `debug_info.rag_count`: RAG 示例数量
   - `debug_info.memory_used`: 是否使用了 Memory
   - `debug_info.memory_count`: Memory 示例数量
4. 保存 Few-shot 示例预览（最多3个，包含问题、SQL预览、来源、相似度）
5. 将所有调试信息保存到 `extra_json` 中

### 异常处理

- 如果获取调试信息失败，不会影响主流程，只记录警告日志
- 向后兼容：如果调试信息不存在，前端会显示"未使用"

### 数据结构

调试信息的数据结构：

```json
{
  "debug_info": {
    "rag_used": true,
    "rag_count": 2,
    "memory_used": true,
    "memory_count": 1
  },
  "few_shot_examples": [
    {
      "question": "用户问题示例",
      "sql": "SELECT ...",
      "source": "rag",
      "similarity": 0.85,
      "score": 4.5
    }
  ],
  "selected_tables": ["gio_event", "sales"],
  "semantic_tokens": [...]
}
```

## 🎯 使用说明

### 查看调试信息

1. 打开"会话历史评测"页面
2. 点击任意会话记录的"详情"按钮
3. 在会话详情中，每个 assistant 消息下方会显示：
   - **RAG 使用情况**：是否使用了 RAG 知识库，使用了多少个示例
   - **Memory 使用情况**：是否使用了 Agent Memory，使用了多少个示例
   - **Few-shot 示例**：显示使用的示例列表（最多3个）

### 调试信息说明

- **RAG: X 个示例**：从 RAG 知识库中检索到的高质量示例数量
- **Memory: X 个示例**：从 Agent Memory 中检索到的历史案例数量
- **Few-shot 示例**：实际使用的前几个示例，包括：
  - 来源标签（📚 RAG 或 💾 Memory）
  - 示例问题（前50个字符）
  - 相似度评分

## 📋 相关文件

- `app/services/sql_enhancer.py` - FewShotSelector（已支持返回调试信息）
- `app/routes/chat.py` - 会话详情 API（已支持提取调试信息）
- `app/middleware/logging.py` - **待修改**：记录调试信息到 extra_json
- `frontend/src/components/EvaluatePage.tsx` - 评测详情页（已支持展示调试信息）

## ⚠️ 注意事项

1. **性能影响**：在 logging middleware 中调用 `FewShotSelector` 可能会增加响应时间。建议：
   - 异步调用
   - 添加缓存机制
   - 只在需要时调用（可通过配置开关控制）

2. **数据一致性**：调试信息应该在 SQL 生成时记录，而不是在消息保存时。但目前 Vanna Agent 是黑盒，我们只能通过中间件记录。

3. **向后兼容**：对于历史会话，`debug_info` 可能不存在，前端已经做了兼容处理（显示"未使用"）。

