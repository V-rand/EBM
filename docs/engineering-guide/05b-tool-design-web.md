# 工具设计分析：网页搜索与读取

> 网页工具是深度研究 agent 的核心能力。设计好坏直接决定了研究质量。本分析基于 `web.py` 和 `search.py` 的源码。

## web_search：网络搜索

`agent_os/tools/search.py:28`

### 架构

```
Agent → web_search(query, source="web")
               │
               ├── Tavily 搜索（主 backend）
               │     └── API Key: TAVILY_API_KEY
               │
               ├── Serper 搜索（fallback）
               │     └── API Key: SERPER_API_KEY
               │
               └── 结果统一格式化
                     ├── title / url / content (snippet)
                     └── 最近 N 条结果
```

### 设计决策

**1. 双 backend 回退**

```
Tavily → 原生搜索 + AI 提取，但可能不达
Serper → Google 搜索结果，覆盖面广
```

如果 Tavily 失败（无 key 或 API 错误），自动回退到 Serper。这种"主 + 备"模式保证了可用性。

**2. query 处理策略**

- 保留 `site:`、`"exact phrase"` 等搜索语法 — 模型可以精确控制搜索范围
- `source=scholar` 切换到学术搜索
- `source=news` 切换到新闻搜索

**3. 结果数量控制**

默认返回 top-8 结果，每个包含 snippet。不返回全文 — 全文需要 agent 再通过 `web_read` 获取。

**4. 结果过滤（agent_system.txt 层面控制）**

搜索前应该先确定搜索策略（关键词、site 限制、语言），而不是泛泛搜索。Agent 的提示词中：

> "选对过滤锚点比多搜几次更重要。"

## web_read：网页读取

`agent_os/tools/web.py:44`

### 架构

```
Agent → web_read(url)
               │
               ├── Jina Reader（主，需 JINA_API_KEY）
               │     └── url → LLM-ready markdown
               │
               ├── Firecrawl（回退 1）
               │     └── scrape with JS rendering
               │
               ├── Trafilatura（回退 2）
               │     └── 本地纯文本提取，无 JS
               │
               └── MinerU（PDF/Office 文档 fallback）
                     └── document → markdown
```

### 四层回退设计

| 层级 | Provider | 能力 | 速度 | 需 Key |
|------|----------|------|------|--------|
| 1 | Jina Reader | 最佳 LLM markdown，自动清洗 | 快 | ✓ |
| 2 | Firecrawl | JS 渲染 SPA，完整页面 | 中 | ✓ |
| 3 | Trafilatura | 本地纯文本，无需网络请求 | 极快 | ✗ |
| 4 | MinerU | PDF/DOCX/图片 → Markdown | 慢 | ✓ |

**设计原则**：尽量返回 LLM-ready 的 markdown（Jina），实在不行才降级。不要强行依赖单一服务。

### 关键设计细节

**1. 内容清洗**

```python
# web.py 中对内容的处理：
# - 去除 HTML 标签
# - 合并连续空白
# - 保留超链接引用（便于溯源）
# - 截断到 max_result_chars
```

**2. 文档类型检测**

根据 URL 后缀判断是否为 PDF/Office 文档，自动路由到 MinerU：

```python
_DOC_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls"}
if Path(parsed.path).suffix.lower() in _DOC_EXTENSIONS:
    return await _read_document(url, ...)
```

**3. 超时控制**

config.yaml 中可配置 `tool_timeout_web_read: 20` 秒。

## 与学术搜索工具的关系

AgentOS 将网页搜索与学术搜索分离为不同工具：

| 工具 | 覆盖范围 | 数据源 |
|------|---------|--------|
| web_search | 通用网络 | Tavily/Serper |
| web_read | 特定 URL | Jina/Firecrawl/Trafilatura |
| arxiv_search | 学术预印本 | arXiv API |
| crossref_search | 出版物元数据 | CrossRef API |
| openalex_works | 综合性学术 | OpenAlex |
| pubmed_search | 生物医学 | PubMed |
| opencitations_search | 引用关系 | COCI |

**设计原因**：专用工具比通用搜索+读取在学术场景下效率高得多。arXiv/PubMed/OpenAlex 有结构化元数据（作者、年份、引用数），不需要 agent 自己去 parsing。

## 最佳实践（从源码中总结）

### 工具 Prompt 设计

web_search 和 web_read 的 description 文本是关键：

```python
# web_search 的 description 应包含：
- 支持的搜索语法 (site:, "exact", source=)
- 结果数量限制
- 什么情况下使用（vs law_retrieve vs workspace_search）

# web_read 的 description 应包含：
- 支持的 URL 类型（HTML, PDF, DOCX）
- 内容格式（Markdown）
- 什么情况下阅读 vs 什么情况下先搜索
```

### 常见陷阱

1. **搜索结果读完不归档** — Agent 经常读完网页就把内容丢了。结果应该通过 `research_state` 或 `artifact_upsert` 持久化。

2. **搜索之前没有策略** — 见提示词原则："选对过滤锚点比多搜几次更重要。"

3. **过度依赖单一 backend** — 双 backend 策略就是为了避免这个问题。

4. **搜索+阅读在同一轮** — 当前架构中搜索和阅读分两步进行，agent 需要先搜索再决定读哪些。这避免了盲目读取。
