# 推理步骤动态显示优化

## 优化目标

根据用户反馈，6步推理不一定是必须的。系统应该**只显示实际有内容的步骤**，让界面更简洁、更直观。

## 实现策略

### 1. 流式处理时保持完整结构

在 `useChat.ts` 的流式处理过程中：
- 保持完整的6步结构（便于索引访问）
- 所有步骤初始状态为 `pending`
- 根据实际数据动态更新步骤状态和内容

### 2. 消息完成时过滤无内容步骤

在消息完成（`isStreaming = false`）时：
- 过滤掉没有实际内容的步骤
- 重新编号（1, 2, 3...）
- 只保留有意义的步骤

### 3. 历史消息加载时动态过滤

在 `EvaluatePage.tsx` 和 `useChat.ts` 的 `loadConversation` 中：
- 检查每个步骤是否有实际内容
- 根据实际数据判断是否应该显示
- 动态过滤并重新编号

## 步骤显示判断逻辑

### 理解问题步骤（rewrite）
- ✅ 显示条件：有语义分词（`semanticTokens`）或改写后问题
- ❌ 不显示：没有任何metadata

### 选择数据表步骤（tables）
- ✅ 显示条件：有选择的表（`selectedTables.length > 0`）
- ❌ 不显示：没有选择任何表

### 参考业务知识步骤（knowledge）
- ✅ 显示条件：有相关知识（`relevantKnowledge.length > 0`）
- ❌ 不显示：没有参考任何业务知识

### 生成SQL查询步骤（sql）
- ✅ 显示条件：有SQL查询（`sql` 存在）
- ❌ 不显示：没有生成SQL

### 执行查询获取数据步骤（execute）
- ✅ 显示条件：有查询结果（`tableData.length > 0`）
- ❌ 不显示：没有查询结果

### 生成分析结果步骤（analyze）
- ✅ 显示条件：有分析内容（`content` 存在）
- ❌ 不显示：没有分析内容

## 代码实现

### 1. 消息完成时过滤（`useChat.ts`）

```typescript
// 过滤掉没有实际内容的步骤，并重新编号
const filteredReasoning = reasoning
  .filter((step) => {
    // 根据步骤类型和实际数据判断是否有内容
    return (
      (step.stepType === 'rewrite' && (step.metadata?.semanticTokens?.length > 0 || step.detail)) ||
      (step.stepType === 'tables' && (step.metadata?.selectedTables?.length > 0 || step.detail)) ||
      (step.stepType === 'knowledge' && (step.metadata?.relevantKnowledge?.length > 0 || step.detail)) ||
      (step.stepType === 'sql' && finalSql) ||
      (step.stepType === 'execute' && tableData && tableData.length > 0) ||
      (step.stepType === 'analyze' && finalContent) ||
      (step.detail && step.detail.trim() && step.detail !== '分析完成' && step.detail.length > 5)
    );
  })
  .map((step, idx) => ({
    ...step,
    number: idx + 1, // 重新编号
  }));
```

### 2. 历史消息加载时过滤（`EvaluatePage.tsx`）

```typescript
reasoning = reasoning
  .filter((step: any) => {
    // 根据步骤类型和实际数据判断是否有内容
    const hasContent = 
      (step.stepType === 'rewrite' && (step.metadata?.semanticTokens?.length > 0 || step.detail)) ||
      (step.stepType === 'tables' && (step.metadata?.selectedTables?.length > 0 || step.detail)) ||
      (step.stepType === 'knowledge' && (step.metadata?.relevantKnowledge?.length > 0 || step.detail)) ||
      (step.stepType === 'sql' && sql) ||
      (step.stepType === 'execute' && tableData && tableData.length > 0) ||
      (step.stepType === 'analyze' && cleanContent) ||
      (step.detail && step.detail.trim() && step.detail !== '分析完成' && step.detail.length > 5);
    
    return hasContent;
  })
  .map((step: any, idx: number) => ({
    ...step,
    number: idx + 1, // 重新编号
  }));
```

## 用户体验优化

### 之前
- ❌ 强制显示6步，即使某些步骤没有实际内容
- ❌ 用户需要滚动查看所有步骤
- ❌ 界面显得冗余

### 优化后
- ✅ 只显示有实际内容的步骤
- ✅ 界面更简洁，重点突出
- ✅ 步骤编号动态调整（1, 2, 3...）
- ✅ 用户能快速理解系统做了什么

## 示例场景

### 场景1：完整分析（6步）
```
1. 理解问题（有语义分词）
2. 选择数据表（有选择的表）
3. 参考业务知识（有相关知识）
4. 生成SQL查询（有SQL）
5. 执行查询获取数据（有数据）
6. 生成分析结果（有内容）
```

### 场景2：简单查询（3步）
```
1. 生成SQL查询（有SQL）
2. 执行查询获取数据（有数据）
3. 生成分析结果（有内容）
```

### 场景3：无法回答（2步）
```
1. 理解问题（有语义分词）
2. 选择数据表（没有找到相关表）
```

## 向后兼容

- ✅ 历史消息仍然可以正常显示
- ✅ 如果后端返回了完整的reasoning，会进行过滤
- ✅ 如果后端没有返回reasoning，会根据实际数据动态构建

## 文件变更

### 修改的文件
- `frontend/src/hooks/useChat.ts` - 消息完成时过滤步骤
- `frontend/src/components/EvaluatePage.tsx` - 历史消息加载时过滤步骤

### 新增的工具函数
- `frontend/src/utils/reasoningUtils.ts` - 推理步骤工具函数（未来可复用）

## 测试建议

1. **测试完整分析流程**
   - 发送一个复杂查询，验证6步是否都显示

2. **测试简单查询**
   - 发送一个简单查询，验证只显示必要的步骤

3. **测试无法回答**
   - 发送一个无法回答的问题，验证只显示相关步骤

4. **测试历史消息**
   - 查看历史会话详情，验证步骤是否正确过滤









