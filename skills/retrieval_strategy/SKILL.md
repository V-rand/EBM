---
name: retrieval-strategy
description: "**PICO 构建后、开始检索前必加载。** 按证据层级选工具：guideline→pubmed article_type=guideline, SR→cochrane+pubmed, RCT→clinical_query=therapy。自上而下逐层检索。"
---

# 检索策略

检索不是"输入关键词 → 获得结果"。它是一个分阶段的、逐步收窄的过程——就像人类研究员一样，从广泛开始，锁定权威来源，然后在其内部深入挖掘。

## 核心规则

**当你可以锁定到权威域名时，永远不要搜索整个网络。当你有结构化字段时，永远不要使用关键词。当你可以从约束推理得出结论时，永远不要再次搜索。**

## EBM 工具选择：按证据层级

不要问"用什么关键词搜"——先问"这个问题在证据金字塔的哪一层？"

| 要找到什么 | 工具 | 怎么用 |
|-----------|------|--------|
| 临床指南 | `pubmed_search` | `article_type="guideline"` |
| Cochrane 系统评价 | `cochrane_search` | 直接搜，PubMed 自动回退 |
| 系统评价/Meta分析 | `pubmed_search` | `article_type="systematic_review"` |
| 随机对照试验 | `pubmed_search` | `article_type="rct"`, 加 `clinical_query="therapy"` |
| 正在进行的试验 | `clinical_trials` | `condition` + `intervention`, `status="recruiting"` |
| 最新预印本 | `medrxiv_search` | 查 PubMed 还没收录的新研究 |
| 特定 PMID | `pubmed_search` | `pmid="34101387"` 返回完整元数据 |
| 扩展文献/引用链 | `openalex_works` | `indexed_in="pubmed"` |
| 灰色文献/补充 | `web_search` | 配合 `site:域名` 锁定权威源 |

**自上而下检索**：先搜 guideline → 搜到就用其引用的系统评价 → 再查底层 RCT。不要跳过中间层。

## 可复制的检索轨迹

**自上而下检索某疗法的证据（EBM 标准路径）**
```
pubmed_search(query="SGLT-2 inhibitor cardiovascular", article_type="guideline")
    → 找到指南后，查看其引用的系统评价
pubmed_search(query="SGLT-2 inhibitor MACE", article_type="systematic_review")
    → 找到系统评价后，查看其纳入的 RCT
pubmed_search(query="empagliflozin cardiovascular", article_type="rct", year="2015-2024")
    → 验证关键 RCT 的方法学和效应量
clinical_trials(condition="type 2 diabetes", intervention="empagliflozin", status="completed")
    → 查看已完成但未发表的试验
```

**探索最新证据**
```
medrxiv_search(query="long COVID treatment", category="infectious")
    → 预印本最快，但未经同行评议
pubmed_search(pmid="34101387")
    → 已知 PMID，快速获取完整元数据 + grade_readiness
```

**引文链追踪**
```
openalex_works(query="key paper title", indexed_in="pubmed")
    → 找到目标论文的 OpenAlex ID
opencitations_search(doi="10.1000/xxx", mode="citations")
    → 谁引用了这篇（前向追踪）
opencitations_search(doi="10.1000/xxx", mode="references")
    → 这篇引用了什么（后向追踪）
```

## 域名锁定

已知权威来源时，用 site: 锁定域名而非搜全网。web_search 配合 `site:domain`、`intitle:`、`filetype:pdf` 操作符。发现查询要精简（2-5 个高信息熵词），不要堆砌关键词。有希望的来源出现后，下一步是 `web_read` 读全文，而不是继续换关键词搜。

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

## 当遇到困难时

如果 3 次以上搜索没有产生进展：
1. **检查前提** — 是否有根本假设错误？
2. **更换工具** — 如果 web_search 不奏效，尝试 arxiv_search 或 openalex_works
3. **尝试参考文献指纹** — 如果你知道具体参考文献，使用 openalex_works(references=...)
4. **尝试域名锁定** — 如果广泛搜索，用 site: 锁定到权威域名
5. **停止搜索** — 如果 2 次转向失败，以不确定性回答，而非无限搜索

