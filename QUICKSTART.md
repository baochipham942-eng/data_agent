# 快速启动指南

## 🚀 启动服务（3步）

### 步骤 1：打开终端

- **macOS**: 按 `⌘ + Space`，输入 "Terminal"，回车
- 或从菜单：应用程序 → 实用工具 → 终端

### 步骤 2：进入项目目录并启动

在终端中依次输入以下命令：

```bash
# 进入项目目录
cd /Users/linchen/vanna-demo

# 运行启动脚本
./start.sh
```

### 步骤 3：访问页面

启动成功后，在浏览器中打开：

- **✨ 新版聊天界面**: http://localhost:8000/chat (或 http://localhost:8000/app)
- **📜 经典聊天界面**: http://localhost:8000/classic
- **📝 日志列表**: http://localhost:8000/logs  
- **🔧 Vanna UI**: http://localhost:8000/

---

## 📋 完整操作示例

```bash
# 1. 打开终端后，输入：
cd /Users/linchen/vanna-demo

# 2. 运行启动脚本：
./start.sh

# 你会看到类似输出：
# 🚀 启动服务...
# 📍 访问地址:
#    - 新版聊天界面: http://localhost:8000/chat
#    - 经典聊天界面: http://localhost:8000/classic
#    - 日志列表: http://localhost:8000/logs
#    - Vanna UI: http://localhost:8000/
# 
# INFO:     Uvicorn running on http://0.0.0.0:8000

# 3. 保持终端窗口打开，在浏览器访问上述地址
```

---

## ⚠️ 常见问题

### 问题 1：提示 "Permission denied"

**解决方案**：
```bash
chmod +x start.sh
./start.sh
```

### 问题 2：提示 "No such file or directory"

**解决方案**：确保在正确的目录
```bash
pwd  # 查看当前目录，应该显示 /Users/linchen/vanna-demo
cd /Users/linchen/vanna-demo  # 如果不在，执行这行
```

### 问题 3：提示 "uvicorn: command not found"

**解决方案**：确保虚拟环境已激活
```bash
source venv/bin/activate
./start.sh
```

### 问题 4：端口被占用

**解决方案**：使用其他端口
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```
然后访问 http://localhost:8001/chat (新版) 或 http://localhost:8001/classic (经典版)

---

## 🛑 停止服务

在运行 `./start.sh` 的终端窗口中：
- 按 `Ctrl + C` 停止服务

---

## ✅ 验证服务是否运行

打开新的终端窗口，运行：

```bash
curl http://localhost:8000/chat | head -5
```

如果返回 HTML 内容，说明服务正常运行。

---

## 📱 在 VS Code 中运行

如果你使用 VS Code：

1. 打开终端：`View` → `Terminal` 或按 `` Ctrl + ` ``
2. 在终端中输入：
   ```bash
   cd /Users/linchen/vanna-demo
   ./start.sh
   ```

---

## 🎯 下一步

服务启动后：
1. 访问 http://localhost:8000/chat (新版界面) 或 http://localhost:8000/classic (经典界面)
2. 尝试输入问题，例如："最近7天按省份统计访问量"
3. 查看 AI 的推理过程和查询结果

