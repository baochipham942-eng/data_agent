#!/bin/bash

# 重新构建前端并重启服务的脚本

set -e  # 遇到错误立即退出

cd "$(dirname "$0")"

echo "🔄 开始重新构建并重启服务..."
echo ""

# 1. 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "❌ 错误: 虚拟环境不存在，请先创建虚拟环境"
    exit 1
fi

# 激活虚拟环境
echo "📦 激活虚拟环境..."
source venv/bin/activate

# 2. 检查并停止现有服务
echo ""
echo "🛑 检查并停止现有服务..."
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "发现运行在8000端口的进程，正在停止..."
    pkill -f "uvicorn main:app" || true
    sleep 2
    echo "✅ 已停止现有服务"
else
    echo "✅ 未发现运行中的服务"
fi

# 3. 重新构建前端
echo ""
echo "📦 重新构建前端..."
cd frontend

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi

# 清理旧的构建
if [ -d "dist" ]; then
    echo "清理旧的构建文件..."
    rm -rf dist
fi

# 重新构建
echo "开始构建前端..."
npm run build

if [ $? -ne 0 ]; then
    echo "❌ 前端构建失败！"
    exit 1
fi

echo "✅ 前端构建完成"
cd ..

# 4. 检查后端代码是否有语法错误
echo ""
echo "🔍 检查后端代码..."
python -m py_compile main.py
if [ $? -ne 0 ]; then
    echo "❌ 后端代码有语法错误！"
    exit 1
fi
echo "✅ 后端代码检查通过"

# 5. 启动服务
echo ""
echo "🚀 启动服务..."
echo ""
echo "📍 访问地址:"
echo "   ✨ 新版聊天界面: http://localhost:8000/chat (或 http://localhost:8000/app)"
echo "   📜 经典聊天界面: http://localhost:8000/classic"
echo "   📝 日志列表: http://localhost:8000/logs"
echo "   🔧 Vanna UI: http://localhost:8000/"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 启动服务（使用 --reload 以便代码更改后自动重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8000



