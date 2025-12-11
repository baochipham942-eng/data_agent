# 测试文档

## 测试概述

本项目使用 `pytest` 作为测试框架，包含以下类型的测试：

- **单元测试**：测试单个服务或函数的功能
- **集成测试**：测试多个组件之间的协作
- **端到端测试**：测试完整的业务流程

## 测试结构

```
tests/
├── conftest.py                          # 测试配置和共享 fixtures
├── test_config.py                       # 配置管理测试
├── test_conversation_log.py             # 会话日志测试
├── test_query_analyzer.py               # 查询分析器测试
├── test_prompt_manager.py               # Prompt 管理器测试
├── test_business_knowledge.py           # 业务知识库测试
├── test_agent_memory.py                 # Agent Memory 测试
├── test_middleware.py                   # 中间件测试
├── test_api_routes.py                   # API 路由测试
├── test_integration.py                  # 集成测试
├── test_enhanced_user_resolver.py       # 增强用户解析器测试 ⭐
├── test_dynamic_prompt_builder.py       # 动态 Prompt 构建器测试 ⭐
├── test_tool_permission_manager.py      # 工具权限管理器测试 ⭐
├── test_agent_optimization_integration.py # Agent 优化集成测试 ⭐
└── README.md                            # 本文档
```

⭐ 表示新增的 Agent 优化组件测试

## 运行测试

### 运行所有测试

```bash
pytest
```

### 运行特定类型的测试

```bash
# 只运行单元测试
pytest -m unit

# 只运行集成测试
pytest -m integration

# 只运行端到端测试
pytest -m e2e

# 只运行服务层测试
pytest -m service

# 只运行 API 测试
pytest -m api
```

### 运行特定文件

```bash
pytest tests/test_query_analyzer.py
```

### 运行特定测试用例

```bash
pytest tests/test_query_analyzer.py::TestQueryAnalyzer::test_semantic_tokenize_basic
```

### 显示详细输出

```bash
pytest -v
```

### 显示覆盖率

```bash
# 需要先安装 coverage
pip install pytest-cov

# 运行测试并生成覆盖率报告
pytest --cov=app --cov-report=html
```

## 测试标记

测试用例使用以下标记进行分类：

- `@pytest.mark.unit` - 单元测试
- `@pytest.mark.integration` - 集成测试
- `@pytest.mark.e2e` - 端到端测试
- `@pytest.mark.service` - 服务层测试
- `@pytest.mark.api` - API 端点测试
- `@pytest.mark.slow` - 运行较慢的测试（可选跳过）

### 跳过慢测试

```bash
pytest -m "not slow"
```

## 测试 Fixtures

### 常用 Fixtures

- `temp_dir` - 临时目录路径
- `temp_db_path` - 临时数据库文件路径
- `system_db_path` - 系统数据库路径
- `data_db_path` - 测试数据数据库路径（包含测试表和数据）
- `mock_llm_service` - 模拟的 LLM 服务

### 使用 Fixtures

```python
def test_example(system_db_path, data_db_path):
    # 使用 fixtures
    analyzer = QueryAnalyzer(
        data_db_path=data_db_path,
        knowledge_db_path=system_db_path,
    )
    # ...
```

## 编写测试

### 基本测试结构

```python
import pytest

@pytest.mark.service
class TestMyService:
    """我的服务测试"""
    
    def test_basic_functionality(self, fixture1, fixture2):
        """测试基本功能"""
        # Arrange（准备）
        service = MyService(fixture1)
        
        # Act（执行）
        result = service.do_something()
        
        # Assert（断言）
        assert result is not None
        assert result.status == "success"
```

### 异步测试

```python
@pytest.mark.asyncio
async def test_async_function(memory):
    """测试异步函数"""
    result = await memory.add_text_memory("content")
    assert result is not None
```

### 参数化测试

```python
@pytest.mark.parametrize("input,expected", [
    ("input1", "expected1"),
    ("input2", "expected2"),
])
def test_multiple_cases(input, expected):
    assert process(input) == expected
```

## 测试最佳实践

1. **独立性**：每个测试应该是独立的，不依赖其他测试的执行顺序
2. **可重复性**：测试应该可以重复运行，产生相同的结果
3. **快速执行**：单元测试应该尽可能快地执行
4. **清晰命名**：测试名称应该清楚地描述测试的内容
5. **AAA 模式**：使用 Arrange-Act-Assert 模式组织测试代码
6. **Mock 外部依赖**：对于外部服务（如 LLM API），使用 mock 避免真实调用

## 持续集成

### GitHub Actions 示例

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.14'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
        run: pytest --cov=app --cov-report=xml
```

## 故障排查

### 测试失败常见原因

1. **数据库路径问题**：确保测试使用临时数据库，不会影响实际数据
2. **环境变量缺失**：检查是否需要设置 `DEEPSEEK_API_KEY` 等环境变量
3. **模块导入错误**：检查 `PYTHONPATH` 或 `sys.path` 设置
4. **异步测试问题**：确保异步测试使用 `@pytest.mark.asyncio` 标记

### 调试测试

```bash
# 在失败时进入调试器
pytest --pdb

# 显示打印输出
pytest -s

# 只运行失败的测试
pytest --lf
```

## 下一步

- [ ] 添加更多单元测试覆盖
- [ ] 完善 API 端点测试
- [ ] 添加性能测试
- [ ] 集成代码覆盖率报告
- [ ] 设置 CI/CD 自动测试

