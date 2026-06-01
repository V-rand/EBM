# Agent Loop 状态机对比

四个系统核心 agent loop 的源码级对比。

---

## AgentOS — 隐式 ReAct + 事件生成器

**文件**：`agent_os/kernel/agent_loop.py` (2435 行)

```
用户消息 → AgentLoop.process()
             │
             ▼
     ┌──────────────────────────────────┐
     │  1. 准备阶段                      │
     │  ├─ 检查中断/调度消息              │
     │  ├─ 估算 token                    │
     │  └─ 超阈值？→ compress + fork     │
     └──────────────────────────────────┘
             │
             ▼
     ┌──────────────────────────────────┐
     │  2. 编译上下文                    │
     │  └─ context_compiler.compile()   │
     └──────────────────────────────────┘
             │
             ▼
     ┌──────────────────────────────────┐      ┌────────────────────┐
     │  3. ReAct 循环                    │      │                    │
     │  ┌─────────────────────────┐     │      │   事件流输出        │
     │  │ model.chat.create()    │─────┼──────▶ ActivityEvent      │
     │  │  ↓                      │     │      │ ThinkingStreamEvent │
     │  │ response 有 tool_calls? │     │      │ ContentStreamEvent  │
     │  │  ├─ 是 → 执行工具       │─────┼──────▶ ToolCallEvent      │
     │  │  │      ↓               │     │      │ ToolResultEvent    │
     │  │  │   └─ 回到 model      │     │      │ SessionCompressed  │
     │  │  └─ 否 → 返回最终答案   │─────┼──────▶ ContentEvent       │
     │  └─────────────────────────┘     │      │ ErrorEvent         │
     └──────────────────────────────────┘      └────────────────────┘
```

- **不是显式状态机**。用 `while` 循环 + `break` 控制流程
- **最多 `max_iterations` 次**（默认 64）
- **无并发工具执行**——tool calls 串行
- **事件流通过 `yield` 输出**——CLI/TUI 都是 `async for` 消费者
- **无重试/回退机制**——内容过滤有两级恢复（软/硬），但没有 provider fallback

---

## nanobot — 显式 8 状态状态机

**文件**：`nanobot/agent/loop.py` (1600 行)

```
                         COMMAND
                      ┌───(dispatch)───┐
                      ▼                │
RESTORE ──→ COMPACT ──→ COMMAND ──→ BUILD ──→ RUN ──→ SAVE ──→ RESPOND ──→ DONE
  │           │          │                       │          │
  │           │          └──(shortcut)────────────┼──────────┼─────→ DONE
  │           │                                   │          │
  │           ↓                                   │          │
  │    auto_compact  ← token 超阈值               │          │
  │           │                         RUN 内部循环：        │
  │           │    ┌─────────────────────────────────────┐    │
  │           │    │ for iteration in range(max_iter):   │    │
  │           │    │   context_governance()  ← 5 步清洗   │    │
  │           │    │   model.call()                     │    │
  │           │    │   if tool_calls:                   │    │
  │           │    │     execute (并行)                  │    │
  │           │    │     checkpoint                     │    │
  │           │    │     continue                       │    │
  │           │    │   else:                            │    │
  │           │    │     handle_empty()                 │    │
  │           │    │     drain_injections()             │    │
  │           │    │     break                          │    │
  │           │    └─────────────────────────────────────┘    │
  │           │                                   │          │
  │           │                      SAVE：写入 JSONL + 文件帽 │
  │           │                                   │          │
  │           │                      RESPOND：组装 Outbound   │
  └───────────┴───────────────────────────────────────────────┘
```

**转换表**（核心）：

```python
_TRANSITIONS = {
    (RESTORE, "ok"):        COMPACT,
    (COMPACT, "ok"):        COMMAND,
    (COMMAND, "dispatch"):  BUILD,
    (COMMAND, "shortcut"):  DONE,    # 内置命令走这里
    (BUILD, "ok"):          RUN,
    (RUN, "ok"):            SAVE,
    (SAVE, "ok"):           RESPOND,
    (RESPOND, "ok"):        DONE,
}
```

- **显式状态机的核心模式**：handler 返回 event string（如 "ok"），驱动查表进入下一状态
- **COMMAND 可短路到 DONE**——内置命令（/new, /help）跳过整个 LLM 交互
- **RUN 内部是独立的 tool-calling 循环**——外层状态机管"一轮对话"的生命周期
- **context_governance 5 步清洗**——drop_orphan → backfill → microcompact → truncate → snip
- **支持并行工具执行**——concurrency_safe 的工具走 `asyncio.gather`

---

## Hermes — Dual-Loop ReAct + Retry 链

**文件**：`agent/conversation_loop.py:run_conversation()` (4300 行)

```
主循环入口
while api_call_count < max_iterations AND budget.remaining > 0:
     │
     ├── 重试循环 (inner while retry_count < max_retries)
     │    │
     │    ├── API 调用
     │    │    │
     │    │    ├── 成功？
     │    │    │    ├── 有 tool_calls?
     │    │    │    │    ├── 验证/去重 tool names
     │    │    │    │    ├── _execute_tool_calls() ← 同步执行
     │    │    │    │    ├── guardrail halt 检查
     │    │    │    │    ├── post-tool 压缩检查
     │    │    │    │    └── continue
     │    │    │    │
     │    │    │    └── 无 tool_calls?
     │    │    │         ├── thinking-only? → prefill 续写
     │    │    │         ├── empty? → retry → nudge → fallback
     │    │    │         └── break
     │    │    │
     │    │    └── 失败？
     │    │         ├── 429/401/402 → credential pool 轮换
     │    │         ├── 413/context_overflow → 压缩（最多 3 次）
     │    │         ├── Unicode/image/thinking 错误 → 清洗重试
     │    │         ├── 超过 max_retries → fallback provider
     │    │         └── 不可恢复错误 → abort
     │    │
     │    └── 需要压缩后重开？→ restart_with_compressed_messages = True
     │         → budget refund → continue
     │
     └── budget 耗尽? → _handle_max_iterations() → 摘除工具后单次总结
```

**预压缩（循环外）**：
```
估算 token → 超 75% context window?
  ├─ 是 → 压缩（最多 3 pass）
  └─ 否 → 正常进入循环
```

**后压缩（循环内）**：每次工具执行后检查 `should_compress()` → 需要则 fork 新 session + 注入摘要

**Retry 链（4 层）**：
```
Layer 1: inner while 重试（指数退避）
Layer 2: 各类错误特定恢复（unicode/credential/compression）
Layer 3: fallback provider 切换（跨越 retry boundary）
Layer 4: 不可恢复→ abort
```

---

## Codex CLI — 流式响应处理器

**文件**：`codex-rs/core/src/session/turn.rs` (~2100 行)

```
run_turn()
  │
  ├── 1. Pre-sampling compact (token budget / model downshift)
  │
  ├── 2. 构建 skills & plugins 注入
  │
  └── 3. 主循环（多轮 sampling）
       │
       │   ┌──────────────────────────────────────────────┐
       │   │ 可以 drain pending input?                     │
       │   │  ├─ 有 → 注入用户 mid-turn 消息                │
       │   │  └─ 无 → 继续                                │
       │   │                                               │
       │   │ clone_history() → for_prompt()                │
       │   │ build_tools() → ToolRouter                    │
       │   │                                               │
       │   └──→ run_sampling_request()                     │
       │          │                                        │
       │          ├── try_run_sampling_request() ← 核心     │
       │          │    │                                   │
       │          │    │ 事件循环:                           │
       │          │    │ loop { stream.next() }            │
       │          │    │   OutputItemAdded → 创建 item      │
       │          │    │   OutputTextDelta → 流式输出       │
       │          │    │   ToolCallInputDelta → UI 显示     │
       │          │    │   OutputItemDone →                 │
       │          │    │     ├─ 工具调用 → dispatch → 并行执行│
       │          │    │     │   → in_flight 队列           │
       │          │    │     └─ 文本 → record + finalize    │
       │          │    │   Completed → break (needs_follow_up)│
       │          │    │                                        │
       │          │    └── drain_in_flight() → 等所有工具完成   │
       │          │                                           │
       │          └── 失败? → retry loop                      │
       │                                                       │
       └── 继续还是停止?
            needs_follow_up | token_limit | pending_input
            ├── true  + true   → compact + continue
            ├── false + false  → stop
            ├── true  + false  → continue
            └── false + true   → continue (drain pending)
```

**关键特点**：
- **不是"调用 LLM → 解析返回"的经典 ReAct**，而是**流式事件消费者**
- OpenAI Responses API 的 `/responses` 端点返回流式事件，Codex 的 loop 逐事件消费
- **工具并行执行**通过 `FuturesOrdered<InFlightFuture>` 管理
- **模型决定是否需要 follow-up**（`end_turn` 字段），而非代码判断
- **auto-compact 在判断继续/停止之后**——超预算时不立刻停，而是压缩后再继续

---

## 四者并排对比

```
AgentOS:    准备 → 编译 → [ model → 工具(串行) → model → ... ] → 结束
                       ↑ 隐式 while 循环, yield 事件流输出

nanobot:    RESTORE → COMPACT → COMMAND → BUILD → RUN → SAVE → RESPOND → DONE
                                                         │
                                          ┌──── 内部 tool-calling 循环 ────┐
                                          │ for iter: model → 工具(并行)   │
                                          └───────────────────────────────┘

Hermes:     [预压缩] → [ model → 工具(同步) → post-tool 压缩 → model → ... ]
                       ↑ 双层 while + 4 层 retry/fallback

Codex:      [预压缩] → [ 流式事件 loop: model ↔ 工具(并行) ↔ 用户 mid-turn ]
                       ↑ 流式 Response API 消费者，模型控制 follow-up
```

## 核心差异总结

| 维度 | AgentOS | nanobot | Hermes | Codex CLI |
|------|---------|---------|--------|-----------|
| **循环结构** | 隐式 while | 显式 8 状态状态机 | 隐式 while + retry 层 | 流式事件循环 |
| **状态定义** | 无（代码内 while） | `_TRANSITIONS` dict | 无（while + continue/break） | 无（loop + match event） |
| **状态数量** | 隐式 3 阶段 | 8 显式状态 | 隐式 5+ 阶段 | 隐式 4 阶段 |
| **工具执行** | 串行 | 并行（按 safe 分组） | 同步（串行） | 并行（in_flight 队列） |
| **事件输出** | `AsyncGenerator` yield | `MessageBus` Queue | callback 体系 | 50+ `EventMsg` 枚举 |
| **循环控制** | while + break | state + event → next | while + continue/break | stream event driven |
| **重试链** | 两级内容过滤 | 无 | 4 层（退避→特定恢复→fallback→abort） | retry loop + compact |
| **压缩时机** | 进入时 token 超阈值 | BUILD 时 + background | 预压缩 + post-tool + 错误时 | pre + mid-turn + model downshift |
| **mid-turn 注入** | inject_message() | pending_queue + _drain_pending | steer injection | drain_pending_input |
| **文件行数** | ~2400 | ~1600 (loop+runner) | ~4300 | ~2100 (仅 turn.rs) |

**关键趋势**：
- nanobot 的状态机模式**最易于理解和修改**——加了新状态只需 enum + handler + transition
- Hermes 的 retry/fallback 链**最健壮**——4 层、credential pool、provider fallback
- Codex 的流式事件处理**最适合长上下文**——模型端处理 reasoning，客户端只需消费事件
- AgentOS 的结构**最简单**——40 个文件，核心概念少，适合作为基线理解其他系统
