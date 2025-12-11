# 🚀 立即重启 - 让修改生效

## ✅ 是的，需要重新构建前端和重启后端

## 📋 操作步骤

### 第1步：停止当前服务

在运行服务的终端窗口按 `Ctrl+C`

或者执行：
```bash
lsof -ti:8000 | xargs kill -9
```

### 第2步：重新构建前端

```bash
cd /Users/linchen/vanna-demo/frontend
npm run build
cd ..
```

### 第3步：重启后端服务

```bash
cd /Users/linchen/vanna-demo
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🎯 或者使用一键脚本（更简单）

```bash
cd /Users/linchen/vanna-demo

# 方式1：快速重启（推荐）
./RESTART_NOW.sh

# 方式2：完整重启（包含检查）
./rebuild_and_restart.sh
```

---

## ✅ 验证修改是否生效

### 前端修改验证

1. **硬刷新浏览器**
   - Mac: `Cmd + Shift + R`
   - Windows: `Ctrl + Shift + R`

2. **清除缓存**
   - 打开开发者工具（F12）
   - 右键刷新按钮 → "清空缓存并硬性重新加载"

### 后端修改验证

1. **查看终端日志**
   - 应该看到 "Application startup complete"
   - 如果使用 `--reload`，代码更改会自动重载

2. **测试功能**
   - 发送查询测试新功能
   - 检查推理步骤是否动态显示
   - 检查快捷操作按钮是否出现

---

## 🔍 检查清单

- [ ] 服务已停止
- [ ] 前端已重新构建（`frontend/dist/` 目录已更新）
- [ ] 后端服务已重启
- [ ] 浏览器已硬刷新
- [ ] 新功能正常工作









