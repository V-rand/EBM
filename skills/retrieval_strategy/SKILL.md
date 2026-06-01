---
name: retrieval-strategy
description: Use when the task requires multi-step retrieval (finding specific papers, entities, or facts across multiple sources). Teaches staged search recipes, domain-locking, reference fingerprinting, and progressive drill-down — avoiding broad keyword soup.
---

# 检索策略

检索不是"输入关键词 → 获得结果"。它是一个分阶段的、逐步收窄的过程——就像人类研究员一样，从广泛开始，锁定权威来源，然后在其内部深入挖掘。

## 核心规则

**当你可以锁定到权威域名时，永远不要搜索整个网络。当你有结构化字段时，永远不要使用关键词。当你可以从约束推理得出结论时，永远不要再次搜索。**

## 先选节点，后选工具

不要问"下一个关键词是什么？"而要问"问题图中哪个节点最窄且可搜索？"

| 节点 | 宽度 | 工具形态 |
|---|---|---|
| 写了后来评论的评论家 | 宽 | 避免作为第一条路径 |
| 某一年数字专题奖项的获奖者 | 中 | 域名锁定的 web 搜索 |
| 专家出版物集群 | 窄节点 | `openalex_works` / `crossref_search` |
| 某一年学会工作坊演讲者 | 窄节点 | 域名锁定的 web 搜索 / 官方 PDF |

仅在宽节点是唯一可用入口时使用。如果存在窄节点，先选它，再选工具。

## 可复制的检索轨迹

从复制以下某一形态开始，然后替换具体事实。

**从独特线索中查找未知论文**
```
openalex_works(query="\"42,137 households\" \"ordinal probit\"", year="2010-2019")
web_search(query="\"42,137 households\" \"survey wave\"  site:candidate-journal.org")
web_read(url="candidate PDF or article page")
openalex_works(query="candidate title", year="2015")
```

**已知作者/来源，未知论文**
```
openalex_entity(entity_type="author", search="Author Name")
openalex_works(author="Author Name", year="2015", query="distinctive topic phrase")
web_read(url="best candidate page")
```

**通用网络来源发现**
```
web_search(query="\"rare phrase\" uncommon_number domain_noun")
web_search(query="\"rare phrase\" filetype:pdf site:best-returned-domain.org")
web_read(url="best returned page")
```

**生物医学文献**
```
pubmed_search(query="condition intervention outcome", year="2015")
openalex_works(indexed_in="pubmed", query="candidate title")
crossref_search(query="candidate title")
```

## 第一阶段：选择正确的工具

| 需要什么 | 工具 | 原因 |
|---|---|---|
| 按作者/会议/年份查找论文 | `arxiv_search` | 结构化字段（author/venue/year/title/category）。arXiv 有 comment/journal_ref 包含会议信息。 |
| 跨所有来源按作者/机构/主题查找论文 | `openalex_works` | 2.7 亿+篇论文。自动名称→ID 解析。参考文献指纹搜索。 |
| 按精确参考文献指纹查找论文 | `openalex_works(references="paper1,paper2")` | 查找引用了特定论文的论文。通过引用列表唯一标识一篇论文。 |
| 实体查找（作者/机构 ID） | `openalex_entity` | 获取 OpenAlex ID 用于过滤。 |
| 实体事实（出生、演员阵容、年份） | `wikipedia_lookup` | 结构化信息框数据。精确标题匹配。 |
| 论文 DOI/出版商 | `crossref_search` | CrossRef 元数据。 |
| 通用网络（新闻、博客、发现） | `web_search` | 最后手段。配合 site: 和 "精确短语" 操作符使用。 |
| 已保存的资料 | `workspace_search` | 始终**首先**检查。 |

## 第二阶段：域名锁定发现

使用 `web_search` 时，永远不要搜索整个网络来查找学术内容。锁定到权威域名：

```
# 而不是："conference-2022 paper countryX countryY"
# 使用：site:authoritative-proceedings-domain "countryX" "universityY"

# 而不是："what is the capital of France"
# 使用：site:en.wikipedia.org "capital" "France"
```

对于 `arxiv_search`，结构化字段就是你的域名锁定：
```
arxiv_search(author="known_author", venue="venue_name", year="2022")
```

对于 `openalex_works`，组合过滤器来收窄：
```
openalex_works(institution="Stanford", topic="Graph Neural Networks", year="2022-2024", source_type="conference")
```

如果你还不知道权威域名，运行一个紧凑的发现查询，然后深入最佳结果域名：

```
# 发现：2-5 个高信息熵术语，而非每个线索
web_search(query="\"42,137 households\" \"ordinal probit\"")

# 深入：以发现的来源为边界
web_search(query="\"42,137 households\" \"survey wave\"  site:candidate-journal.org")
web_search(query="\"synthetic title phrase\" filetype:pdf site:candidate-journal.org")
```

不要通过添加更多宽泛关键词来回应有希望的结果。下一步通常是 `web_read`、`site:domain/path`、`intitle:`、`inurl:` 或 `filetype:pdf`。

## 第二阶段半：指纹查询构建

好的检索从将约束分为信号层级开始。在写查询前完成这一步。

如果你已经搜索了几次或感觉查询框架在重复，用 research_state 写下当前进展和下一方向：

```
research_state(content="
## 当前阶段
- question_type: literature_lookup
- active_goal: 找到论文 Y 的完整作者列表
- 已试路径：[查询 A 没返回, 查询 B 结果噪音太大]
- 已知：论文 Y 发表于 2022, 方法 X
- 未知：第三作者是谁

## 下一步
尝试在 openalex_works 用 citation fingerprint 定位
")
```

行动标记（在草稿中标注当前动作）：
- `lookup`：对已知实体、标识符、指南、论文、法律或官方来源进行权威事实查找。
- `match`：寻找类似案例、论文、实体、类患者记录、既往轨迹或引用邻居证据。
- `search`：候选身份未知时的开放式发现；使用高信息熵指纹。
- `verify`：在发现后确认/否定候选、输出字段或硬约束。
- `reason`：在决定是否需要更多检索之前处理当前证据。
- `answer`：停止检索并产生最终回复。

**Tier A — 高信息熵指纹。优先使用这些。**
- 精确数字和不常见数量：`"42,137 households"`、`"12.4% validation sample"`、`63(3)`
- 来自提示或来源风格的精确短语：`"survey wave"`、`"reference quarter"`
- 组合中不常见的方法或模型名称：`"ordinal probit"`、`"Bayesian hazard model"`
- 命名实体、标识符、DOI、PMID、法律、条款号、作者姓名
- 稀有共现：一个精确数字 + 一个方法 + 一个领域名词

**Tier B — 有用的过滤器。在候选池出现后添加。**
- 年份范围、国家/地区、领域、出版商、会议系列、来源类型、语言
- 锚定领域但不唯一的通用名词：`census`、`employed`、`sample`、`paper`

**Tier C — 弱/噪声术语。避免以这些开头。**
- 模糊的意图词：`study`、`analysis`、`impact`、`relationship`、`factors`、`determinants`
- 宽泛标签：`research`、`article`、`data`、`model`、`population`
- 许多页面都能满足的问题转述

### 查询配方

从 Tier A 向外构建查询：

1. 以 2-4 个高信息熵标记开头，最好是精确短语。
2. 如有需要，添加一个领域锚点。
3. 如果你知道来源类别，添加域名锁定或结构化工具。
4. 不要包含每个线索。过度加载的查询常常隐藏答案。
5. 如果结果为空，放宽一个精确短语或切换措辞类别；不要仅仅重新排列词语。

示例：

```
# 好的发现指纹
"42,137 households" "survey wave"

# 如果方法是区分线索则更好
"42,137 households" "ordinal probit"

# 太宽泛
survey sample model paper journal country population

# 过度加载
"12.4% validation sample" "42,137 households" "same author" keyword publication
```

### 什么算进展

检索结果只有在提供以下至少一项时才有用：
- 一个候选标题/实体；
- 一个作者、DOI、出版物、来源 URL 或精确标识符；
- 一个验证约束的引用；
- 一个拒绝候选的理由；
- 一个权威来源使用的新同义词类别。

如果结果只重复宽泛主题词，不算进展。

## 第三阶段：逐步深入（类人检索）

不要停在第一次搜索。利用结果来指导下一步：

1. **从广泛开始**：找到候选池。锁定域名 + 1-2 个约束。
2. **阅读结果**：不是所有结果。选择 2-3 个最有希望的。`web_read` 实际页面内容。
3. **识别关键实体**：从阅读内容中提取具体作者姓名、机构名称、DOI、参考文献标题。
4. **用结构化工具验证**：将这些实体带到 arxiv_search 或 openalex_works 进行精确验证。
5. **交叉验证**：用第二个权威来源确认。

查找特定会议论文的通用链：
```
Step 1: arxiv_search(author="known_author", venue="venue_name", year="2022") → 返回候选
Step 2: web_read 最有希望的结果 → 提取完整作者列表、参考文献信息
Step 3: openalex_works(references="ref_paper1,ref_paper2", year="2022") → 通过参考文献指纹验证
Step 4: openalex_works(doi="extracted DOI") → 最终确认
```

## 第四阶段：参考文献指纹（最强大）

一篇论文的参考文献列表就是它的 DNA。如果你知道具体的参考文献：
```
openalex_works(
    references="known reference title 1, known reference title 2",
    year="target year"
)
```
这会找到同时引用了这两篇论文的所有论文——通常只有少数几篇。结合作者/会议/年份过滤器，可以在不需要标题的情况下唯一识别目标论文。

## Google 操作符（用于 web_search）

Tavily 和 Serper 均支持：
- `site:domain/path` — 域名锁定
- `"exact phrase"` — 精确匹配
- `-word` — 排除
- `OR` — 替代项（大写）
- `intitle:keyword` — 页面标题必须包含关键词
- `inurl:keyword` — URL 必须包含关键词
- `filetype:pdf` — 仅查找 PDF
- `AROUND(N)` — 邻近：`word1 AROUND(3) word2`（附近的词语）

## OpenAlex 布尔和邻近搜索

使用 `openalex_works(title=...)` 时，title 参数支持：
- `AND, OR, NOT`（大写）— 布尔逻辑：`(graph AND contrastive) NOT supervised`
- `"exact phrase"` — 短语匹配：`"graph contrastive learning"`
- `"phrase"~N` — N 词内邻近：`"graph learning"~5`
- `word*` — 通配符：`contrast*` 匹配 contrastive, contrasting
- `wom?n` — 单字符通配符
- `word~N` — 模糊（编辑距离）：`transformar~1` 匹配 transformer

## Tavily 高级特性

`web_search` 支持以下 Tavily 专用参数：
- `exact_match=true` — 要求精确短语匹配（用于名称、实体；返回较少结果）
- `time_range` — "day"、"week"、"month"、"year" 用于时效性过滤
- `source="scholar"` — 通过 Serper 访问 Google Scholar（学术论文）
- `source="news"` — 仅新闻搜索
- `search_depth` — "advanced" 为最高质量（已为默认值）

## 当遇到困难时

如果 3 次以上搜索没有产生进展：
1. **检查前提** — 是否有根本假设错误？
2. **更换工具** — 如果 web_search 不奏效，尝试 arxiv_search 或 openalex_works
3. **尝试参考文献指纹** — 如果你知道具体参考文献，使用 openalex_works(references=...)
4. **尝试域名锁定** — 如果广泛搜索，用 site: 锁定到权威域名
5. **停止搜索** — 如果 2 次转向失败，以不确定性回答，而非无限搜索

## 反模式（绝对不要这样做）

- ❌ `web_search("conference2022 countryX countryY N authors M references")` — 关键词汤
- ❌ `web_search("what paper has 6 authors from China and Singapore")` — 自然语言问题作为查询
- ❌ 用稍微不同的关键词重复同一 web_search 10 次以上
- ❌ 在 arxiv_search 或 openalex_works 明显更合适时使用 web_search
- ❌ 阅读全部 10 条搜索结果而不是选取 2-3 条最相关的
- ❌ 不先推理约束意味着什么就进行搜索
