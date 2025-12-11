# 📝 服务日志说明

## 日志文件位置

### 1. 应用日志（改进后）
- **位置**: `logs/app.log`
- **说明**: 记录所有级别的日志（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- **格式**: 包含时间戳、模块名、日志级别、消息内容

### 2. 服务器输出日志
- **位置**: `/tmp/vanna-server.log`
- **说明**: uvicorn 的 stdout/stderr 输出
- **内容**: 主要是请求日志和INFO级别的消息

## 查看日志的方法

### 方法1：使用日志检查脚本（推荐）

```bash
cd /Users/linchen/vanna-demo
./check_service_logs.sh
```

这个脚本会显示：
- 当前运行的服务进程
- 日志文件位置和大小
- 最近的错误和警告
- 数据库中的错误记录

### 方法2：直接查看日志文件

```bash
# 查看应用日志
tail -f logs/app.log

# 查看服务器输出日志
tail -f /tmp/vanna-server.log

# 查看最近的错误
grep -i "error\|exception\|traceback" logs/app.log | tail -20
```

### 方法3：实时监控日志

```bash
# 监控应用日志
tail -f logs/app.log | grep -i "error\|warning"

# 监控所有日志
tail -f logs/app.log /tmp/vanna-server.log
```

## 服务中断诊断

如果服务突然中断，按以下步骤排查：

### 1. 检查日志文件

```bash
./check_service_logs.sh
```

### 2. 查看最近的错误

```bash
grep -i "error\|exception\|traceback\|fatal\|killed" logs/app.log /tmp/vanna-server.log | tail -30
```

### 3. 检查进程状态

```bash
ps aux | grep "uvicorn\|python.*main:app" | grep -v grep
lsof -ti:8000
```

### 4. 检查数据库错误记录

```bash
sqlite3 logs/logs.db "SELECT conversation_id, role, content FROM message WHERE role='system' ORDER BY timestamp DESC LIMIT 10;"
```

## 常见中断原因

1. **代码修改触发自动重载**
   - 使用 `uvicorn --reload` 时，代码修改会自动重载
   - 重载过程中服务会短暂中断
   - 检查日志中的 "StatReload detected changes" 消息

2. **内存不足（OOM）**
   - 系统可能因为内存不足而杀死进程
   - 检查系统日志：`dmesg | grep -i "oom\|kill"`

3. **端口冲突**
   - 多个进程尝试使用同一端口
   - 检查：`lsof -ti:8000`

4. **异常未捕获**
   - 某些异常可能导致服务崩溃
   - 检查日志文件中的ERROR和EXCEPTION记录

5. **资源限制**
   - CPU/内存/文件描述符达到限制
   - 检查系统资源：`top`、`htop`、`ulimit -a`

## 日志级别说明

- **DEBUG**: 详细的调试信息
- **INFO**: 一般信息（默认级别）
- **WARNING**: 警告信息
- **ERROR**: 错误信息
- **CRITICAL**: 严重错误

## 注意事项

1. **日志文件会自动增长**，需要定期清理或使用日志轮转
2. **日志文件位置**可以通过环境变量配置
3. **敏感信息**（如API密钥）不会记录到日志中
4. **生产环境**建议使用专门的日志管理系统

## 改进建议

1. 使用日志轮转工具（如 `logrotate`）
2. 集成日志聚合服务（如 ELK Stack）
3. 设置日志级别为环境变量可配置
4. 添加日志监控和告警









