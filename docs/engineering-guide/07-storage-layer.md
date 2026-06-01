# SQLite 持久化层

## 表结构

`agent_os/storage/sqlite_store.py` — 6 张核心表 + FTS5。

### 实体关系图

```
sessions (1) ──── (N) messages
   │                    │
   │                    │
   ├── (N) artifacts ── (N) chunks
   │
   ├── (N) reminders
   │
   └── (N) interventions
```

### sessions

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,          -- active / compressed / closed
    stage TEXT NOT NULL,           -- intake / research / ...
    work_dir TEXT NOT NULL,
    todo_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    parent_session_id TEXT,        -- 压缩链
    compression_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(parent_session_id) REFERENCES sessions(id)
);
```

- `todo_json` 和 `metadata_json` 是 JSON 字符串（SQLite 不原生支持 JSON）
- `parent_session_id` 指向压缩前的父 session
- `status = "compressed"` 保留完整历史但不再活跃

### messages

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,            -- system / user / assistant / tool
    content TEXT NOT NULL,
    kind TEXT NOT NULL,            -- user / assistant / tool_call / tool / system
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
```

- 使用 AUTOINCREMENT 整数 ID 保证顺序
- `kind` 区分 assistant 的回复文本和工具调用
- `content` 对于 tool_call 类型的消息是 JSON 序列化的参数

### artifacts + chunks

```sql
CREATE TABLE artifacts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    path TEXT NOT NULL,            -- relative path in work_dir
    content TEXT NOT NULL,
    artifact_type TEXT NOT NULL,   -- note / research / draft / ...
    title TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding TEXT,                -- JSON array of floats
    source_path TEXT,
    chunk_index INTEGER,
    FOREIGN KEY(artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE
);
```

分表设计目的：
- `artifacts` 是文件级元数据（路径、类型、标题）
- `chunks` 是片段级数据（内容 + embedding）
- 分块后一个文件对应多个 chunks

### reminders

```sql
CREATE TABLE reminders (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    reminder_type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    fire_at TEXT NOT NULL,          -- ISO datetime
    priority INTEGER NOT NULL,     -- 1-3
    status TEXT NOT NULL,          -- pending / fired / cancelled
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    fired_at TEXT,                 -- 实际触发时间
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
```

- scheduler 轮询 `status = "pending"` 且 `fire_at <= now()` 的记录
- 触发后标记 `status = "fired"`

### interventions

```sql
CREATE TABLE interventions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL,          -- pending / applied / rejected
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    applied_at TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
```

人工干预记录。`kind` 不带在表结构中（仅有 content + status），metadata 可携带额外信息。

## FTS5 全文索引

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS artifact_fts USING fts5(
    content, content=artifacts, content_rowid=rowid
);

-- 自动同步
CREATE TRIGGER IF NOT EXISTS artifacts_ai AFTER INSERT ON artifacts BEGIN
    INSERT INTO artifact_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS artifacts_ad AFTER DELETE ON artifacts BEGIN
    INSERT INTO artifact_fts(artifact_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS artifacts_au AFTER UPDATE ON artifacts BEGIN
    INSERT INTO artifact_fts(artifact_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO artifact_fts(rowid, content) VALUES (new.id, new.content);
END;
```

### FTS5 查询

```python
def fts_search(self, query, session_id, limit=20):
    # FTS5 使用 MATCH 操作符
    # 空格分隔的关键词自动做 AND 合并
    sql = """
    SELECT a.id, a.path, a.content, a.artifact_type, 
           a.title, a.summary, a.metadata_json,
           rank
    FROM artifacts a
    JOIN artifact_fts fts ON a.id = fts.rowid
    JOIN sessions s ON a.session_id = s.id
    WHERE artifact_fts MATCH ?
      AND s.work_dir = ?
    ORDER BY rank
    LIMIT ?
    """
```

## Embedding 存储

Vector 直接存储在 `chunks.embedding` 字段中，JSON 序列化：

```python
# 存储
embedding = await embedding_client.embed(chunk_content)
cursor.execute("UPDATE chunks SET embedding = ? WHERE id = ?", 
               [json.dumps(embedding), chunk_id])

# 查询（内存中计算余弦距离，无原生支持）
all_embeddings = cursor.fetchall()
scores = cosine_similarity(query_embedding, [e.embedding for e in all_embeddings])
```

**局限**：无原生向量索引，全量数据遍历。对于 10 万+ chunks 会有性能问题。

## WAL 模式

```python
self._conn.execute("PRAGMA journal_mode=WAL")
self._conn.execute("PRAGMA foreign_keys=ON")
```

- WAL（Write-Ahead Logging）允许多个读并发
- 写操作不阻塞读操作
- foreign_keys=ON 确保 CASCADE DELETE 生效

## 线程安全

```python
self._lock = threading.RLock()
```

使用可重入锁保护所有写操作。SQLite 连接是单线程创建的，但通过 `check_same_thread=False` 允许跨线程使用，辅以锁保护。

## 查询模式

### 跨 session 查询（按 work_dir）

```sql
SELECT * FROM artifacts a
JOIN sessions s ON a.session_id = s.id
WHERE s.work_dir = ?
```

这是跨压缩链查询的核心模式。一次 SQL 覆盖所有 fork session。

### 消息加载

```sql
SELECT * FROM messages 
WHERE session_id = ? 
ORDER BY id 
LIMIT ?
```

按 ID（创建顺序）排序，取最近的 N 条。

### 待办提醒轮询

```sql
SELECT * FROM reminders 
WHERE status = 'pending' 
  AND fire_at <= ? 
ORDER BY fire_at
```

Scheduler 定期执行（配置间隔，默认 30 秒）。
