# 工具设计分析：文件系统与文档解析

> 文件系统工具是 Agent 与工作区交互的基础。不同于简单的文件读写，AgentOS 的文件系统设计需要处理路径沙箱、大文件、并发、编码多样性等复杂问题。

## 文件系统工具集

`agent_os/tools/base_tools.py` — 8 个文件系统工具 + 1 个文档解析工具。

### 功能矩阵

| 工具 | 读/写 | 作用范围 | 安全保护 | 特殊能力 |
|------|-------|---------|---------|---------|
| file_read | 读 | 工作区任意文件 | 路径沙箱 | offset/limit 分段，dedup cache |
| file_write | 写 | 工作区任意文件 | 路径沙箱 | mkdir -p |
| file_append | 写 | 现有文件 | 路径沙箱 | 追加 |
| file_delete | 写 | 工作区文件 | research/ 目录保护 | 不可删除 research/ |
| file_list | 读 | 工作区目录 | 路径沙箱 | 目录列表 |
| file_grep | 读 | 工作区文件 | 路径沙箱 | 正则搜索 |
| file_tree | 读 | 工作区目录 | 路径沙箱 | 递归树 |
| edit | 写 | 现有文件 | 路径沙箱 | find-and-replace + 规范化回退 |
| upload_parse | 读 | uploads/ 目录 | 仅 uploads/ | MinerU + pymupdf |

## 路径沙箱：第一道防线

`agent_os/core/session.py:25` — `_safe_workspace_path()`

```python
def _safe_workspace_path(value: str) -> str:
    raw = str(value).strip().replace("\\", "/")
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or any(part in {".."} for part in path.parts):
        raise ValueError(f"Unsafe workspace path: {value}")
    return path.as_posix()
```

**防护机制**：
- 拒绝绝对路径（`/etc/passwd`）
- 拒绝目录遍历（`../../`）
- 统一路径分隔符（`\` → `/`）
- 所有文件操作前都经过此检查

### 文件系统层 vs 工具层

`FileSystem` (agent_os/core/filesystem.py) 是底层实现，工具是上层接口：

```
Tool (file_read) → FileSystem.read_file() → OS open()
     │                    │
  参数校验             路径拼接
  offset/limit         work_dir + safe_path
  dedup cache          缓存支持
```

这种分离的好处：工具层处理模型相关的逻辑（参数格式、缓存、事件），文件系统层处理物理 I/O。

## edit 工具：find-and-replace 的双模式

`agent_os/tools/base_tools.py:490`

### 精确模式（首选）

```python
# Agent 指定 old_string 和 new_string
# 完全匹配，替换第一次出现
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
if old_string in content:
    new_content = content.replace(old_string, new_string, 1)
```

### 规范化回退模式

当精确匹配失败时（常见于编码/空白差异）：

```python
# 去除空白差异后匹配
normalized = re.sub(r'\s+', ' ', content)
norm_old = re.sub(r'\s+', ' ', old_string)
if norm_old in normalized:
    # 找到位置后，用原文件的空白做替换
    ...
```

**为什么需要双模式**：LLM 生成的内容在不同调用间可能有不一致的空白、换行、缩进。精确模式在 80% 情况下工作，回退模式覆盖了剩余的 20%。

## upload_parse：文档解析管道

`agent_os/tools/base_tools.py:324`

### 解析优先级

```
User uploads PDF/DOCX/XLSX/图片
        │
        ▼
MinerU v1 API (轻量，快)
   → 失败
   → MinerU v4 API (Premium，更高精度)
       → 失败
       → pymupdf4llm (本地，PDF only)
           → 失败
           → doc2txt (.doc only，纯文本)
```

### MinerU 客户端设计

`agent_os/ingest/mineru.py`

```
MineruClient
  ├── parse_document_v1(url)      # /api/v1/agent 端点
  ├── parse_document_v4(url)      # /api/v4 端点 (Premium)
  └── doc2txt(file_path)          # .doc → text
```

**v1 vs v4**：

| 特性 | v1 (轻量) | v4 (Premium) |
|------|-----------|-------------|
| 端点 | `/api/v1/agent` | `/api/v4` |
| 模型 | 轻量版 | vlm 版 |
| 速度 | 快 (5-15s) | 慢 (30-60s) |
| 精度 | 一般 | ⭐ 高 |
| 格式支持 | PDF/DOCX/图片 | 同上 + 复杂布局 |

**轮询机制**（异步）：

```python
# v1 和 v4 都是异步轮询模式：
1. POST 文件 → 得到 task_id
2. 每 poll_interval_seconds(3s) 查询进度
3. 超时 poll_timeout_seconds(180s) → 失败回退
```

### pymupdf4llm 作为本地 fallback

当 MinerU 不可用时，使用 PyMuPDF4LLM 进行本地 PDF 转 Markdown。优点是无需 API，缺点是只支持 PDF。

### 上传文件保护

所有上传文件放在 `uploads/` 目录，通过 FileSystem 标记为**只读**：

```python
# Agent 无法通过 file_write/delete 修改 uploads/ 下的文件
# 只能读取和解析
```

## 文件操作的注意事项

### 大文件处理

- **分段读取**：file_read 支持 `offset` 和 `limit` 参数
- **大文件不一次加载**：`bash_stdout_max_chars` 限制输出大小
- **超出部分写入临时文件**：bash 工具的大输出写入 `raw_search/`

### 编码处理

- 所有文件操作使用 `utf-8` 编码
- `edit` 工具处理空白/编码差异
- 二进制文件通过 upload_parse 处理

### 并发安全

- `concurrency_safe: False` 写操作（file_write, file_append, file_delete, edit）
- 写操作不与其他工具并行 — 避免竞态
- 读操作（file_read, file_list, file_tree, file_grep）可并行

### 路径约定

AgentOS 没有强制路径约定，但在 AGENT.md 和提示词中推荐：
- `research/` — 研究成果、分析笔记
- `drafts/` — 生成文档、输出文件
- `raw_search/` — 外部检索原始结果（工具自动归档）
- `uploads/` — 用户上传（只读）
- `logs/` — 运行日志（自动写入）
