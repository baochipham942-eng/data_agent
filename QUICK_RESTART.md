# 🚀 快速重启指南

## 修改了代码后，如何让修改生效？

### ✅ 答案：是的，需要重新构建前端和重启后端

## 📋 快速操作步骤

### 方式1：一键重启（最简单）

```bash
cd /Users/linchen/vanna-demo
./rebuild_and_restart.sh
```

这个脚本会自动：
- 🛑 停止现有服务
- 📦 重新构建前端
- 🚀 重启后端服务

### 方式2：手动操作

#### 1. 停止当前服务

如果服务正在运行，在运行服务的终端窗口按 `Ctrl+C`

或者：
```bash
lsof -ti:8000 | xargs kill -9
```

#### 2. 重新构建前端

```bash
cd /Users/linchen/vanna-demo/frontend
npm run build
cd ..
```

#### 3. 重启后端

```bash
cd /Users/linchen/vanna-demo
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 🔍 如何确认修改已生效？

### 前端修改验证

1. **硬刷新浏览器**
   - Mac: `Cmd + Shift + R`
   - Windows/Linux: `Ctrl + Shift + R`

2. **清除浏览器缓存**
   - 打开开发者工具（F12）
   - 右键刷新按钮 → 选择"清空缓存并硬性重新加载"

3. **检查构建时间**
   ```bash
   ls -lh frontend/dist/assets/*.js
   # 查看文件的修改时间，应该是刚刚构建的
   ```

### 后端修改验证

1. **查看终端日志**
   - 如果看到 "Application startup complete" 说明已重启
   - 如果使用 `--reload`，代码修改后会自动重载（会有提示）

2. **测试功能**
   - 发送一个查询，检查功能是否按预期工作

## ⚠️ 重要提示

### 前端修改

- **必须构建**：React/TypeScript 代码必须构建成 JavaScript 才能运行
- **构建位置**：`frontend/dist/` 目录
- **服务位置**：后端服务会从 `frontend/dist/` 目录提供静态文件

### 后端修改

- **自动重载**：如果使用 `uvicorn --reload`，Python 代码修改后会自动重载
- **手动重启**：如果修改了 `main.py` 的导入部分，可能需要手动重启
- **中间件修改**：中间件修改后需要重启服务

## 🎯 推荐的开发流程

### 修改了前端代码

```bash
# 终端1：启动后端（保持运行）
cd /Users/linchen/vanna-demo
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 终端2：启动前端开发服务器（自动热重载）
cd /Users/linchen/vanna-demo/frontend
npm run dev
# 访问 http://localhost:3000/app
```

### 修改了后端代码

```bash
# 使用 --reload 参数，代码修改后自动重载
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 准备测试/部署

```bash
# 使用一键重启脚本
./rebuild_and_restart.sh
```

## 📝 常见问题

**Q: 为什么修改了前端代码，浏览器还显示旧的？**
A: 需要重新构建前端，并硬刷新浏览器（清除缓存）

**Q: 为什么修改了后端代码，功能没变？**
A: 需要重启服务，或者使用 `--reload` 参数

**Q: 我可以只构建前端不重启后端吗？**
A: 可以，但建议一起重启，确保前后端同步

**Q: 开发时每次都要构建吗？**
A: 不需要，可以使用 `npm run dev` 开发模式（自动热重载）









