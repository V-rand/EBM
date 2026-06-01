# 核心概念

要理解这个系统，只需要搞明白四个概念：**Session**、**Event**、**Tool** 和 **Skill**。其他都是围绕它们的实现细节。

## Session — 就是一个独立的工作区

Session 是整个系统最基本的隔离单元。你可以把它想象成操作系统里的一个进程：有自己的内存（消息历史）、自己的文件系统（work_dir）、自己的待办事项。

```python
# agent_os/core/session.py
@dataclass
class Session:
    id: str                 # UUID[:12]
    name: str
    status: str             # active / compressed / closed
    work_dir: str           # data/sessions/{id}_{name}/
    parent_session_id: str  # 如果是从另一个 session 压缩来的
```

每个 session 创建时自动生成目录结构：

```
data/sessions/{id}_{name}/
├── SOUL.md          # Agent 身份设定
├── AGENT.md         # 行为指南
├── MEMORY.md        # 长期记忆（Agent 自己维护）
├── uploads/         # 用户上传（只读）
├── research/        # 研究成果
├── drafts/          # 生成输出
├── raw_search/      # 检索原始内容（自动归档）
└── logs/            # 运行日志
```

Session 之间完全隔离。压缩时 fork 出来的子 session 共享父 session 的 work_dir，但消息历史完全独立。这种设计来自法律场景的保密要求——一个案件的 session 不能看到另一个案件的消息。

### 压缩链

当对话太长（超过 `context_token_threshold`，默认 600K tokens），就会触发压缩：

```
Session A (完整历史)
  → 超阈值 → 中间回合被 LLM 压缩为摘要
  → fork Session B（work_dir 不变，压缩版本号 +1）
  → Session A 标记为 compressed，历史保留在 SQLite
```

这样做的意义：父 session 的完整历史不会丢失（审计需要），子 session 可以继续工作且不需要从头加载所有历史。

## Event — 两个事件系统，各干各的

系统内部有两套事件机制，服务于不同的目的。

### EventBus：组件间的广播

`agent_os/core/event_bus.py` — 一个简单的 pub/sub 单例。

```python
bus = get_event_bus()
bus.subscribe(EventType.TOOL_CALLED, my_handler)
await bus.publish(EventType.TOOL_CALLED, payload={...})
```

有 8 种事件类型：session.created/closed、message.received/sent、tool.called/completed、interrupt.fired/handled。

**目前用得不频繁，也不是持久化的。** 主要是 scheduler 用来通知其他组件"提醒触发了"。这是一个已知的局限——事件发完就丢了。

### AsyncGenerator Events：面向用户的流

`agent_os/kernel/event_types.py` — AgentLoop.process() yield 出来的结构化事件。

```python
async for event in agent_loop.process(session_id, message):
    match event["type"]:
        case "thinking_stream":  # 模型推理中
        case "content_stream":   # 答案内容
        case "tool_call":       # 模型要调工具
        case "tool_result":     # 工具执行完毕
        case "session.compressed":  # 上下文被压缩了
        case "error":           # 出错了
```

CLI、TUI、API 都是这些事件的消费者。这个分离保证了"换前端不用改内核"。

## Tool — 能力的入口

Tool 是 Agent 可以用来影响外部世界的手段。每个 Tool 就是一个异步函数 + 一份 OpenAI function calling schema。

```python
# agent_os/tools/registry.py
@dataclass
class ToolEntry:
    name: str
    toolset: str               # filesystem / retrieval / execution / ...
    schema: dict               # 模型看到的参数描述
    handler: Callable          # async def(**kwargs) → ToolResult
    read_only: bool            # 不会改东西
    concurrency_safe: bool     # 可以和其他工具并行跑
```

目前有 23+ 个内置工具，分 6 类：

| 类别 | 工具数 | 举例 |
|------|--------|------|
| filesystem | 8 | file_read/write/delete, edit |
| retrieval | 13 | web_search, web_read, law_retrieve, arxiv_search |
| execution | 4 | bash, spawn |
| workspace | 3 | todowrite, research_state |
| skills | 2 | skill_use, skill_propose |
| plugins | 2+ | domain_sites |

**工具分类有什么用？** 模型看到的工具列表可以按需过滤——SubAgent 默认只有文件 + 检索工具，不允许执行 bash 或 spawn 子 Agent。config.yaml 里的 disabled_tools 也可以从全局禁用某些工具。

Tool 的 session 上下文通过 contextvars 注入：

```python
# AgentLoop 设置
set_session_context(work_dir=..., session_id=...)

# Handler 获取
work_dir = get_session_work_dir()
```

Handler 不需要显式传 session 参数，通过 contextvars 自动感知。

## Skill — 行为的指南

Skill 是纯 Markdown 文件，存放在 `skills/` 目录下。**它们不包含可执行代码。** 它们的作用是告诉 Agent"在这种场景下应该怎么做"。

```
skills/
├── long_form_research/SKILL.md      # 写报告的方法论
├── short_answer_research/SKILL.md   # 找答案的方法论
├── retrieval_strategy/SKILL.md      # 搜索策略
└── domain_sites/SKILL.md            # 各领域的权威网站
```

每个 Skill 文件有 YAML 头 + Markdown 正文：

```markdown
---
name: long_form_research
description: 结构化报告研究
when_to_use: 需要写分析报告时
allowed-tools: [web_search, workspace_search, file_write]
---
# 研究生命周期
1. 覆盖映射 → 2. 源策略 → 3. 采集 → ...
```

加载方式有两种：
- **手动**：Agent 调用 `skill_use("long_form_research")`
- **条件**：当 Agent 操作匹配路径的文件时自动加载（比如写 research/ 目录下的文件时）

### Tool vs Skill

简单粗暴的区分：

| | Tool | Skill |
|--|------|-------|
| 本质 | 你能做什么 | 你应该怎么做 |
| 形式 | Python 函数 | Markdown 文件 |
| 状态 | 有返回值 | 纯指令 |
| 发现 | 注册制 | 文件系统扫描 |

web_search 是一个 Tool，它让 Agent 能搜网页。但怎么搜、先搜什么后搜什么、搜不到怎么办——这些是 Skill 管的。
