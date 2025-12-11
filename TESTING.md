# 自动化测试指南

## 📋 概述

本项目已配置完整的自动化测试框架，使用 `pytest` 作为测试运行器。测试覆盖了以下方面：

- ✅ 配置管理
- ✅ 核心服务（QueryAnalyzer, PromptManager, BusinessKnowledge, AgentMemory）
- ✅ 中间件（错误处理）
- ✅ API 路由（集成测试）
- ✅ 端到端流程

## 🚀 快速开始

### 安装依赖

确保已安装测试相关依赖：

```bash
pip install pytest pytest-asyncio pytest-cov
```

### 运行测试

```bash
# 运行所有测试
pytest

# 或使用脚本
./scripts/run_tests.sh
```

## 📊 测试分类

### 1. 单元测试 (Unit Tests)

测试单个服务或函数的功能：

```bash
# 运行所有单元测试
pytest -m unit

# 运行特定服务的测试
pytest tests/test_query_analyzer.py
pytest tests/test_prompt_manager.py
pytest tests/test_business_knowledge.py
pytest tests/test_agent_memory.py
```

### 2. 集成测试 (Integration Tests)

测试多个组件之间的协作：

```bash
pytest -m integration
pytest tests/test_integration.py
```

### 3. API 测试

测试 API 端点：

```bash
pytest -m api
pytest tests/test_api_routes.py
```

### 4. 端到端测试 (E2E Tests)

测试完整的业务流程：

```bash
pytest -m e2e
```

### 5. 服务层测试

测试服务层功能：

```bash
pytest -m service
```

## 🎯 测试标记

使用 `-m` 选项运行特定标记的测试：

```bash
# 只运行单元测试
pytest -m unit

# 运行集成测试，但跳过慢测试
pytest -m "integration and not slow"

# 运行所有标记的测试
pytest -m "unit or integration"
```

## 📈 测试覆盖率

生成测试覆盖率报告：

```bash
# 安装覆盖率工具
pip install pytest-cov

# 运行测试并生成覆盖率报告
pytest --cov=app --cov-report=html

# 查看报告
open htmlcov/index.html  # macOS
# 或
xdg-open htmlcov/index.html  # Linux
```

## 🔧 测试 Fixtures

项目提供了多个实用的测试 fixtures（在 `tests/conftest.py` 中定义）：

- `temp_dir` - 临时目录
- `temp_db_path` - 临时数据库文件路径
- `system_db_path` - 系统数据库路径
- `data_db_path` - 测试数据数据库（包含测试表和数据）
- `mock_llm_service` - 模拟的 LLM 服务
- `setup_test_env` - 自动设置测试环境变量

## 📝 编写新测试

### 基本结构

```python
import pytest

@pytest.mark.service
class TestMyService:
    """我的服务测试"""
    
    def test_basic_function(self, system_db_path):
        # Arrange
        service = MyService(system_db_path)
        
        # Act
        result = service.do_something()
        
        # Assert
        assert result is not None
```

### 异步测试

```python
@pytest.mark.asyncio
async def test_async_function(memory):
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

## 🐛 调试测试

### 显示详细输出

```bash
pytest -v          # 详细模式
pytest -vv         # 更详细
pytest -s          # 显示 print 输出
```

### 只运行失败的测试

```bash
pytest --lf        # 只运行上次失败的测试
pytest --ff        # 先运行失败的，再运行其他的
```

### 进入调试器

```bash
pytest --pdb       # 失败时进入调试器
pytest --pdb-trace # 在测试开始时就进入调试器
```

### 运行特定测试

```bash
# 运行特定文件
pytest tests/test_query_analyzer.py

# 运行特定测试类
pytest tests/test_query_analyzer.py::TestQueryAnalyzer

# 运行特定测试方法
pytest tests/test_query_analyzer.py::TestQueryAnalyzer::test_semantic_tokenize_basic
```

## 📋 测试清单

### 已完成 ✅

- [x] 测试基础设施（conftest.py, fixtures）
- [x] 配置管理测试
- [x] QueryAnalyzer 服务测试
- [x] PromptManager 服务测试
- [x] BusinessKnowledge 服务测试
- [x] AgentMemory 服务测试
- [x] 中间件测试
- [x] 集成测试
- [x] 端到端测试框架

### 待完善 🔄

- [ ] 更多 API 端点测试
- [ ] SQL 增强服务测试
- [ ] 对话增强器测试
- [ ] 性能测试
- [ ] 负载测试
- [ ] 前端组件测试（如果适用）

## 🔍 最佳实践

1. **测试独立性**：每个测试应该是独立的，不依赖其他测试
2. **快速执行**：单元测试应该快速运行
3. **清晰命名**：测试名称应该清楚描述测试内容
4. **AAA 模式**：使用 Arrange-Act-Assert 组织测试代码
5. **Mock 外部依赖**：对 LLM API 等外部服务使用 mock
6. **测试边界情况**：测试正常情况、边界情况和错误情况

## 📚 更多信息

详细文档请参考：[tests/README.md](tests/README.md)

## 🆘 故障排查

### 测试失败常见问题

1. **数据库路径错误**：确保测试使用临时数据库
2. **环境变量缺失**：检查 `DEEPSEEK_API_KEY` 等环境变量
3. **模块导入错误**：检查 Python 路径设置
4. **异步测试问题**：确保使用 `@pytest.mark.asyncio` 标记

### 获取帮助

```bash
# 查看 pytest 帮助
pytest --help

# 查看测试收集情况（不运行测试）
pytest --collect-only
```

## 🎉 贡献测试

欢迎为项目添加更多测试！请确保：

1. 测试通过所有检查
2. 遵循项目的测试风格
3. 添加适当的测试标记
4. 更新相关文档









