#!/bin/bash

# 立即重启脚本 - 适用于修改代码后快速重启

cd "$(dirname "$0")"

echo "🔄 快速重启服务..."
echo ""

# 激活虚拟环境
source venv/bin/activate

# 停止现有服务
echo "1️⃣ 停止现有服务..."
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "   正在停止运行在8000端口的服务..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 1
    echo "   ✅ 已停止"
else
    echo "   ✅ 未发现运行中的服务"
fi

# 重新构建前端
echo ""
echo "2️⃣ 重新构建前端..."
cd frontend
rm -rf dist
npm run build
if [ $? -ne 0 ]; then
    echo "   ❌ 前端构建失败！"
    exit 1
fi
echo "   ✅ 前端构建完成"
cd ..

# 重启后端
echo ""
echo "3️⃣ 启动后端服务..."
echo ""
echo "📍 访问地址:"
echo "   ✨ 新版聊天界面: http://localhost:8000/chat (或 http://localhost:8000/app)"
echo "   📜 经典聊天界面: http://localhost:8000/classic"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

uvicorn main:app --reload --host 0.0.0.0 --port 8000



