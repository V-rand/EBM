# 架构总览

## 一句话

AgentOS 是一个**通用深度研究智能体操作系统**。不是写死的 workflow 引擎，而是提供了一套基础设施——会话隔离、ReAct 循环、工具注册、上下文管理——让上层可以灵活地构建各种研究 Agent。业务逻辑通过 Skills（纯 Markdown）和 Tools（Python 能力）注入，kernel 本身不包含任何业务流程。

## 分层

```
用户界面层（纯消费者，不影响内核）
  CLI / TUI / API
       │
组装层（把各个组件粘起来）
  AgentOS — agent_os/agent_os.py
       │
内核层（核心循环）
  AgentLoop — agent_os/kernel/agent_loop.py
  ReAct: plan → action → observe → reflect
       │
基础服务层（被内核调用）
  Core: Session, EventBus, FileSystem
  Memory: ContextCompiler, Retriever, WorkspaceMemory
  Storage: SQLite + FTS5
       │
能力注入层（扩展点）
  Tools — 23 个内置 + plugins（Python 可执行）
  Skills — skills/ 目录下的 SKILL.md（纯 Markdown）
  Prompts — agent_os/prompts/*.txt（模板化）
```

## 核心设计思路

### 1. Kernel 保持通用

架构上最核心的约束：**kernel 不包含任何业务流程代码**。

- Session 管理、ReAct 循环、工具执行 — 属于 kernel
- 法律检索策略、研究报告方法论 — 属于 Skills
- 搜索、读写、执行 bash — 属于 Tools
- 研究哲学、工具优先级 — 属于 Prompts

这样做的原因是：法律场景只是默认入口，系统应该能用于各种研究场景——只需要换 Skills 和 Tools。

### 2. Session 就是隔离的工作区

每个 Session 相当于一个独立进程：有自己的目录、消息历史、工件。Session 之间完全隔离（法律保密性要求），唯一的交叉是通过共享 work_dir 文件来间接协作——压缩链中的父子 session 读写同一份文件。

### 3. KV cache 保护是第一优先级

DeepSeek 的 KV cache 价格差异很大（命中 0.02 元/M vs 未命中 1 元/M）。对于长期运行的 session，cache 命中率直接决定成本。所以系统 prompt 在 session 创建时就编译冻结，之后不再动态组装。动态内容通过 `<system-reminder>` 追加在消息尾部，不破坏已有的 cache prefix。

### 4. 事件是结构化字典

AgentLoop 不直接写终端，而是 yield 结构化的 TypedDict 事件。CLI、TUI、API 都是这些事件的消费者。这个分离意味着换前端不需要改内核。

## 数据怎么流

```
用户说了一句话 → AgentLoop.process()
  │
  ├── 1. 检查有没有定时提醒或调度消息要注入
  ├── 2. 估算 token → 超阈值？→ 压缩 + fork
  ├── 3. 编译上下文（拼 system prompt）
  │     ├── agent_system.txt（研究哲学）
  │     ├── SOUL.md / AGENT.md / MEMORY.md（session 设定）
  │     ├── Skills 索引（name + description）
  │     └── 追加动态内容
  │
  ├── 4. 发起模型调用
  │     └── 流式输出 thinking + content
  │
  ├── 5. 如果模型要调工具 → 执行
  │     ├── 外部检索 → 自动压缩 + 归档 raw_search/
  │     ├── 文件操作 → 检查路径安全
  │     └── 结果返回模型
  │
  ├── 6. 重复 4-5 直到模型给出最终答案
  │
  └── 7. yield ContentEvent 或 ErrorEvent
```

## 模块依赖

AgentOS 组装时把各个组件串起来：

```
AgentOS
  ├── Settings ← config.yaml + .env
  ├── SQLiteStore → 所有数据
  ├── SessionManager → session CRUD
  ├── ToolRegistry → 23+ 工具
  ├── SkillLoader → skills/ 目录扫描
  ├── WorkspaceMemory → 文件同步 + artifact
  ├── SessionRetriever → 混合检索
  ├── ContextCompiler → 拼 system prompt
  ├── InterruptScheduler → 定时提醒
  ├── MineruClient → 文档解析
  └── AgentLoop → 核心循环（依赖上面几乎所有组件）
```

## 关键的架构约束

- **不要在已有消息之间插入新消息** — 会破坏 KV cache prefix
- **不要在 kernel 里硬编码业务逻辑** — 业务走 Skills + Tools
- **不要修改 system prompt 结构** — cache 依赖固定的 XML 结构
- **SubAgent 不能创建 SubAgent** — 防止递归失控
- **文件操作必须在 work_dir 内** — `_safe_workspace_path()` 拒绝绝对路径和 `..`
