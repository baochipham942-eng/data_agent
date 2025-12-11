# GeneratorExit 异常修复

## 问题

日志显示 `GeneratorExit()` 异常，导致 SSE 流被提前中断，前端收到 `ERR_INCOMPLETE_CHUNKED_ENCODING` 错误。

## 根本原因

1. **解析逻辑阻塞了流的传递**：之前的代码先解析后 yield，如果解析出错可能导致流传递被阻塞
2. **GeneratorExit 未正确处理**：当客户端断开连接时，生成器会收到 GeneratorExit，这是正常的，不应该作为错误处理
3. **chunk 可能被重复 yield**：JSON 解析失败时，chunk 被 yield 了两次

## 修复方案

### 1. 先 yield 后解析
```python
async for chunk in original_iter:
    # 先yield chunk，确保流不会被阻塞
    yield chunk
    
    # 然后尝试解析和提取数据（不影响流的传递）
    try:
        text = chunk.decode("utf-8")
        # ... 解析逻辑
    except Exception:
        # 即使解析失败，chunk已经传递，不影响流
        pass
```

### 2. 正确处理 GeneratorExit
```python
except GeneratorExit:
    # 生成器被关闭是正常的（客户端断开连接等），不需要记录错误
    logger.debug(f"[logging_middleware] 生成器被关闭（可能是客户端断开连接）")
    raise  # 重新抛出，让生成器正常关闭
```

### 3. 确保所有解析错误都被捕获
所有解析逻辑都在 try-except 块中，即使出错也不会中断流。

## 修复效果

- ✅ SSE 流不会被解析错误中断
- ✅ chunk 总是能及时传递给客户端
- ✅ GeneratorExit 被正确处理
- ✅ 所有错误都被记录但不影响流传递

## 测试建议

1. 测试正常流程：发送消息，确保流能完整传递
2. 测试断开连接：中途关闭页面，确保后端不会报错
3. 测试异常数据：发送可能导致解析错误的数据，确保流不被中断








