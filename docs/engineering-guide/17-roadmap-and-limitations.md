# 当前架构局限

> 基于源码和测试结果整理的已知设计权衡。不是"bug"，是当前实现中有意识的取舍。

## 一、设计取舍

| 取舍 | 选择 | 放弃的原因 |
|------|------|-----------|
| 存储 | SQLite + FTS5 | PostgreSQL 的并发和向量索引能力 |
| 事件 | 双轨（EventBus + AsyncGenerator） | 统一事件流的简化 |
| 配置 | config.yaml + .env | 纯环境变量的简洁性 |
| 隔离 | Session 完全隔离 | 全局记忆池的便利性 |
| 扩展 | Skills（纯 Markdown） | 可执行 Workflow 引擎的灵活性 |
| 上下文 | 压缩 + Fork | 滑动窗口的简单性 |
| 工具注入 | contextvars | 显式参数传递的可读性 |
| Token 估算 | 启发式（CJK 1.5, ASCII 0.25） | tiktoken 的精确度 |

## 二、当前架构局限

### 2.1 EventBus 无持久化

`agent_os/core/event_bus.py`

EventBus 的事件发布后无法回溯。组件崩溃后事件丢失——纯内存 pub/sub 的限制。

**影响**：低。EventBus 目前主要用于 Scheduler 通知，使用率不高。

### 2.2 无原生向量索引

`agent_os/storage/sqlite_store.py`

Embedding 向量以 JSON 存储在 `chunks.embedding` 字段，查询时全表加载到内存计算余弦距离。无原生向量索引支持。

**影响**：中。10K+ chunks 时性能下降。当前场景（单 session <5K chunks）可接受。

### 2.3 无 metrics/telemetry

- 无 KV cache hit/miss 监控
- 无工具调用延迟分布
- 无 API 错误率追踪

**影响**：中。生产环境成本优化受限。

### 2.4 无批处理队列

工具调用顺序执行，不支持并行：

```python
for tool_call in tool_calls:
    result = await execute(tool_call)  # 串行
```

**影响**：中。多个独立检索串行增加延迟。

### 2.5 Todo 不持久化（CLI 模式）

`Session.todo_list` 在内存中，CLI session 退出后丢失。

**影响**：低。SQLite 中 reminders 已有持久化。

## 三、已知测试失败

| 测试 | 原因 | 性质 |
|------|------|------|
| test_chat_tool_call | deepseek-v4-flash 未调用 file_read | 模型行为，非代码错误 |
| test_sub_agent_completion | 子 agent 30s 超时 | 需调整超时窗口 |
| test_reminder_event | EventBus 不存储事件历史 | EventBus 架构取舍所致 |
