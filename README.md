# Vanna Data Agent Demo

现代化的数据分析 Agent 应用，支持自然语言查询、SQL 生成、数据可视化和对话日志管理。

## 功能特性

- 💬 **智能对话界面** - 现代化的聊天式数据查询界面
- 📊 **数据可视化** - 自动生成图表（柱状图、折线图、饼图等）
- 📝 **对话日志** - 完整的对话历史记录和查看
- 🔍 **SQL 展示** - 自动提取和展示生成的 SQL 查询
- 🤖 **AI 推理过程** - 可视化 AI 的思考步骤

## 快速开始

### 1. 环境准备

确保已安装 Python 3.8+ 并激活虚拟环境：

```bash
# 激活虚拟环境
source venv/bin/activate

# 或使用其他虚拟环境管理工具
```

### 2. 配置环境变量

确保 `.env` 文件存在并包含必要的配置：

```bash
DEEPSEEK_API_KEY=your_api_key_here
```

可选配置：
```bash
DATA_DB_PATH=data/data.db
LOGS_DB_PATH=logs/logs.db
VANNA_DATA_DIR=vanna_data
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 3. 初始化数据库（首次运行）

```bash
# 初始化日志数据库
python scripts/init_logs_db.py

# 如果需要导入数据到数据库
python scripts/create_tables_and_import.py
```

### 4. 启动应用

**方式一：使用启动脚本（推荐）**

```bash
./start.sh
```

**方式二：手动启动**

```bash
# 激活虚拟环境
source venv/bin/activate

# 使用 uvicorn 启动
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**方式三：使用 Python 模块**

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 访问应用

启动成功后，在浏览器中访问：

- **新版聊天界面**: http://localhost:8000/chat (或 http://localhost:8000/app)
- **经典聊天界面**: http://localhost:8000/classic
- **日志列表**: http://localhost:8000/logs
- **Vanna 默认 UI**: http://localhost:8000/ （Vanna 提供的原始界面）

## 项目结构

```
vanna-demo/
├── app/                    # 应用核心代码
│   ├── config.py          # 配置管理
│   ├── routes/            # 路由
│   │   ├── chat.py        # 聊天界面
│   │   └── logs.py        # 日志管理
│   ├── services/          # 业务逻辑
│   ├── middleware/         # 中间件
│   └── utils/             # 工具函数
├── data/                   # 数据文件
├── logs/                   # 日志数据库
├── scripts/               # 工具脚本
├── tests/                 # 测试文件
├── main.py                # 应用入口
└── .env                   # 环境变量配置
```

## 使用说明

### 聊天界面

1. 访问 `/chat` 页面（新版）或 `/classic` 页面（经典版）
2. 在输入框中输入自然语言问题，例如：
   - "最近7天按省份统计访问量"
   - "显示各渠道的转化率对比"
   - "Top 10 访问量最高的页面"
3. AI 会自动生成 SQL、执行查询并展示结果
4. 可以查看推理过程、SQL 查询和可视化图表

### 日志管理

1. 访问 `/logs` 查看所有对话记录
2. 点击任意对话卡片查看详情
3. 支持搜索功能，可按摘要、用户ID、会话ID搜索

## 开发

### 运行测试

```bash
pytest
```

### 代码检查

```bash
# 检查 lint
ruff check .
```

## 注意事项

- 确保 `data/data.db` 存在且包含数据表
- 确保 `logs/logs.db` 已初始化
- DeepSeek API Key 必须正确配置
- 首次使用建议先运行初始化脚本

## 故障排查

### 启动失败

1. 检查 `.env` 文件中的 `DEEPSEEK_API_KEY` 是否配置
2. 确认虚拟环境已激活
3. 检查数据库文件是否存在

### 数据库错误

```bash
# 重新初始化日志数据库
python scripts/init_logs_db.py
```

### 端口被占用

```bash
# 使用其他端口启动
uvicorn main:app --reload --port 8001
```

