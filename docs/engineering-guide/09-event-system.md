# 事件系统

AgentOS 有两个独立的事件系统，服务于不同目的。理解双轨设计是理解整个架构的关键。

## 双轨概览

```
                    AgentOS Event Architecture
                    ═══════════════════════════

内部通信 (EventBus)                   面向输出 (AsyncGenerator)
────────────────────                  ──────────────────────
作用: 组件间松耦合通信                  作用: 用户界面数据
模式: 单例 pub/sub                     模式: AsyncGenerator[TypedDict]
监听: 系统组件 (scheduler, etc)         监听: CLI / TUI / API
持久: ❌ 不持久化                       持久: 写入 run_events.jsonl
类型: 8 种 EventType                   类型: 11 种 TypedDict
```

## EventBus：内部 pub/sub

`agent_os/core/event_bus.py`

### 接口

```python
class EventBus:
    def subscribe(self, event_type: EventType, handler): ...
    def subscribe_all(self, handler): ...
    async def publish(self, event: Event): ...
    async def publish_typed(self, event_type, payload, session_id): ...

class Event:
    type: EventType
    payload: dict
    session_id: str | None
    timestamp: str  # ISO datetime
```

### 8 种事件类型

```python
class EventType(Enum):
    SESSION_CREATED   = "session.created"    # 新 session
    SESSION_CLOSED    = "session.closed"     # session 关闭
    MESSAGE_RECEIVED  = "message.received"   # 收到用户消息
    MESSAGE_SENT      = "message.sent"       # Agent 回复
    TOOL_CALLED       = "tool.called"        # 工具被调用
    TOOL_COMPLETED    = "tool.completed"     # 工具执行完毕
    INTERRUPT_FIRED   = "interrupt.fired"    # 定时提醒触发
    INTERRUPT_HANDLED = "interrupt.handled"  # 提醒被处理
```

### 使用场景

目前 EventBus 主要用于 Scheduler 的提醒触发通知。其他组件通过 `subscribe` 订阅感兴趣的事件。

**已知局限**：不持久化，事件发布后无法回溯。EventBus 是为未来扩展预留的架构，当前使用率不高。

## AsyncGenerator Events：用户面向输出

`agent_os/kernel/event_types.py`

AgentLoop.process() 是一个 `AsyncGenerator[ProcessEvent]`。每个 yield 的事件是一个 TypedDict。

### 11 种事件类型

```python
class ActivityEvent(TypedDict):
    type: str      # "activity"
    phase: str     # "context.compiled" / "run.started" / "model.completed" / ...
    detail: str
    payload: dict | None

class ThinkingStreamEvent(TypedDict):
    type: str      # "thinking_stream"
    content: str   # 推理文本片段

class ContentStreamEvent(TypedDict):
    type: str      # "content_stream"
    content: str   # 答案文本片段

class ToolCallEvent(TypedDict):
    type: str      # "tool_call"
    name: str
    arguments: dict
    summary: str   # 一行摘要

class ToolResultEvent(TypedDict):
    type: str      # "tool_result"
    result: dict   # ToolResult.to_dict() 输出

class ContentEvent(TypedDict):
    type: str      # "content"
    content: str   # 最终答案

class ErrorEvent(TypedDict):
    type: str      # "error"
    error: str
    payload: dict | None  # 快照路径、错误类型等

class InterventionEvent(TypedDict):
    type: str      # "intervention"
    content: str
    payload: dict | None

class QuestionEvent(TypedDict):
    type: str      # "question"
    content: str
    payload: dict | None

class SessionCompressedEvent(TypedDict):
    type: str              # "session.compressed"
    old_session_id: str
    new_session_id: str
    estimated_tokens_before: int
```

### 阶段流

```
context.compiled ──→ run.started ──→ model.requested
                                         │
                              ┌──────────┼──────────┐
                              ▼          ▼          ▼
                    thinking_stream  content_stream  模型完成
                              │          │
                              └──────────┘
                                         │
                              model.completed (含缓存命中率)
                                         │
                              tool_call ──→ tool_result
                                         │
                              ← 回到 model.requested (循环)
                                         │
                              run.completed / run.failed
```

### CLI 渲染示例

```python
# cli.py 中的简化渲染
async def _render_chat_chunk(chunk):
    match chunk["type"]:
        case "thinking_stream":
            sys.stdout.write(dim(chunk["content"]))
        case "content_stream":
            sys.stdout.write(chunk["content"])
        case "tool_call":
            print(f"  🛠 {chunk['name']}({chunk['summary']})")
        case "tool_result":
            status = "✓" if chunk["result"]["success"] else "✗"
            print(f"  {status} ({duration})")
        case "activity":
            print(f"  · {chunk['detail']}")
        case "session.compressed":
            print(f"  📦 上下文压缩: {chunk['old_session_id']} → {chunk['new_session_id']}")
        case "error":
            print(f"  ❌ {chunk['error']}")
```

### 事件日志

运行事件写入 `data/sessions/{id}/logs/run_events.jsonl`：

```jsonl
{"type":"activity","phase":"context.compiled","detail":"上下文编译完成","payload":null,"session_id":"abc123","timestamp":"..."}
{"type":"thinking_stream","content":"让我分析一下...","session_id":"abc123"}
{"type":"tool_call","name":"web_search","arguments":{...},"summary":"搜索xxx","session_id":"abc123"}
{"type":"tool_result","result":{"success":true,...},"session_id":"abc123"}
```

## 为什么是双轨

| 维度 | EventBus | AsyncGenerator |
|------|----------|----------------|
| 消费者 | 系统组件 | 用户界面 |
| 传递方式 | publish/subscribe | yield/async for |
| 同步性 | 异步回调 | 顺序流 |
| 持久化 | 否 | JSONL 文件 |
| 用于 | 事件驱动的工作流 | 流式渲染 |

**不是合并的理由**：
- EventBus 适合"触发后不管"的通知（定时器触发、文件变更）
- AsyncGenerator 适合需要顺序消费的流（模型输出、工具结果）
- 两者的生产者、消费者、处理方式完全不同

## 未来改进方向

1. EventBus 持久化 — 事件流可回溯、可审计
2. 事件类型扩展 — 文件变更、skill 激活、session 压缩
3. 事件过滤器 — 按 session、类型、时间范围查询历史事件
