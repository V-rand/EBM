# 工具设计分析：学术检索

> 学术检索是深度研究 agent 区别于通用聊天助手的核心能力。AgentOS 集成了 6 个学术检索工具，各自针对不同场景。

## 工具矩阵

| 工具 | 覆盖 | 元数据深度 | 时效性 | 引用网络 | 限流 |
|------|------|-----------|--------|---------|------|
| `arxiv_search` | 预印本（200万+） | 作者、类别、年份 | 即时 | 无 | 无（公开 API） |
| `crossref_search` | 出版物元数据 | DOI、期刊、作者 | 1-3 天 | 引用数 | 50/s |
| `openalex_works` | 学术论文全集 | 27+ 过滤器、概念、机构 | 周级 | 引用数 + 参考 | 100k/天（免费） |
| `openalex_entity` | 作者/机构/来源 | 层级结构、关联作品 | 周级 | 合作网络 | 同上 |
| `opencitations_search` | 引用关系 | DOI-DOI 引用边 | 月级 | ⭐ 全图 | 无 |
| `pubmed_search` | 生物医学 | MeSH 主题词、摘要 | 天级 | PubMed Central | 10/s |

## arxiv_search

`agent_os/tools/academic.py:99`

### 特性

- 支持：作者名、标题、分类、年份范围
- 有 Semantic Scholar fallback（当 arXiv API 返回空时）
- 返回：标题、作者列表、摘要、PDF URL、分类标签

### 设计要点

```python
# 参数设计考虑
# - author: "Firstname Lastname" 格式（arXiv API 要求）
# - max_results: 默认 10
# - sort_by: "relevance" | "submittedDate"
# - category: "cs.AI" | "math.ST" | ...
```

**Semantic Scholar fallback 的意义**：arXiv API 在非英语查询时召回率低，Semantic Scholar 的语义搜索可以弥补。但 S2 的延迟比 arXiv 高。

## openalex_works + openalex_entity

`agent_os/tools/openalex.py:239`

OpenAlex 是当前最全面的开放学术图谱，两者配合使用：

### openalex_works

```python
# 27+ 过滤参数
params = {
    "search": "论文主题",     # 全文搜索
    "author.id": "...",      # 限定作者
    "institutions.id": "...", # 限定机构
    "concepts.id": "...",    # 限定概念
    "from_publication_date": "2020-01-01",
    "cited_by_count": ">10",  # 引用过滤
    "per_page": 25,
}
```

支持自动 name-to-ID 解析：

```python
# 传入作者名称，自动 resolve 到 OpenAlex ID
"author.name": "Yoshua Bengio"
# 内部调用 /authors 端点查找 ID
```

**引用指纹**：结果中包含 `referenced_works` 列表，可用于雪球检索。

### openalex_entity

```python
# 实体查询（作者/机构/来源/概念）
result = await openalex_entity(type="authors", search="Geoffrey Hinton")
# 返回作者信息 + 作品列表 + 合作网络
```

### 设计模式

**两阶段检索**：

```
第一阶段：openalex_works(search="主题")
  → 发现关键论文、作者
第二阶段：openalex_entity(type="authors", ...)
  → 获取作者深度信息 + 全部作品
```

## opencitations_search

`agent_os/tools/opencitations.py:78`

### 独特价值

- 专注于 COCI（Citation Object Citation Index）
- 提供引用图：谁引用了谁，被谁引用，引用计数
- 适合：引文分析、研究前沿跟踪、文献综述

### 提供的查询

```python
# 引用方（谁引用了这篇论文）
/citations/doi:{doi}

# 被引用（这篇论文引用了谁）
/references/doi:{doi}

# 引用计数
/citation-count/doi:{doi}
```

## 学术检索的协作模式

### 典型工作流

```
1. 确定研究主题
       │
2. arxiv_search() — 最新预印本（时效性优先）
       │
3. openalex_works() — 综合性搜索（覆盖优先）
       │
4. crossref_search() — 补充元数据（DOI/期刊）
       │
5. opencitations_search() — 引用追踪（影响力判断）
       │
6. 重复 3-5 直到饱和
```

### 为什么不合并成一个工具

1. **API 差异太大** — 每个都有独特的参数和返回结构
2. **覆盖范围不同** — arXiv 没有 published 论文，OpenAlex 没有最新预印本
3. **限流策略不同** — 合并会导致一个限流阻塞所有
4. **Agent 需要感知哪个数据源** — 让它根据需求选择

### 结果格式统一

所有学术工具返回统一格式的列表：

```python
[
    {
        "title": "...",
        "authors": ["..."],
        "year": 2024,
        "abstract": "...",
        "url": "...",
        "source": "arxiv",  # 标明来源
        "citation_count": 10,
    }
]
```

## 限流与退避策略

| 工具 | 限流 | 应对 |
|------|------|------|
| arxiv_search | 无 | 无 |
| crossref_search | 50 请求/秒 | 退避重试 |
| openalex | 100k 请求/天 | 退避+h 请求头 |
| opencitations | 无（但大量可能被 ban） | 无 |
| pubmed | 10 请求/秒 | 退避重试 |
