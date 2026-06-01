# Session 生命周期

## 状态机

```
create() ──→ active
                │
                ├── close() ──→ closed (软删除，可恢复)
                │
                ├── compress() ──→ compressed (父 session)
                │     │
                │     └── fork ──→ active (子 session)
                │
                └── delete() ──→ 物理删除 + 文件删除
```

## 创建流程

`agent_os/core/session.py` + `agent_os/agent_os.py:192`

```python
async def create_session(name, description, stage, initial_files):
    # 1. 生成 ID 和 work_dir
    session_id = uuid.uuid4()[:12]
    safe_name = slugify(name)
    work_dir = f"data/sessions/{session_id}_{safe_name}/"
    
    # 2. 创建目录结构
    _ensure_default_workspace(work_dir, profile)
    #   ├── SOUL.md        — Agent 人格
    #   ├── AGENT.md       — 行为指南
    #   ├── MEMORY.md      — 长期记忆
    #   ├── todo.md        — 初始待办
    #   ├── uploads/       — 只读
    #   ├── research/
    #   ├── drafts/
    #   ├── raw_search/
    #   └── logs/
    
    # 3. 写入初始文件
    for name, content in (initial_files or {}).items():
        (work_dir / name).write_text(content)
    
    # 4. 索引初始文件到 artifact 表
    workspace_memory.sync_work_dir(session_id, work_dir)
    
    # 5. SQLite 写入 sessions 表
    store.insert_session(session)
    
    return session
```

### workspace 模板

默认文件内容：

```markdown
# SOUL.md
你是 AgentOS, 一个专业的深度研究助手...

# AGENT.md
当前 session 的行为指南...

# MEMORY.md
Session 运行过程中积累的重要事实和发现...
```

可通过 `workspace.files` 在 config.yaml 中自定义。

## 消息生命周期

```
Agent 收到 user message
    │
    ├── SQLite 存储 (messages 表, kind="user")
    │
    ├── context_compiler.compile() 中加载历史消息
    │     └── max_context_messages = 8 (可配)
    │
    ├── model 处理
    │     ├── assistant 回复 → 存储 (messages 表, kind="assistant")
    │     └── tool_calls → 存储 (messages 表, kind="tool_call")
    │
    └── tool 执行
          └── results → 存储 (messages 表, kind="tool")
```

### 检索上下文时的加载逻辑

```python
# context_compiler 加载消息时:
1. 从 SQLite 加载所有消息 (按创建时间排序)
2. 只取最近 max_context_messages 条
3. 如果超过 token 阈值 → 走压缩路径
4. 否则全部加载
```

## 压缩与 Fork

`agent_os/kernel/agent_loop.py` 中实现。

### 触发条件

```python
if total_prompt_tokens > context_token_threshold:  # 600K
    new_session_id = await compress_session(session_id)
```

### Fork 语义

```
Parent Session (v1, status=compressed)
    │
    ├── work_dir = data/sessions/{id}_name/
    ├── 完整消息历史在 SQLite（不删除）
    ├── compression_state.md 写入 work_dir
    │
    └── Child Session (v2, status=active)
        ├── work_dir = 同上（共享！）
        ├── 继承 todo_list
        ├── 继承 SOUL.md/AGENT.md/MEMORY.md
        ├── compression_version = 2
        ├── parent_session_id = parent.id
        └── 第一条消息 = [COMPACTION v1] + <chronology>摘要
```

**work_dir 共享的意义**：压缩后，子 session 能读取父 session 写入的所有文件。事件、检索结果、草稿都在。

**messages 表关联**：父 session 的 messages 不删除。通过 `parent_session_id` 可追溯完整历史。

### 压缩状态文件

写入 `compression_state.md`：

```markdown
# Compression State v1

- compressed_at: 2026-05-27T10:00:00Z
- forked_to: abcdef123456
- original_session: 123456789abc
- estimated_tokens_before: 625000
- estimated_tokens_after: 85000
- compression_ratio: 7.4x
- preserved_turns:
  - head: 3 (turns 1-3)
  - tail: 8 (turns 14-21)
  - key_decisions: [turn_5, turn_9, turn_12]
```

## 关闭与删除

### 关闭 (soft)

```python
session.status = "closed"
# 不删除文件
# 不删除 SQLite 记录
# 可恢复
```

### 删除 (hard)

```python
# 1. 删除 SQLite 记录（CASCADE 删除关联数据）
store.delete_session(session_id)

# 2. 删除 work_dir
shutil.rmtree(session.work_dir)

# 3. 清理缓存
agent_loop.cleanup_session(session_id)
```

## 跨压缩链的工件查询

`agent_os/storage/sqlite_store.py` — 一次 SQL 查询覆盖所有 fork session：

```sql
SELECT c.* FROM chunks c
JOIN artifacts a ON c.artifact_id = a.id
JOIN sessions s ON a.session_id = s.id
WHERE s.work_dir = ?
ORDER BY c.embedding <-> ?  -- cosine distance
LIMIT ?
```

**设计要点**：
- 使用 `work_dir JOIN` 而非递归遍历 `parent_session_id`
- O(1) SQL，不做 O(N) 循环
- embedding 余弦距离排序
