# Vercel 部署配置指南

## 📋 部署前检查清单

### 1. 环境变量配置

在 Vercel 项目设置中，必须配置以下环境变量：

**必需的环境变量：**
- `DEEPSEEK_API_KEY` - DeepSeek API 密钥（必需）

**可选的环境变量：**
- `DEEPSEEK_MODEL` - 模型名称（默认：`deepseek-chat`）
- `DEEPSEEK_BASE_URL` - API 基础 URL（默认：`https://api.deepseek.com`）

### 2. 配置步骤

1. 访问 Vercel 项目设置：https://vercel.com/[your-project]/settings/environment-variables
2. 点击 "Add New" 添加环境变量
3. 添加 `DEEPSEEK_API_KEY` 及其值
4. 选择环境（Production, Preview, Development）
5. 点击 "Save"
6. 重新部署项目

### 3. 项目结构

```
vanna-demo/
├── api/
│   └── index.py          # Vercel Serverless Function 入口点
├── app/                  # 应用代码
├── frontend/             # 前端代码
│   └── dist/             # 前端构建输出（需要构建）
├── main.py               # FastAPI 应用主文件
├── vercel.json           # Vercel 配置
└── requirements.txt      # Python 依赖
```

## 🔧 已知问题和限制

### 1. 数据库文件

**问题：** SQLite 数据库文件（`data/data.db`, `logs/system.db`）在 Vercel Serverless Functions 中无法持久化。

**解决方案：**
- 使用外部数据库服务（如 Supabase、PlanetScale、Neon）
- 或使用 Vercel 的 KV 存储（Redis）
- 或使用 `/tmp` 目录（临时，不持久）

### 2. 静态文件

**问题：** `frontend/dist/` 目录需要构建后才能部署。

**解决方案：**
- 在 Vercel 中配置构建命令：`cd frontend && npm install && npm run build`
- 或手动构建后提交到 Git（不推荐）

### 3. 文件系统限制

**问题：** Vercel Serverless Functions 的文件系统是只读的（除了 `/tmp`）。

**影响：**
- 无法写入数据库文件
- 无法写入日志文件
- 需要使用外部存储服务

## 🚀 部署步骤

### 方式1：通过 GitHub 自动部署（推荐）

1. 将代码推送到 GitHub
2. 在 Vercel 中导入 GitHub 仓库
3. 配置环境变量
4. Vercel 会自动部署

### 方式2：使用 Vercel CLI

```bash
# 安装 Vercel CLI
npm i -g vercel

# 登录
vercel login

# 部署
vercel

# 生产环境部署
vercel --prod
```

## 📝 故障排查

### 错误：500 INTERNAL_SERVER_ERROR

**可能原因：**
1. 环境变量未配置
2. 数据库文件不存在
3. 依赖安装失败

**解决方法：**
1. 检查 Vercel 日志：`vercel logs [deployment-url]`
2. 确认环境变量已配置
3. 检查 `requirements.txt` 是否包含所有依赖

### 错误：FUNCTION_INVOCATION_FAILED

**可能原因：**
1. 应用初始化失败
2. 导入错误
3. 配置错误

**解决方法：**
1. 查看 `api/index.py` 中的错误处理
2. 检查 Vercel 函数日志
3. 确认所有依赖都已安装

## 🔍 验证部署

部署成功后，访问以下 URL：

- 根路径：`https://[your-project].vercel.app/`
- 前端应用：`https://[your-project].vercel.app/app`
- API 端点：`https://[your-project].vercel.app/api/...`

## 📚 相关资源

- [Vercel Python 文档](https://vercel.com/docs/functions/serverless-functions/runtimes/python)
- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)
- [Vercel 环境变量配置](https://vercel.com/docs/concepts/projects/environment-variables)

