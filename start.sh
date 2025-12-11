#!/bin/bash

# 启动脚本
cd "$(dirname "$0")"

# 激活虚拟环境
source venv/bin/activate

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  警告: .env 文件不存在，请确保已配置 DEEPSEEK_API_KEY"
fi

# 检查日志数据库
if [ ! -f logs/logs.db ]; then
    echo "📝 初始化日志数据库..."
    python scripts/init_logs_db.py
fi

# 检查前端构建
if [ ! -d "frontend/dist" ]; then
    echo "📦 前端未构建，正在构建..."
    cd frontend
    npm install
    npm run build
    cd ..
fi

# 获取局域网IP地址
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="未检测到（请手动查看 ifconfig）"
fi

# 启动服务
echo "🚀 启动服务..."
echo ""
echo "📍 本地访问地址:"
echo "   ✨ 新版聊天界面: http://localhost:8000/chat (或 http://localhost:8000/app)"
echo "   📜 经典聊天界面: http://localhost:8000/classic"
echo "   📝 日志列表: http://localhost:8000/logs"
echo "   🔧 Vanna UI: http://localhost:8000/"
echo ""
echo "🌐 局域网访问地址（供同事访问）:"
echo "   ✨ 新版聊天界面: http://${LOCAL_IP}:8000/chat (或 http://${LOCAL_IP}:8000/app)"
echo "   📜 经典聊天界面: http://${LOCAL_IP}:8000/classic"
echo "   📝 日志列表: http://${LOCAL_IP}:8000/logs"
echo "   🔧 Vanna UI: http://${LOCAL_IP}:8000/"
echo ""
echo "💡 提示: 确保防火墙允许 8000 端口的访问"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

uvicorn main:app --reload --host 0.0.0.0 --port 8000

