#!/bin/bash

# 服务日志检查脚本

cd "$(dirname "$0")"

echo "🔍 检查服务日志..."
echo ""

# 检查进程
echo "📊 当前运行的服务进程:"
ps aux | grep -E "uvicorn|python.*main:app" | grep -v grep | head -3
echo ""

# 检查日志文件
echo "📝 日志文件:"
if [ -f "logs/app.log" ]; then
    echo "   ✅ logs/app.log 存在"
    echo "   📏 文件大小: $(ls -lh logs/app.log | awk '{print $5}')"
    echo "   📊 行数: $(wc -l < logs/app.log)"
    echo ""
    echo "   🔴 最近的错误 (最后20行):"
    grep -i "error\|exception\|traceback\|fatal\|killed" logs/app.log | tail -20 || echo "   未找到错误"
    echo ""
    echo "   ⚠️  最近的警告 (最后10行):"
    grep -i "warning\|warn" logs/app.log | tail -10 || echo "   未找到警告"
else
    echo "   ❌ logs/app.log 不存在"
fi

echo ""
echo "📋 /tmp/vanna-server.log:"
if [ -f "/tmp/vanna-server.log" ]; then
    echo "   ✅ /tmp/vanna-server.log 存在"
    echo "   📏 文件大小: $(ls -lh /tmp/vanna-server.log | awk '{print $5}')"
    echo "   📊 行数: $(wc -l < /tmp/vanna-server.log)"
    echo ""
    echo "   🔴 最近的错误:"
    grep -i "error\|exception\|traceback\|fatal\|killed" /tmp/vanna-server.log | tail -10 || echo "   未找到错误"
else
    echo "   ❌ /tmp/vanna-server.log 不存在"
fi

echo ""
echo "📦 数据库中的错误记录:"
if [ -f "logs/logs.db" ]; then
    sqlite3 logs/logs.db "SELECT conversation_id, role, content FROM message WHERE role='system' AND content LIKE '%ERROR%' ORDER BY timestamp DESC LIMIT 5;" 2>/dev/null || echo "   无法查询数据库"
else
    echo "   ❌ logs.db 不存在"
fi

echo ""
echo "✅ 检查完成"









