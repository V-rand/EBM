# 工具系统

## 架构总览

AgentOS 的工具系统受 Hermes 协议启发，采用**注册—依赖注入—上下文变量**三分离模式：

```
┌──────────────────────────────────────────────────┐
│                  ToolRegistry                      │
│  ┌──────────────┐  ┌────────────┐                │
│  │  register()  │  │ retain_only│                │
│  │  get_entry() │  │ get_avail. │                │
│  └──────────────┘  └────────────┘                │
│         │                                         │
│         ▼                                         │
│  ┌──────────────────────────────────────────┐     │
│  │              ToolEntry                    │     │
│  │  name / toolset / schema / handler       │     │
│  │  max_result_chars / concurrency_safe     │     │
│  │  read_only                               │     │
│  └──────────────────────────────────────────┘     │
└──────────────────────────────────────────────────┘
         │
         ▼ (contextvars 注入)
┌──────────────────┐    ┌──────────────────────┐
│ set_session_ctx  │    │   set_tool_deps()    │
│ work_dir         │    │   session_manager    │
│ session_id       │    │   retriever          │
│                  │    │   workspace_memory   │
│                  │    │   mineru_client      │
└──────────────────┘    └──────────────────────┘
```

### 注册模式

```python
# agent_os/tools/base_tools.py
def register_filesystem_tools(r: ToolRegistry):
    r.register("file_read", "filesystem", {
        "name": "file_read",
        "description": "...",
        "parameters": {...},
    }, handler=handle_file_read, read_only=True)
```

每个模块导出一个 `register_*_tools(r)` 函数，在 `agent_os/tools/__init__.py:register_all()` 中统一调用。

### 工具分类

| 工具集 (toolset) | 包含工具 | 数量 |
|-----------------|---------|------|
| `filesystem` | file_read/write/append/delete/list/grep/tree, edit | 8 |
| `execution` | bash, spawn, send_message, task_stop | 4 |
| `workspace` | todowrite, reminder_create, research_state | 3 |
| `retrieval` | web_search, web_read, workspace_search, law_retrieve, case_retrieve, arxiv_search, crossref_search, openalex_works, openalex_entity, wikipedia_lookup, pubmed_search, opencitations_search, github_search | 13 |
| `skills` | skill_use, skill_propose | 2 |
| `plugins` | domain_sites, word_count (auto-discovered) | 2+ |

### 会话上下文注入

通过 `contextvars` 实现零参数的 session 感知：

```python
# 设置（AgentLoop 在每次 dispatch 前）
from agent_os.tools.registry import set_session_context
set_session_context(work_dir="/data/sessions/abc123_mycase", session_id="abc123")

# 读取（Handler 内部）
from agent_os.tools.registry import get_session_work_dir, get_session_id
work_dir = get_session_work_dir()  # → "/data/sessions/abc123_mycase"
```

### 基础设施注入

全局共享的依赖在启动时一次性注入：

```python
# AgentOS.__init__()
set_tool_deps(
    session_manager=self.sessions,
    workspace_memory=self.workspace_memory,
    retriever=self.retriever,
    mineru_client=self.mineru_client,
    skill_loader=self.skill_loader,
)
```

Handler 通过 `get_tool_dep("retriever")` 获取。

## 结果过滤机制

对外部检索工具（web_search, law_retrieve, case_retrieve 等），输出可能超过 10K 字符，需经过 `ResultFilterAgent` 压缩：

```
外部检索结果 (50K+ chars)
        │
        ▼
ResultFilterAgent (LLM 压缩)
        │
        ├── 保留引文关键信息
        ├── 缩短篇幅（典型压缩比 10:1）
        ├── 标注置信度
        │
        ▼
压缩后结果 (<5K chars) → 模型上下文

原始完整结果 → raw_search/ 归档 → 可 file_read 获取全文
```

### 触发条件

- 结果 > `result_filter_threshold` (默认 5000 chars)
- 工具属于 `_FILTERABLE_TOOLS` (当前仅为 `workspace_search`)
- 注意：web_search 等外部检索工具也有硬编码的 `max_result_chars` 限制

## 工具超时与限流

所有工具都有独立的超时配置：

```yaml
# config.yaml
tool_timeouts:
  bash_default: 60
  law_retrieve: 30
  case_retrieve: 30
  web_search: 20
  web_read: 20

tool_output_limits:
  bash_stdout_max_chars: 100000
  bash_stderr_max_chars: 20000
  result_filter_threshold: 5000
```

## Plugin 系统

`agent_os/tools/plugins/__init__.py`

自动发现机制：

```python
def discover_plugins(registry: ToolRegistry):
    plugins_dir = Path(__file__).parent
    for f in sorted(plugins_dir.iterdir()):
        if f.suffix != ".py" or f.name.startswith(("_", "sample_", "example_")):
            continue
        mod = importlib.import_module(f"agent_os.tools.plugins.{f.stem}")
        if hasattr(mod, "register"):
            mod.register(registry)
```

插件必须暴露 `register(registry)` 函数。

## 工具开发规范

1. **总是返回 ToolResult** — `ToolResult.ok(data)` 或 `ToolResult.fail(error)`
2. **标记只读** — `read_only=True` 豁免于安全检查
3. **设置 toolsets** — 正确分类便于过滤
4. **避免内部 import** — 减少延迟
5. **编写 description txt** — 工具的描述会影响模型调用频率和参数质量
6. **结果截断** — 设置合理的 `max_result_chars`

## 现有工具完整列表

| 工具名 | 工具集 | handler 文件 | read_only | 说明 |
|--------|--------|-------------|-----------|------|
| file_read | filesystem | base_tools.py | ✓ | 带 offset/limit，有 dedup cache |
| file_write | filesystem | base_tools.py | | 覆盖或新建 |
| file_append | filesystem | base_tools.py | | 追加到文件末尾 |
| file_delete | filesystem | base_tools.py | | 有 research/ 目录安全保护 |
| file_list | filesystem | base_tools.py | ✓ | 目录列表 |
| file_grep | filesystem | base_tools.py | ✓ | 工作区文件内正则搜索 |
| file_tree | filesystem | base_tools.py | ✓ | 递归目录树 |
| edit | filesystem | base_tools.py | | find-and-replace，精确+规范化回退 |
| bash | execution | base_tools.py | | 命令执行，安全过滤，大输出持久化 |
| spawn | execution | base_tools.py | | 子 Agent，隔离 session |
| send_message | execution | base_tools.py | | 给子 Agent 发消息 |
| task_stop | execution | base_tools.py | | 停止子 Agent |
| todowrite | workspace | base_tools.py | | 替换 todo 列表 |
| reminder_create | workspace | base_tools.py | | 定时提醒 |
| research_state | workspace | base_tools.py | | 思考草稿纸 |
| upload_parse | filesystem | base_tools.py | | PDF/DOCX 解析 |
| workspace_search | retrieval | base_tools.py | ✓ | 混合检索 |
| law_retrieve | retrieval | base_tools.py | ✓ | 法规检索（得理 API） |
| case_retrieve | retrieval | base_tools.py | ✓ | 案例检索（得理 API） |
| web_search | retrieval | search.py | ✓ | 网络搜索 |
| web_read | retrieval | web.py | ✓ | 网页读取 |
| wikipedia_lookup | retrieval | media.py | ✓ | 维基百科 |
| arxiv_search | retrieval | academic.py | ✓ | arXiv 论文 |
| crossref_search | retrieval | academic.py | ✓ | CrossRef DOI |
| openalex_works | retrieval | openalex.py | ✓ | OpenAlex 论文 |
| openalex_entity | retrieval | openalex.py | ✓ | OpenAlex 实体 |
| opencitations_search | retrieval | opencitations.py | ✓ | OpenCitations 引用 |
| pubmed_search | retrieval | pubmed.py | ✓ | PubMed 生物医学 |
| github_search | retrieval | github.py | ✓ | GitHub 搜索 |
| skill_use | skills | skills.py | ✓ | 加载 skill |
| skill_propose | skills | skills.py | ✓ | 提出新 skill |
| domain_sites | plugins | plugins/domain_sites.py | ✓ | 领域网站查询 |
| word_count | plugins | plugins/sample_word_count.py | ✓ | 示例插件 |
