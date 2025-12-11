# 语义拆解和图表类型推荐修复

## 🐛 问题描述

1. **复合词拆分问题**：`"变化趋势"` 被拆分成 `"变化"` 和 `"趋势"` 两个独立的语义token，应该作为一个整体处理
2. **图表类型未应用**：虽然 hover 到 `"变化"` 和 `"趋势"` 时都提示折线图，但实际绘制的图表没有默认选中折线图

## ✅ 修复方案

### 1. 复合词优先匹配（后端）

**文件**: `app/services/query_analyzer.py`

**修改**:
- 在 `chart_keywords` 字典中，将复合词放在前面（Python字典在3.7+保持插入顺序）
- 添加了以下复合词：
  - `"变化趋势"` → 折线图
  - `"趋势变化"` → 折线图
  - `"走势变化"` → 折线图
  - `"趋势走势"` → 折线图
  - `"分布情况"` → 饼图
  - `"占比分布"` → 饼图
  - 等等

**原理**:
- Python 字典在匹配时会按照定义顺序遍历
- 复合词定义在前，单个词定义在后
- 使用 `question.find(keyword)` 优先匹配更长的复合词

**测试验证**:
```python
result = analyzer.semantic_tokenize('最近7天按日期统计访问量的变化趋势')
# 结果：只识别出一个 token: {'text': '变化趋势', 'type': 'chart_hint', ...}
```

### 2. 图表类型推荐传递（前端）

**文件**: 
- `frontend/src/components/AutoChart.tsx`
- `frontend/src/components/MessageContent.tsx`

**修改**:

1. **AutoChart 组件**:
   - 添加 `recommendedChartType` prop，接收从语义分析中得到的图表类型推荐
   - 修改 `recommendedType` 逻辑，优先使用传入的推荐类型
   - 只有当没有推荐类型时，才使用数据特征判断（日期格式、数据量等）

2. **MessageContent 组件**:
   - 添加 `extractChartTypeFromTokens` 函数，从语义token中提取图表类型推荐
   - 在 `renderChart` 函数中提取推荐类型并传递给 `AutoChart`

**数据流**:
```
后端语义分析
  → 生成 chart_hint token (knowledge.value = 'line')
  → 存储在 reasoning[0].metadata.semanticTokens
  → 前端 MessageContent 提取
  → 传递给 AutoChart.recommendedChartType
  → AutoChart 优先使用推荐类型
```

## 📊 效果

### 修复前

- `"变化趋势"` 被拆分为两个token：`"变化"` (chart_hint: line) 和 `"趋势"` (chart_hint: line)
- 图表默认类型基于数据特征判断，可能不是折线图

### 修复后

- `"变化趋势"` 作为一个完整的token识别：`"变化趋势"` (chart_hint: line)
- 图表默认选中折线图（如果语义分析推荐了折线图）

## 🔍 测试验证

### 后端测试

```python
from app.services.query_analyzer import QueryAnalyzer

analyzer = QueryAnalyzer(...)
result = analyzer.semantic_tokenize('最近7天按日期统计访问量的变化趋势')

chart_tokens = [t for t in result if t['type'] == 'chart_hint']
# 应该只有1个token: {'text': '变化趋势', 'knowledge': {'value': 'line'}}
```

### 前端测试

1. 在聊天界面输入：`"最近7天按日期统计访问量的变化趋势"`
2. 查看语义拆解：应该只显示一个绿色的 `"变化趋势"` token
3. 查看图表：应该默认选中折线图

## 📝 相关文件

- `app/services/query_analyzer.py` - 语义拆解逻辑
- `frontend/src/components/AutoChart.tsx` - 图表组件
- `frontend/src/components/MessageContent.tsx` - 消息内容组件
- `frontend/src/types/index.ts` - 类型定义

## 🔮 未来优化

1. **更多复合词**：可以根据用户反馈添加更多复合词
2. **智能匹配**：使用更智能的匹配算法，如最长匹配
3. **上下文感知**：考虑上下文来确定图表类型推荐









