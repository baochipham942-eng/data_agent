# 部署和重启指南

## 🔄 让修改生效的完整流程

### 情况1：修改了前端代码

**需要操作：**
1. ✅ 重新构建前端
2. ✅ 重启后端服务

### 情况2：修改了后端代码

**需要操作：**
1. ✅ 重启后端服务（如果使用 `--reload`，会自动重载）

### 情况3：修改了前后端代码

**需要操作：**
1. ✅ 重新构建前端
2. ✅ 重启后端服务

## 🚀 快速重启方案

### 方案1：使用一键重启脚本（推荐）

```bash
cd /Users/linchen/vanna-demo
chmod +x rebuild_and_restart.sh
./rebuild_and_restart.sh
```

这个脚本会：
- ✅ 停止现有服务
- ✅ 清理旧的构建文件
- ✅ 重新构建前端
- ✅ 检查后端代码
- ✅ 启动服务

### 方案2：手动操作

#### 步骤1：停止现有服务

如果服务正在运行，按 `Ctrl+C` 停止，或者：

```bash
# 查找并停止运行在8000端口的进程
lsof -ti:8000 | xargs kill -9
```

#### 步骤2：重新构建前端

```bash
cd /Users/linchen/vanna-demo/frontend
npm run build
cd ..
```

#### 步骤3：重启后端服务

```bash
cd /Users/linchen/vanna-demo
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 方案3：使用开发模式（仅前端修改时）

如果只修改了前端，可以使用开发模式，无需构建：

#### 终端1：启动后端

```bash
cd /Users/linchen/vanna-demo
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 终端2：启动前端开发服务器

```bash
cd /Users/linchen/vanna-demo/frontend
npm run dev
```

然后访问：http://localhost:3000/app

**注意**：这种方式只在开发时使用，生产环境需要使用构建后的文件。

## 📋 检查清单

### 前端构建检查

```bash
# 检查构建文件是否存在
ls -la frontend/dist/

# 应该看到：
# - index.html
# - assets/ 目录
```

### 后端服务检查

```bash
# 检查服务是否运行
curl http://localhost:8000/api/server/status

# 检查端口是否被占用
lsof -i :8000
```

### 验证修改是否生效

1. **前端修改验证**：
   - 打开浏览器开发者工具（F12）
   - 查看 Network 标签
   - 刷新页面，检查加载的 JS/CSS 文件时间戳是否更新
   - 或者硬刷新（Ctrl+Shift+R 或 Cmd+Shift+R）

2. **后端修改验证**：
   - 查看终端日志，确认服务已重启
   - 测试相关 API 端点
   - 检查功能是否按预期工作

## 🔧 常见问题

### 问题1：前端构建失败

```bash
# 清理缓存并重新安装依赖
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

### 问题2：端口被占用

```bash
# 方法1：杀死占用端口的进程
lsof -ti:8000 | xargs kill -9

# 方法2：使用其他端口
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### 问题3：修改后仍然看到旧代码

**前端：**
- 清除浏览器缓存（Ctrl+Shift+Delete）
- 硬刷新页面（Ctrl+Shift+R）
- 检查 `frontend/dist/` 目录是否更新

**后端：**
- 确认服务已重启（查看终端日志）
- 如果使用 `--reload`，代码更改会自动重载
- 检查是否有多个服务实例在运行

### 问题4：构建文件没有更新

```bash
# 强制清理并重新构建
cd frontend
rm -rf dist node_modules/.vite
npm run build
```

## 📝 推荐的开发工作流

### 日常开发

1. **修改前端代码**：
   - 使用 `npm run dev` 启动开发服务器（自动热重载）
   - 访问 http://localhost:3000/app

2. **修改后端代码**：
   - 使用 `uvicorn --reload` 启动（自动重载）
   - 代码更改后自动生效

3. **测试时**：
   - 构建前端：`cd frontend && npm run build`
   - 重启后端：按 `Ctrl+C` 然后重新运行 `uvicorn`

### 部署到生产

```bash
# 1. 重新构建前端
cd frontend
npm run build

# 2. 检查构建结果
ls -la dist/

# 3. 重启后端服务
# （根据你的部署方式，可能是 systemd、supervisor、docker 等）
```

## ✅ 快速验证清单

部署后，检查以下功能是否正常：

- [ ] 访问 http://localhost:8000/app 能正常加载
- [ ] 发送查询问题能正常响应
- [ ] 推理步骤显示正常（只显示有内容的步骤）
- [ ] 快捷操作按钮显示正常（如果有查询结果）
- [ ] 会话详情页显示完整信息
- [ ] 调试信息（RAG/Memory）正确显示

## 🎯 一键重启脚本使用说明

```bash
# 给脚本添加执行权限
chmod +x rebuild_and_restart.sh

# 运行脚本
./rebuild_and_restart.sh
```

脚本会自动完成：
1. 停止现有服务
2. 清理旧的构建文件
3. 重新构建前端
4. 检查后端代码
5. 启动服务

**建议**：每次修改代码后，运行此脚本确保所有更改生效。









