# ReAct 循环详解

`agent_os/kernel/agent_loop.py` — 2435 行，这是 AgentOS 最核心的模块。

## 循环结构

```
AgentLoop.process(session_id, message)
  │
  ├── Phase 1: 准备
  │   ├── 恢复/创建 session
  │   ├── 检查中断/调度消息
  │   ├── 估算 token
  │   └── token 超阈值 → compress_session() + fork
  │
  ├── Phase 2: 编译上下文
  │   └── context_compiler.compile() → system prompt
  │
  ├── Phase 3: ReAct 循环 (最多 max_iterations 次)
  │   ├── 3.1 model.chat.completions.create() 流式请求
  │   ├── 3.2 解析 response
  │   │   ├── content (文本回复) → ContentStreamEvent
  │   │   └── tool_calls (函数调用) → ToolCallEvent
  │   ├── 3.3 工具执行
  │   │   ├── 过滤 → 执行 → 归档 → ResultFilterAgent
  │   │   ├── 检查 skills 条件激活
  │   │   └── ToolResultEvent
  │   └── 3.4 重复直到：
  │       ├── 模型返回纯文本（无 tool_call）
  │       ├── 达到 max_iterations
  │       ├── 用户中断
  │       └── 超时
  │
  └── Phase 4: 结束
      ├── ContentEvent / ErrorEvent
      ├── 写入运行日志
      └── 保存事件 JSONL 到 logs/run_events.jsonl
```

## 流式事件输出

AgentLoop.process() 是一个异步生成器，每次迭代 yield 事件：

```python
async for event in agent_loop.process(session_id, message):
    match event["type"]:
        case "thinking_stream":
            render_thinking(event["content"])
        case "content_stream":
            render_content(event["content"])
        case "tool_call":
            render_tool_call(event["name"], event["arguments"])
        case "tool_result":
            render_tool_result(event["result"])
        case "activity":
            render_activity(event["phase"], event["detail"])
        case "session.compressed":
            handle_compression(event)
        case "error":
            handle_error(event)
```

## 上下文编译

`context_compiler.compile()` 生成完整的 system prompt：

### 组成

```
<xml>  (~5000 chars)
├── agent_system.txt (prompts/agent_system.txt, ~90 行)
├── SOUL.md (session 创建时生成, 400-800 chars)
├── AGENT.md (session 创建时生成, 300-600 chars)
├── MEMORY.md (session 创建时生成, 300-500 chars)
├── Skill profiles (YAML frontmatter 从激活的 skill)
├── Skills index (可用 skill 列表, name + description)
├── Memory guidance (prompts/memory_guidance.txt)
└── </xml>
```

### 动态注入（不破坏 KV cache）

编译后追加的 user 消息：

```python
[
    {"role": "system", "content": "<xml>编译好的 system prompt</xml>"},
    {"role": "user", "content": "<workspace_tree>文件列表</workspace_tree>\n<system-reminder>时间戳</system-reminder>\n"},
    ...history messages...
    {"role": "user", "content": "用户当前输入"},
]
```

- `workspace_tree` 在每次变化时更新
- `system-reminder` 携带时间戳、待办提醒、文件变更通知
- 这些在 history 之前、system prompt 之后，不破坏 prefix

## Token 估算与压缩

### 估算方法

`agent_os/kernel/helpers.py:estimate_messages_tokens()`

```python
def estimate_messages_tokens(messages: list) -> int:
    total = 0
    for msg in messages:
        content = extract_message_content(msg)
        # CJK: 1.5 token/char
        # ASCII: 0.25 token/char
        # 其他: 0.5 token/char
        total += estimate(content)
    return total
```

**为什么不用 tiktoken**：
- 减少外部依赖
- 不需要为每个 model 加载 tokenizer
- 近似的线性估算对于触发压缩阈值足够

### 压缩流程

`agent_os/kernel/agent_loop.py` 中的 `compress_session()`

```
触发条件: total_prompt_tokens > context_token_threshold (600K)

Step 1: 语义切片
  ├── 保留头部 N 回合（含 system prompt + 初始消息）
  ├── 保留尾部 N 回合（最近的交互）
  ├── 识别中间回合中的"关键"消息:
  │   ├── user 角色消息
  │   ├── file_write 调用
  │   └── 含决策信号的 tool 输出
  └── 其余标记为"可压缩"

Step 2: LLM 压缩
  └── 可压缩回合序列化 → LLM → <chronology> 时序摘要
      格式: "做了什么 → 发现了什么 → 因此做了什么 → 得到了什么"

Step 3: fork 新 session
  ├── fork_session(work_dir=parent.work_dir)
  ├── compression_version++
  ├── 父 session status = "compressed"
  └── 写入 compression_state.md

Step 4: 注入压缩上下文
  └── [COMPACTION vN] + <chronology>XML
```

### 保留 vs 丢弃

| 保留 | 丢弃 |
|------|------|
| System prompt（原样） | 中间回合精确文本 |
| 头部 N 回合完整 | 中间回合 token 开销 |
| 尾部 N 回合完整 | 旧 session KV cache |
| user/file_write/decision 消息 | 冗余的 tool 输出 |
| work_dir 全部文件 | |
| LLM 生成的时序摘要 | |

## 内容过滤恢复

`agent_os/kernel/agent_loop.py` — 两级恢复策略：

### 软恢复

```python
# 当模型被内容过滤拦截时：
if is_content_filter_exception(exc):
    # 删除刚刚添加的 assistant 消息
    # 删除最后一个 user 消息（就是触发过滤的那个）
    # 重新请求，不改变上下文结构
```

适用：模型输出了被审查的内容，删除后重试。

### 硬恢复

```python
# 当软恢复连续失败时：
# 构建"系统仅"恢复消息（不带 tool 结果）
# 跳过最近 2 轮 tool 调用
# 限制后续 tool 调用为 read_only
```

适用：多轮内容过滤无法恢复，需要更激进的上下文清理。

## 研究护栏 (Guardrails)

### 盲搜索护栏

```python
# blind_search_guardrail_rounds = 9 (config)
# 连续 9 轮 tool call 都是检索且没有 research_state 时：
# → 注入干预消息，强制 agent 反思
```

### 工具执行限制

```python
# research_state 不能与检索工具在同一轮共享
# 检索工具输出自动归档 raw_search/
# 外部检索结果自动经过 ResultFilterAgent
```

## SubAgent 执行

`agent_os/kernel/sub_agent.py`

### 隔离模式

```
spawn(任务描述)
  ├── 创建 child session (parent_session_id = parent.id)
  ├── 共享 parent 的 work_dir
  ├── 独立消息历史
  ├── 可限制 allowed_tools（默认文件 + 检索）
  ├── 禁止嵌套 spawn
  ├── 异步执行（不阻塞 parent）
  └── 返回 <task_notification>XML

parent 通过 send_message() 与 child 通信
parent 通过 task_stop() 终止 child
```

### 状态追踪

```python
# SubAgent 运行状态写入:
# work_dir/raw_search/subagents/{child_id}.jsonl
# 每行: {"type": "status", "phase": "running", ...}
# 父 agent 和 UI 可实时查看进展
```

## KV Cache 保护策略

```
1. System prompt prefix 固定
   └── 编译时冻结，不动态重组

2. 动态内容以 user 消息追加
   └── 不在 history 中间插入

3. tool_call arguments 排序序列化
   └── sorted(key=...) 确保 bit-perfect match

4. active_skills 变更 → cleanup_session()
   └── 显式缓存失效，避免脏数据

5. 压缩使用 cache-aligned 方式
   └── 在原上下文末尾追加 summarize 请求
```

### 缓存命中率监控

`model.completed` 事件包含：

```python
{
    "type": "activity",
    "phase": "model.completed",
    "payload": {
        "prompt_cache_hit_tokens": 450000,
        "prompt_tokens": 500000,
        "completion_tokens": 2000,
        "cache_hit_rate": 0.9,
        "duration_ms": 2500,
    }
}
```
