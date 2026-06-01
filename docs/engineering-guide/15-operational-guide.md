# 运营架构

AgentOS 的运行时架构——从启动到数据流，到可观测性。

## 一、启动架构

```
cli.py main()
    │
    ├── check_api_keys()
    │     └── 验证 provider 对应的 API key 是否存在
    │
    ├── AgentOS.__init__()
    │     ├── Settings（config.yaml + .env → dataclass）
    │     ├── SQLiteStore（初始化 6 表 + FTS5 + WAL）
    │     ├── SessionManager（session 读写代理）
    │     ├── ToolRegistry（注册 23+ 工具 + plugins）
    │     ├── SkillLoader（文件发现 skills/*/SKILL.md）
    │     ├── ContextCompiler（system prompt 编译器）
    │     ├── SessionRetriever（FTS5 + embedding + RRF）
    │     ├── WorkspaceMemory（文件同步 + artifact 管理）
    │     ├── InterruptScheduler（提醒轮询）
    │     ├── MineruClient（文档解析 HTTP 客户端）
    │     └── AgentLoop（ReAct 循环）
    │
    ├── AgentOS.start()
    │     ├── scheduler.start()         ← 提醒轮询启动
    │     └── agent_loop.warmup_session_cache()
    │
    └── CLI 主循环（prompt_toolkit / 管道）
```

## 二、数据流架构

### 运行时数据流

```
用户输入 → AgentLoop.process()
  │
  ├── 准备阶段
  │   ├── 估算 token → 超阈值？→ 压缩 + fork
  │   ├── 编译上下文（agent_system.txt + 工作区文件 + skills）
  │   └── 构建 messages 数组
  │
  ├── ReAct 循环
  │   ├── model.chat.completions.create()    ← 外部 API
  │   ├── 解析 response → tool_call or content
  │   ├── 执行工具 → 过滤/压缩/归档
  │   └── 循环直到完成或中断
  │
  └── 结束阶段
      ├── yield ContentEvent / ErrorEvent
      └── 写入 run_events.jsonl
```

### 持久化流

```
Agent 操作 → 写入 SQLite + 文件系统

messages 表         ← 每轮对话追加
artifacts 表        ← file_write / artifact_upsert 时写入
chunks 表           ← artifact 分块 + embedding
reminders 表        ← reminder_create 时写入
interventions 表    ← 人工干预时写入
sessions 表         ← create / compress / close 时变更

work_dir 文件系统：
  uploads/          ← 用户上传（只读）
  research/         ← Agent 研究成果
  drafts/           ← Agent 生成文档
  raw_search/       ← 检索原始结果（自动归档）
  logs/             ← run_events.jsonl
```

### 事件流（两个系统）

```
系统内部：EventBus（pub/sub）
  scheduler → EventBus → 其他组件
  用途：定时提醒、session 变更通知

用户面向：AsyncGenerator（顺序流）
  AgentLoop → process() → yield → CLI/TUI/API
  用途：流式显示、渲染
```

## 三、可观测性架构

### 运行时事件日志

每个 session 的 `logs/run_events.jsonl` 记录了完整的事件流，包含：

| 事件类型 | 包含信息 | 用途 |
|---------|---------|------|
| activity (context.compiled) | prompt 结构、文件列表 | 调试上下文组成 |
| activity (model.completed) | prompt_tokens, cache_hit_tokens, duration | 成本分析 |
| tool_call | 工具名、参数 | 行为分析 |
| tool_result | 成功/失败、耗时 | 健康监控 |
| session.compressed | 新旧 session ID, token 变化 | 压缩频率监控 |
| error | 错误信息、快照路径 | 异常追踪 |

### KV cache 命中率

`model.completed` 事件 payload 中的 `prompt_cache_hit_tokens` 和 `prompt_tokens` 可用于计算有效缓存命中率。这是成本优化的核心指标。

### 故障恢复机制

两级内容过滤恢复：

```
软恢复：删除最近 user+assistant 消息 → 重试
  └── 适用：单次内容过滤

硬恢复：构建"系统仅"恢复上下文 → 跳过最近 2 轮 tool 调用
  └── 适用：连续内容过滤失败
```

## 四、配置架构

### 分层

```
config.yaml          ← 所有运行参数（模型、超时、阈值、工具开关）
.env                 ← 仅存放 API keys
AgentOS 构造参数     ← 运行时覆盖（data_dir, model, enabled_tools）
```

### Provider 自动推导

```python
provider = "deepseek"  →  base_url = api.deepseek.com
                       →  api_key = DEEPSEEK_API_KEY

provider = "dashscope" →  base_url = dashscope.aliyuncs.com/compatible-mode/v1
                       →  api_key = OPENAI_API_KEY
```

### Proxy 保护

API 域名自动加入 `NO_PROXY`，防止 HTTP_PROXY 劫持模型 API 调用。

## 五、部署结构

```
项目根目录
├── config.yaml       ← 运行参数
├── .env              ← 密钥
├── cli.py            ← 入口
├── agent_os/         ← 核心代码
├── skills/           ← 零代码工作流
├── data/             ← 运行时数据（自动创建）
│   ├── agent_os.db   ← SQLite
│   └── sessions/     ← 各 session work_dir
└── scripts/          ← 工具脚本（评测等）
```

### 外部依赖

- Python >= 3.11
- SQLite 3（内置）
- API Keys（至少一个 LLM provider）
- 可选：Tavily / Jina / MinerU / Feishu
