# EBM Agent OS 架构

## 总览

```
┌─────────────────────────────────────────┐
│              CLI (cli.py)               │  Rich TUI + prompt_toolkit
├─────────────────────────────────────────┤
│            AgentOS 组装层                │  Session / Config / Skills / Tools
├─────────────────────────────────────────┤
│            Kernel (核心引擎)             │  AgentLoop (ReAct) / SubAgent
├──────────────┬──────────────────────────┤
│   Memory     │      Storage             │
│ Context      │  SQLite (FTS5 + Embed)   │
│ Compiler     │  Session state           │
│ Workspace    │  Artifacts / Messages     │
└──────────────┴──────────────────────────┘
```

## 核心模块

### AgentLoop — ReAct 主循环

```
用户输入 → compile context → model API → parse tool calls → execute tools → observe → loop
```

每轮：模型决策（thinking）→ 工具调用（并行执行）→ 结果注入上下文 → 下一轮。直到模型输出 final answer 或达到 max_iterations（默认 64）。

关键守护机制：
- **blind_search_guardrail**：连续 9 轮纯检索未写 research_state → 提醒
- **calm_nudge**：第 8/15 轮注入冷静提示，防止焦虑性加速
- **todo_nudge**：待办事项长期未更新 → 提醒同步

### SubAgent — 子 Agent

独立会话、共享工作区、可并行。用于引用验证等可分派任务。子 Agent 不能 spawn 子 Agent。

### 工具体系

| 分类 | 工具 |
|------|------|
| EBM 检索 | pubmed_search, cochrane_search, clinical_trials, medrxiv_search |
| 学术检索 | openalex_works, openalex_entity, opencitations_search |
| 网络 | web_search (Tavily/Serper), web_read (Jina/Firecrawl/Trafilatura) |
| 文件 | file_read/write/append/delete/list/grep/tree/edit |
| 工作区 | workspace_search (FTS5+Embedding 混合检索) |
| 任务 | todowrite, research_state, reminder_create |
| 技能 | skill_use, skill_propose |
| 子 Agent | spawn, send_message, task_stop |
| 执行 | bash, upload_parse (MinerU PDF/Office 解析) |

### Skills 系统

Skills 是纯 Markdown 工作流定义。系统提示注入 `<available_skills>` 索引（name + description），模型调用 `skill_use(name)` 加载正文。Skills 内容作为 tool result 进入对话历史，不修改 system prompt（保护 KV Cache）。

### 上下文编译

每次模型请求前编译 system prompt：角色 + 研究哲学 + 工具表 + 技能索引 + 工作区文件树 + 记忆指导 + 最近 N 条消息。动态内容（时间戳、domain_hint）作为 user message 追加，保持 system prompt 前缀稳定以利用 DeepSeek KV Cache（实测 90-98% 命中）。

### Session 工作区

每个 session 独立目录 `data/sessions/{id}_{name}/`：
```
├── uploads/      ← 用户上传材料（只读）
├── research/     ← 研究笔记、报告、memory/
├── drafts/       ← 草稿（验证后 cp 到 research/）
├── raw_search/   ← 检索结果自动归档
├── logs/         ← 运行日志
├── AGENT.md      ← agent 执行规则
├── SOUL.md       ← 研究品格
└── MEMORY.md     ← 跨 session 记忆索引
```

### EBM 研究管线（5A+A）

```
Ask → Acquire → Appraise → Apply → Audit → 输出
 │       │         │          │        │
PICO    Guideline  GRADE     CAT/      self-
        → SR       逐跳      Synthesis  audit
        → RCT      评级
```

## Provider 支持

| Provider | Base URL | 说明 |
|----------|----------|------|
| DeepSeek | api.deepseek.com | 当前使用，KV Cache 90%+ |
| DashScope | dashscope.aliyuncs.com | 阿里云百炼（兼容模式） |

通过 `config.yaml` 切换 provider。模型通过 OpenAI 兼容 API 调用，`reasoning_effort` 控制思考深度。

## 网络策略

| 服务 | 代理 | 原因 |
|------|------|------|
| Jina (web_read) | 走代理 | 国内需代理 |
| Firecrawl/Trafilatura (web_read) | 直连 | 回退方案 |
| Tavily/Serper (web_search) | 直连 | 直连可用 |
| PubMed/OpenAlex/Cochrane 等学术 API | 直连 | `trust_env=False` |
| MinerU | 直连 | `trust_env=False` |

## 数据流

```
用户输入 → context_compiler → system prompt + messages
  → model API (DeepSeek) → thinking + tool_calls
  → tool handlers (async parallel) → tool results
  → result archiver → raw_search/*.md
  → messages 注入 → 下一轮 model API
  → ... → final answer → self-audit → 输出
```
