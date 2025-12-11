# 单 Agent 架构优化总结

## 📋 优化概述

本次优化增强了现有的单 Agent 架构，实现了用户级别的个性化配置和动态 Prompt 生成。

## 🎯 优化目标

1. ✅ **增强用户识别**：支持多种方式识别用户（请求头、Cookie、查询参数）
2. ✅ **动态 System Prompt**：根据用户画像和偏好动态调整 Prompt
3. ✅ **用户级别工具权限控制**：支持不同用户组对工具的访问权限
4. ✅ **个性化上下文**：在请求处理时注入用户画像信息

## 🔧 实现内容

### 1. 增强用户解析器 (`EnhancedUserResolver`)

**文件**: `app/services/enhanced_user_resolver.py`

**功能**:
- 支持从多个来源识别用户：
  - 请求头: `X-User-ID`, `X-Email`
  - Cookie: `vanna_email`, `user_id`
  - 查询参数: `user_id`
- 自动获取用户画像信息
- 根据用户画像确定用户组（admin, expert, user, guest）
- 返回包含用户元数据的 User 对象

**使用方式**:
```python
from app.services.enhanced_user_resolver import EnhancedUserResolver

enhanced_user_resolver = EnhancedUserResolver(
    user_profile_service=user_profile_service,
)
```

### 2. 动态 Prompt 构建器 (`DynamicPromptBuilder`)

**文件**: `app/services/dynamic_prompt_builder.py`

**功能**:
- 根据用户画像动态生成 System Prompt
- 考虑用户的专业级别（beginner, intermediate, expert）
- 考虑用户的图表偏好
- 考虑用户关注的维度

**个性化增强项**:
- **专业级别调整**：
  - Beginner: 更详细的解释，通俗易懂
  - Expert: 使用专业术语，深入分析
- **偏好设置**：根据用户的图表类型偏好调整建议
- **关注维度**：优先考虑用户常用的维度

### 3. 工具权限管理器 (`ToolPermissionManager`)

**文件**: `app/services/tool_permission_manager.py`

**功能**:
- 管理不同用户组的工具访问权限
- 支持允许列表和限制列表
- 默认权限配置：
  - `admin`: 所有工具
  - `expert/user/guest`: 基础工具（RunSqlTool, VisualizeDataTool）

**使用方式**:
```python
from app.services.tool_permission_manager import get_tool_permission_manager

permission_manager = get_tool_permission_manager()
if permission_manager.check_tool_access(user, "RunSqlTool"):
    # 允许访问
    pass
```

### 4. 个性化上下文中间件

**文件**: `app/middleware/personalized_context.py`

**功能**:
- 在请求处理时注入用户画像信息
- 为 Agent 提供个性化上下文
- 支持用户级别的定制化体验

## 📊 架构变更

### 优化前

```
用户请求 → SimpleUserResolver → Agent (静态配置) → 响应
```

### 优化后

```
用户请求 
  → EnhancedUserResolver (获取用户画像)
  → PersonalizedContextMiddleware (注入个性化上下文)
  → Agent (利用用户元数据)
  → 动态 Prompt 构建
  → 响应
```

## 🔄 工作流程

1. **用户识别阶段**:
   - `EnhancedUserResolver` 从多个来源识别用户
   - 获取用户画像信息
   - 确定用户组和权限

2. **个性化配置阶段**:
   - `DynamicPromptBuilder` 根据用户画像生成个性化 Prompt
   - `ToolPermissionManager` 检查工具访问权限
   - 个性化上下文中间件注入用户信息

3. **请求处理阶段**:
   - Agent 使用用户元数据
   - 根据用户专业级别调整回答风格
   - 考虑用户偏好和关注维度

## 📁 文件结构

```
app/
├── services/
│   ├── enhanced_user_resolver.py      # 增强用户解析器
│   ├── dynamic_prompt_builder.py      # 动态 Prompt 构建器
│   └── tool_permission_manager.py     # 工具权限管理器
├── middleware/
│   └── personalized_context.py        # 个性化上下文中间件
└── ...
```

## 🎨 用户画像集成

用户画像信息会自动注入到 Agent 处理流程中：

- **专业级别** (`expertise_level`): beginner, intermediate, expert
- **偏好设置** (`preferences`): 
  - `preferred_chart_type`: 偏好的图表类型
- **关注维度** (`focus_dimensions`): 用户常用的分析维度

## 🔐 权限控制

### 用户组定义

- **admin**: 管理员，拥有所有权限
- **expert**: 专家用户，可以使用高级功能
- **user**: 普通用户，基础功能
- **guest**: 访客用户，基础功能

### 权限配置

可以在 `ToolPermissionManager` 中配置不同用户组的权限：

```python
permission_manager.set_group_permissions(
    group="expert",
    allowed_tools=["RunSqlTool", "VisualizeDataTool", "AdvancedTool"],
    restricted_tools=[],
)
```

## 📝 使用示例

### 1. 前端传递用户ID

```typescript
// frontend/src/utils/api.ts
const headers = {
  'Content-Type': 'application/json',
  'X-User-ID': userId,  // 传递用户ID
};
```

### 2. 获取用户画像

```python
# 后端自动获取
profile = await user_profile_service.get_profile(user_id)
```

### 3. 动态生成 Prompt

```python
# 自动根据用户画像生成
prompt = await dynamic_prompt_builder.build_system_prompt(user)
```

## ⚡ 性能考虑

1. **缓存机制**:
   - 用户画像信息会被缓存
   - Prompt 构建结果可以缓存

2. **异步处理**:
   - 用户画像获取是异步的
   - 不阻塞请求处理

3. **降级策略**:
   - 如果获取用户画像失败，使用默认配置
   - 不影响核心功能

## 🔮 未来扩展

1. **更多个性化选项**:
   - 用户特定的系统 Prompt 模板
   - 用户级别的工具配置

2. **A/B 测试**:
   - 不同用户组使用不同的 Prompt 版本
   - 测试不同的策略效果

3. **实时学习**:
   - 根据用户反馈调整个性化策略
   - 动态优化 Prompt 生成

## 📚 相关文档

- [用户画像服务](../app/services/agent_memory.py#L622)
- [Prompt 管理](../app/services/prompt_manager.py)
- [用户识别机制](../app/services/enhanced_user_resolver.py)









