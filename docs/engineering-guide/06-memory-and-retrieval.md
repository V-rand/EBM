# 混合检索与 Memory 系统

## 架构概览

```
┌─────────────────────────────────────────────────┐
│               SessionRetriever                    │
│                                                   │
│   query → FTS5 (关键词) + Embedding (语义) → RRF │
│            ↕                    ↕                  │
│       SQLiteStore          EmbeddingClient         │
│       (FTS5 索引)          (DashScope API)         │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│             WorkspaceMemory                       │
│                                                   │
│   artifact upsert → chunking → embed → store     │
│   sync_work_dir → diff → index new files          │
│   lineage tracking                          │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│             ContextCompiler                       │
│                                                   │
│   session + message → system prompt               │
│     ├── agent_system.txt                          │
│     ├── SOUL.md / AGENT.md / MEMORY.md            │
│     ├── Skill profiles + skills index             │
│     ├── Memory guidance                           │
│     └── Retrieved items (FTS+embedding results)   │
└─────────────────────────────────────────────────┘
```

## 混合检索：SessionRetriever

`agent_os/memory/retriever.py`

### 三路融合

```python
async def search(session_id, query, limit=8, work_dir=None):
    # 1. FTS5 全文检索
    fts_results = await store.fts_search(query, session_id, limit=limit*2)
    
    # 2. Embedding 语义检索
    query_embedding = await embedding_client.embed(query)
    emb_results = await store.vector_search(query_embedding, session_id, limit=limit*2)
    
    # 3. RRF 融合
    results = reciprocal_rank_fusion(
        [fts_results, emb_results],
        k=60  # RRF 常数
    )
    
    return results[:limit]
```

### FTS5 索引

SQLite FTS5 全文索引：

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS artifact_fts USING fts5(
    content, content=artifacts, content_rowid=rowid
);

-- 自动同步触发器
CREATE TRIGGER artifacts_ai AFTER INSERT ON artifacts BEGIN
    INSERT INTO artifact_fts(rowid, content) VALUES (new.id, new.content);
END;
```

- 支持中文分词吗？使用 SQLite FTS5 的 unicode61 tokenizer，对 CJK 字符按单字索引。大规模中文文本的搜索可能不如专用分词器。
- 更新同步：DELETE+INSERT 触发器

### Embedding

`agent_os/memory/embedding.py`

```python
class EmbeddingClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
        )
    
    async def embed(self, text: str) -> list[float]:
        resp = await self.client.embeddings.create(
            model="text-embedding-v4",  # DashScope
            input=text,
            dimensions=1024,
        )
        return resp.data[0].embedding
```

- 模型：DashScope text-embedding-v4
- 维度：1024
- 降级：API key 不可用时返回空列表
- 存储：JSON 序列化到 `chunks.embedding` 字段

### 检索范围

```python
# 跨 session（同一 work_dir）
SELECT a.* FROM artifacts a
JOIN sessions s ON a.session_id = s.id
WHERE s.work_dir = ?
AND ...
```

设计意图：压缩后的子 session 需要能检索父 session 的工件。

## WorkspaceMemory：工件管理

`agent_os/memory/workspace.py`

### 工件生命周期

```
file_write / upload_parse / artifact_upsert
    │
    ▼
WorkspaceMemory.upsert_artifact(session_id, path, content, type)
    │
    ├── 写入或更新 DB (artifacts 表)
    ├── chunking (按段落/大小切分)
    ├── 触发后台 embedding 任务
    ├── 存储 chunk → embedding 向量
    └── 追踪 lineage（来源文件、转换链）
```

### Chunking 策略

```python
def chunk_document(content: str, max_chunk_size=1000):
    # 1. 按段落分割
    paragraphs = content.split('\n\n')
    # 2. 合并小段落
    # 3. 分割大段落（超过 max_chunk_size）
    # 4. 返回 chunk 列表 + 位置索引
```

简单文档分块策略：
- 按双换行分块（段落边界）
- 块大小约 1000 字符
- 不重叠（后续可改进）

### sync_work_dir：文件同步

启动时或文件变更时，扫描 work_dir 中的文件到 artifact 表：

```python
async def sync_work_dir(session_id, work_dir):
    # 遍历 work_dir 中的文件
    # 计算 hash 对比上次同步
    # 新增/变更文件 → upsert_artifact
    # 删除文件 → 标记删除
```

### Lineage 追踪

```python
# uploads/case.pdf → drafts/case_summary.md
metadata = {
    "lineage": {
        "source": "uploads/case.pdf",
        "derived_from": ["uploads/case.pdf"],
        "pipeline": "upload_parse → extract_facts → summarize",
        "tool_calls": [
            {"tool": "upload_parse", "timestamp": "..."},
            {"tool": "file_write", "path": "drafts/case_summary.md"},
        ]
    }
}
```

## ContextCompiler：系统提示编译

`agent_os/memory/context_compiler.py`

### 编译流程

```python
def compile(session, message):
    sections = []
    
    # 1. 加载 agent_system.txt（内核层）
    sections.append(read_prompt("agent_system.txt"))
    
    # 2. 加载 SOUL.md / AGENT.md / MEMORY.md（会话层）
    for f in ["SOUL.md", "AGENT.md", "MEMORY.md"]:
        sections.append(read_workspace_file(session, f))
    
    # 3. 加载 skill profiles（领域层）
    for skill in session.active_skills:
        sections.append(skill["profile"])
    
    # 4. 加载 skills index
    sections.append(build_skills_index())
    
    # 5. 加载 memory guidance
    sections.append(read_prompt("memory_guidance.txt"))
    
    # 6. 打包为 XML
    return format_xml(sections, tag="system_prompt")
```

### memory_guidance.txt

`agent_os/prompts/memory_guidance.txt` — 关于 session 记忆的指导：

- 使用 MEMORY.md 积累跨回合的关键事实
- 定期更新 MEMORY.md（通过 file_write）
- 使用 workspace_search 检索历史工件
- 注意 artifact lineage 追踪

### Skills Index 构建

```python
def build_skills_index():
    xml = "<skills_index>\n"
    for skill in skills.values():
        xml += f'  <skill name="{skill["name"]}" desc="{skill["description"]}"/>\n'
    xml += "</skills_index>"
    return xml
```

只包含 name 和 description — 完整内容通过 `skill_use` 工具按需加载。

## 使用模式

### 何时使用哪种检索

| 场景 | 推荐方式 | 工具 |
|------|---------|------|
| 查找关键词匹配 | FTS5 | workspace_search |
| 语义相似内容 | Embedding | workspace_search |
| 外部知识 | 网络搜索 | web_search |
| 法律法规 | 专用 API | law_retrieve |
| 法律案例 | 专用 API | case_retrieve |
| 学术论文 | 专用 API | arxiv_search / openalex_works |

### Agent 记住关键信息的方式

不是依赖检索，而是通过 `file_write` 持久化：

```python
# Agent 发现关键信息后，写入 research/ 下文件：
research_state(content="发现：A 公司实际控制人是 B")
file_write(path="research/key_findings.md", content="...")
```

下次迭代通过 `workspace_search` 或 `file_read` 获取。
