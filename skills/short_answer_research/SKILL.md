---
name: short-answer-research
description: Use when the answer_contract mode is short_answer — the user needs one fact, entity, number, year, location, or a BrowseComp-style multi-clue puzzle answer. Load this skill BEFORE any search or tool call for short-answer tasks.
---

# 短答案研究规范

目标是一个唯一的、可验证的短答案。方法论是以约束驱动的推理为核心，检索作为发现和验证手段，而非关键词驱动的浏览。保持协议精简：解析问题，发现/构建候选，测试硬约束，更新状态，然后回答或转向。

## 最小协议（先推理后搜索）

以下为执行主干：

1. **Parse（解析）** — 提取 answer_type、hard_constraints、soft_clues、ambiguities、premises 和 output_fields。
2. **Discover / Build Candidates（发现/构建候选）** — 在可能的情况下构建 2-5 个候选。如果答案无法推断（论文/文档/法律/案例查找），使用定向检索来发现候选。
3. **Test（测试）** — 选择最有可能区分候选的硬约束。优先选择能够排除某个候选的检查。
4. **Update（更新）** — 将证据绑定到某个声明或约束。一个失败的硬约束会拒绝候选，除非约束解释发生了变化。
5. **Pivot / Answer（转向/回答）** — 如果没有进展，修复前提/框架/工具选择。如果有一个候选满足所有硬约束且竞争对手已被排除，简洁回答。

在检索之前，你需要一个策略，而不一定是一个候选。查询必须由约束分析或高信息熵指纹计划生成，而不是将用户问题直接粘贴到搜索中。

当你发现自己搜索了 3 次以上仍无进展时，问题几乎肯定出在你的推理框架中，而非关键词。停止搜索，检查你的前提。

## 策略主干

对于链式谜题，不要从搜索第一个被提及的实体开始。首先外化问题图：

1. 构建问题图：节点、边、锚点。
2. 选择路径：正向路径、反向路径、锚点优先路径。
3. 选择最窄的可搜索节点。
4. 从所选路径中执行一个动作。
5. 只将已验证的证据提升为事实；假设不是事实。

糟糕的路径：
`critic -> prize -> later review -> cited scientist`，因为评论/评论空间巨大。

更好的路径：
`society workshop presenter -> specialist publication cluster -> cited review -> critic`，因为学会记录和出版物元数据更窄且结构化。

## 可复制的行动轨迹

将这些轨迹作为行为模板使用。调整术语，保持结构。

**带有宽泛第一实体的多跳链式谜题**
```
research_state(content="
## 问题图
- 节点：critic、prize、review、specialist、study、presenter
- 边：critic->prize、review references specialist、study -> workshop presenter
- 锚点：society records、OpenAlex papers、prize lists

## 路径选择
- 候选路径：[前向 critic->prize->review, 后向 presenter->study->review, 锚点优先 society+publication]
- 选定路径：后向 presenter->study->review
- 最窄节点：society presenter / specialist publication cluster
- 第一步：society 会议搜索 或 openalex_works 定位 specialist 论文

## 声明盘点
- 已验证：无
- 假设：critic/review 关联在检索前只是猜测
- 未知：哪个合作者参与了 workshop
")
```

**来自方法论线索的特定论文**
```
research_state(content="
## 问题模型
- 答案类型：论文标题
- 硬约束：[方法 X, 数据 Y, 期刊 Z]
- 软线索：[括号内短语]
- 前提：[数据 Y 的样本量 > 1000]（已验证）
")
openalex_works(query="\"42,137 households\" \"ordinal probit\"", year="2010-2019")
web_search(query="\"42,137 households\" \"survey wave\" site:promising-journal-domain.org")
web_read(url="candidate paper or PDF URL")
research_state(content="# 进展：找到候选论文，发表信息已核实")
answer
```

**带有联想性约束的谜题/实体线索**
```
research_state(content="
## 约束分析
- 约束词：X 让人联想到 Y
- 推理视角：[字面含义, 中文翻译, 词源, 国籍/地理, 职业/领域, 文化原型, 领域隐喻]
- 推理链 1：X 在中文中译为「Z」→ 联想的可能是某著名 Z 人
- 推理链 2：X 在某文化中原型为 A → 联想的可能是 A 的故事
")
web_search(query="\"candidate name\" \"exact association phrase\"")
# 如果没有直接高质量匹配：
skill_use("constraint_reasoning")
research_state(content="# 进展：约束已通过已知事实链解决/排除")
```

**找到有希望来源的宽泛网络发现**
```
web_search(query="\"rare phrase\" uncommon_number domain_noun")
web_search(query="\"rare phrase\" discriminating_term site:best-returned-domain.org")
web_read(url="best returned page")
```

### 发现优先例外：文献/文档查找

某些短答案任务要求你从一个约束指纹中找到一篇特定的论文、文章、出版物、期刊、会议、报告、数据集、法律、案例或文档。在这些任务中，搜索不仅仅是最终验证——搜索就是候选发现机制。

对于文献/文档查找：
- 不要强制纯已知事实推理来产生一个无法推断的候选。
- 先推理到足以构建一个高信号检索计划即可：精确短语、数字指纹、方法术语、总体/样本线索、作者/年份提示、来源类别和可能的数据库。
- 优先使用高信息熵指纹而非模糊关键词。好的第一查询单元包括精确数字、不寻常短语、方法名称、标识符和稀有共现。避免使用弱词如"study"、"analysis"、"paper"、"factors"、"relationship"，除非与强指纹搭配。
- 然后尽早运行定向发现检索。例如：精确短语搜索、带引号/域名锁定的 `web_search`、`openalex_works`、`crossref_search`、`arxiv_search`、出版商/会议记录网站，或域名站点查找。
- 在检索后使用推理来排序、排除和验证候选，逐一对照每个硬约束。

好的结构：精确数字/方法指纹 → 结构化学术工具或紧凑的 web 发现 → 域名深入/阅读 → 验证候选出版物。

糟糕的结构：对隐藏国家/期刊进行多轮推断，或在出现有用来源后轮换宽泛关键词组合。

## 详细关卡

**3. TEST（测试）** — 选择最有可能区分候选的硬约束。对于联想性、语言性、地理性或推理密集的线索，先用 research_state 把约束分析和推理视角写到草稿上，再进行广泛搜索。如果对联想性约束的一轮搜索没有产生直接高质量匹配，在继续检索之前切换到已知事实推理（`constraint_reasoning` 技能）。只有在能够陈述具体的预期收益——将区分哪个候选以及如何区分时——才继续检索。

**4. UPDATE（更新）** — 在每一批工具调用后更新账本。一个失败的硬约束拒绝候选——不要挽救它，除非约束解释发生了变化。幸存的候选必须使每个硬约束要么匹配要么标记为缺失。证据必须绑定到特定的硬约束。不要接受整体上"看起来合理"作为证据。

**5. PIVOT_OR_STOP（转向或停止）** — 显式统计进展和转向次数。进展意味着：新候选、拒绝候选、已验证的硬约束或修正了歧义。无进展意味着：搜索返回了结果但候选区分没有改善（没有新候选、没有拒绝、没有验证约束、没有修正歧义）。三轮无进展 = 一次失败的转向。

在转向之前，进行前提重新检查：列出你一直依赖的 3 个假设。其中任何一个可能错误吗？选择最可疑的一个并验证它。错误的前提是延长搜索失败的最常见原因——不检查前提就更换关键词是浪费精力。

一次失败转后：更换查询类别或框架（按排除的替代选项搜索、法律类别、日期/数字模式、来源数据库、引用链或同义词家族）。不要在同一框架内轮换关键词。
两次失败转向后且没有候选满足所有硬约束：停止搜索。以最佳候选加明确不确定性回答，或说明证据不足。两次失败转向后的"再搜一次"是无限搜索，不是勤勉。

**6. VERIFY_OR_ANSWER（验证或回答）** — 一旦某个候选看起来满足答案字段和主要硬约束，切换到验证模式。在草稿上写下："正在验证候选 X 的字段 Y"。最多运行一个最高权威验证来源，除非该来源与候选矛盾或留下未解决的硬约束。在存在优胜候选后，不要继续发现搜索。

**7. ANSWER（回答）** — 当有一个候选满足所有硬约束且最强竞争对手被明确排除时，立即回答。只输出最终答案和紧凑的论证。除非被要求，否则不暴露完整账本。只有当优胜者满足所有硬约束时，才输出确定答案——否则输出最可能答案并注明不确定性。

## 思考外化：research_state 草稿纸

`research_state` 是一张自由格式的草稿纸。调 `research_state(content="...")` 时，**完整草稿内容写入返回值**，模型立刻看到。不传 content 就只读当前草稿。

**典型写法：**
```
research_state(content="
## 当前约束
「born in the year of the Green Serpent」→ 乙巳年 → 1965, 1977, 1989, 2001...

## 候选
- 候选 A: 张三 (1965 年生) — 待核实：小说是否被改编音乐剧
- 候选 B: 李四 (1977 年生) — 已排除：无小说出版记录

## 已知事实
- 乙巳年对应蛇
- 60 年一轮回，20 世纪出现于 1905, 1965...

## 下一步
验证候选 A → web_search
")
```

**调用时机**：需要外化思考时随时调用。长时间未调用系统会温和提示。

## 检索配方

在搜索候选时，使用分阶段的、域名锁定的查询。以结构思考：

1. **已知权威领域** → 在其内部搜索：
   `web_search(query="\"known country\" \"known institution\"  site:authoritative-proceedings-domain.org")`
2. **未知领域** → 一个紧凑的发现查询，然后领域深入：
   `web_search(query="\"rare phrase\" method_name")` → `web_search(query="\"rare phrase\" discriminating_term site:best-domain.org")`
3. **候选存在** → 通过指纹验证：
   `web_search(query="\"candidate title\" \"known reference title\"  site:publisher-or-proceedings.org")`
4. **最终确认** → 使用另一结构化/权威来源：
   `arxiv_search(title="candidate title")`、`openalex_works(doi="...")`、`crossref_search(query="candidate title")` 或 `web_read`。

**Google 操作符（Tavily 和 Serper 均支持）：**
- `site:domain/path` — 域名锁定
- `"exact phrase"` — 精确匹配
- `-word` — 排除
- `OR` — 替代项（大写）
- `intitle:keyword` — 标题聚焦搜索
- `inurl:keyword` — URL/路径聚焦搜索
- `filetype:pdf` — 仅搜索 PDF

**常见任务的站点锁定目标：**
| 任务 | 锁定到 |
|---|---|
| 会议论文 | 官方会议记录网站、OpenReview、arXiv、出版商页面 |
| Wikipedia 事实 | `site:en.wikipedia.org` |
| 政府/官方数据 | `site:gov.cn` 或相关机构的域名 |
| 公司/产品信息 | `site:company.com` |

阐明每个查询所服务的方式：
- discovery 查询：发现候选
- expansion 查询：沿别名/人员/地点扩展候选信息
- discriminating 查询：搜索最容易排除候选的约束
- answer 查询：验证最终输出字段

避免从 discovery 查询直接跳到 answer 查询。除非任务是简单查找或来源明显权威，否则不要在第一轮搜索后锁定到单个候选。

## 补充规则

- 搜索片段是发现提示，不是最终证明。对于硬约束，在可用时使用 web_read 或权威来源。
- 当约束涉及抽象联想（名字让人联想到、与……相关、让人想起），将精确匹配检索仅视为发现。如果一轮搜索没有产生直接高质量匹配，在继续检索之前切换到已知事实推理（使用 `constraint_reasoning` 技能）。
- 联想性线索偏好是软的，不是绝对的：如果推理仍然薄弱，可以运行另一轮定向查询，但记录为什么这个查询能够区分候选。
- 优先选择解释简洁性：当两种解释都成立时，优先选择假设较少、推理链较短的那个。如果链长差距 >=2 步，默认选择更短链，除非有明确的反证。
- 不要混淆相似概念：discovery / approved / put into production / launched / mass-produced（发现/批准/投产/推出/量产）；birthplace / ancestral home / registered residence（出生地/祖籍/户籍所在地）；adjacent to / located in / belongs to（毗邻/位于/属于）。

## 最终审查关卡

在输出任何答案之前（即使你认为不需要搜索）：
- 优胜者是否满足所有硬约束？→ 如果是，准备输出。如果不是，继续搜索或标记不确定性。
- 是否至少有一个竞争候选被明确排除？排除原因是什么？
- 最薄弱的证据是什么？它是否由两个独立来源或一个权威来源支持？
- 你是否混淆了相似概念？（参见补充规则中的列表。）

## 收敛规则（硬停止信号）

- 优胜者满足所有硬约束且竞争候选被排除 → 立即输出答案。多一个来源不会增加价值。
- 找到了优胜候选但还需要一个来源 → 切换到验证模式；使用一个权威来源，然后回答或标记剩余的不确定性。
- 对同一活跃约束进行 2 轮搜索未产生区分收益 → 停止轮换关键词。写出当前解释和一个竞争解释，与 constraint_reasoning 比较，用更好的框架继续。
- 3 轮无进展 = 1 次失败转向。在转向之前，重新检查前提。更换查询类别或框架（不仅仅是关键词）。
- 2 次失败转向且没有候选满足所有约束 → 停止。以最佳候选加不确定性回答，或说明证据不足。
- 5 个独立来源指向同一结论 → 认为是可信的，直接回答。

只有优胜者满足所有硬约束时才输出确定答案。否则输出最可能答案并注明不确定性。保持最终回复简洁；除非用户要求，否则不显示完整账本。
