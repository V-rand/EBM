# 扩展系统架构

AgentOS 的扩展通过三个正交的维度实现：**Tools**（能力）、**Skills**（指令）、**Plugin**（自动发现）。它们各自有不同的抽象层次和设计目的。

## 扩展架构全景

```
┌──────────────────────────────────────────────────────────────┐
│                    扩展方式对比                                 │
│                                                              │
│              Tools              Skills             Plugins    │
│  ┌─────────────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │ 可执行 Python 代码   │ │ 纯 Markdown   │ │ 自动发现工具  │  │
│  │ 有外部调用能力       │ │ 无执行能力    │ │ 轻量、独立    │  │
│  │ 有状态（返回值）     │ │ 无状态        │ │ 免手动注册    │  │
│  │ 手动注册            │ │ 文件发现      │ │ importlib    │  │
│  └─────────────────────┘ └──────────────┘ └──────────────┘  │
│         │                      │                 │           │
│         ▼                      ▼                 ▼           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              AgentOS 内核（不变的部分）                │   │
│  │  Session | AgentLoop | Storage | Memory | Scheduler  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│             配置层（config.yaml + .env）                      │
│        控制启用/禁用、超时、阈值、密钥                         │
└──────────────────────────────────────────────────────────────┘
```

## 一、Tool 扩展架构

### 注册模式

`agent_os/tools/registry.py`

工具扩展采用**声明式注册**模式：

```
工具模块 → register() → ToolRegistry → 模型可见
                            │
                      ToolEntry {
                        name,         # 唯一标识
                        toolset,      # 分类（影响过滤策略）
                        schema,       # 模型看到的 function calling schema
                        handler,      # 实际执行逻辑
                        read_only,    # 不影响状态
                        concurrency_safe  # 可并行
                      }
```

**关键抽象**：`ToolResult` 是所有工具的**唯一返回值类型**。`ToolResult.ok(data)` 成功，`ToolResult.fail(error)` 失败。消费者（AgentLoop）统一处理成功/失败，不需要感知具体工具的错误处理方式。

### 工具分类的意义

`toolset` 不仅是标签，它决定了：

| toolset | 过滤策略 | 结果处理 | 示例 |
|---------|---------|---------|------|
| filesystem | 路径沙箱检查 | 直接返回 | file_read, file_write |
| retrieval | ResultFilterAgent 压缩 | 归档 raw_search/ | web_search, law_retrieve |
| execution | 超时控制 | 大输出截断 | bash, spawn |
| workspace | 事件通知 | 持久化到 DB | todowrite, reminder_create |
| skills | 条件路径激活 | 注入 skill 内容 | skill_use |

### 会话上下文机制

`contextvars` 实现了**零参数的 session 感知**：

```python
# AgentLoop 在每次工具分发前设置：
set_session_context(work_dir=..., session_id=...)

# Handler 中无需额外参数即可获取：
from ..registry import get_session_work_dir, get_session_id
```

基础设施依赖通过 `set_tool_deps()` 一次性注入，而非每个 handler 构造自己的依赖。

### 设计约束

- Handler 必须是 async 函数（AgentLoop 全异步）
- 不能 import 其他工具（通过 `get_tool_dep("name")` 访问共享服务）
- 路径操作必须经过 `_safe_workspace_path()` 沙箱

## 二、Skill 扩展架构

### 零代码工作流

Skill 是纯 Markdown 文件，不含可执行代码。它是对 Agent 行为的**指令性约束**，不是自动化脚本。

```
skills/<domain>/SKILL.md
         │
         ├── YAML frontmatter（元数据、触发条件）
         └── Markdown body（状态机、约束、输出规范）
```

### 激活机制（两种模式）

**手动激活**：Agent 调用 `skill_use("name")` 工具，完整 SKILL.md 内容作为 tool result 注入对话。

**条件激活**：当 Agent 操作匹配路径的文件时（如写入 `research/` 下的文件），自动加载 path 配置匹配的 skill。

### 与 KV cache 的协作

只有 skill 的 name + description 出现在 system prompt 的 skills index 中。完整内容通过 tool result 按需加载，不污染 KV cache prefix。

### Schema

```yaml
---
name: <唯一标识>
layer: system | domain      # 加载优先级
description: <简述>
when_to_use: <触发场景指引>
allowed-tools: [...]        # 此 skill 可用的工具
paths:                      # 条件激活路径
  include: ["dir/"]
  exclude: ["**/temp/**"]
profile:                    # 工作区模板
  folders: []
  files: {}
---
```

## 三、Plugin 扩展架构

### 自动发现机制

`agent_os/tools/plugins/__init__.py`

Plugin 是工具的自动发现子集。通过文件系统扫描 + importlib 加载，无需手动注册：

```python
for .py file in plugins/:
    if not starts with "_" / "sample_" / "example_":
        import_module(file)
        if hasattr(mod, "register"):
            mod.register(registry)
```

### 适用场景

- 独立、可复用的轻量工具（如 domain_sites）
- 与主项目耦合度较低的扩展
- 第三方贡献的工具

## 四、配置扩展架构

### 两层分离

```
config.yaml（运行参数）          .env（密钥）
     │                                │
     └──────────┬─────────────────────┘
                ▼
         Settings dataclass
```

- `config.yaml` 控制所有行为参数（模型、超时、阈值、工具开关）
- `.env` 仅存放 API keys
- `provider` 字段自动推导 base_url 和 key 的环境变量名
- `NO_PROXY` 自动配置保护模型 API 不被代理劫持

### 工具级的控制

| 机制 | 作用域 | 实现 |
|------|--------|------|
| disabled_tools | 全局 | `registry.retain_only()` 过滤 |
| enabled_tools | 构造时 | AgentOS 初始化时设置 |
| allowed_tools | SubAgent | 子 agent 工具白名单 |

## 五、三个扩展维度的关系

```
Tool 和 Skill 的关系
══════════════════════
Tool：你能做什么（执行能力）
Skill：你应该怎么做（行为指导）

一个 Tool + 多个 Skill → 不同的行为模式
例：web_search 在不同 skill 下的搜索策略不同

Plugin 是 Tool 的子集
══════════════════════
Plugin 本质是自动注册的 Tool
同等的注册能力，不同的发现方式

配置层是横切关注点
══════════════════════
不影响各扩展本身的逻辑，但控制其启用状态和行为参数
```
