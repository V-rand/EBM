---
name: long-form-research
description: Use when the user needs a comprehensive clinical evidence synthesis, systematic review report, structured analysis, comparison, guideline appraisal, or decision support document. Load this skill BEFORE any search for long-form EBM tasks.
---

# 临床证据综合报告规范

目标是生成一份结构化、可验证、引用忠实、对临床决策有用的循证医学报告。方法论与问题研究一致（推理→检索→验证→综合），但需要在多个维度上组织证据、评估质量、区分强度。

The goal is a structured, verifiable clinical evidence synthesis with sufficient coverage, coherent argumentation, faithful citations, and clinical utility. The method is constraint-driven reasoning and evidence verification organized over multiple dimensions. Long-form does NOT mean "search broadly first and reason later" — it means synthesizing more dimensions, each requiring the same reasoning discipline.

## Research Lifecycle

Follow the 7-step research loop. Each step produces output that feeds the next. The loop applies to every dimension and every search decision within the report.

**1. Start from the concrete problem.**
Clarify what decision, judgment, or explanation the research must support. Audience, scope, time boundary, what is NOT answered. Avoid vague curiosity — convert into a concrete question.

**2. Investigate reality first.**
Gather primary facts, source materials, timelines, actors, incentives, constraints, and observable outcomes before forming strong conclusions. Do not build conclusions on weak sources (media/community) — they can prompt investigation, not support it.

**3. Identify contradictions.**
Look for tensions: claims vs evidence, theory vs practice, stated goals vs incentives, short-term vs long-term effects, mainstream view vs anomalies. A report without contradictions is a summary, not research.

**4. Grasp the principal contradiction.**
Do not list everything equally. Determine which conflict, variable, or uncertainty most strongly shapes the outcome. The report's structure should lead from this principal contradiction.

**5. Form a provisional synthesis.**
Build the best current explanation from evidence. State confidence, assumptions, missing information, and alternative interpretations. Cite sources that actually support each claim.

**6. Return to practice.**
Test the synthesis against additional evidence, counterexamples, real-world constraints, and user goals. Revise the question if needed. 3+ search rounds without progress → check premises, not keywords.

**7. Spiral upward.**
Repeat until the answer is not merely more detailed, but more accurate, more structured, and more useful.

## Research Architecture

**Research Frame:**
Clarify the judgment type: explanation, comparison, decision support, systematic review, trend judgment, risk assessment, roadmap. Write explicit scope, time boundary, object boundary, and non-goals.

**Coverage Map:**
Break into 3-7 research dimensions: background, definitions, mechanisms, key actors, evidence, controversies, counterarguments, cases, trends, risks, evaluation metrics. Track each dimension as covered / weak / out-of-scope. Revisit after each search round — if a dimension remains empty, either search for it, mark it out of scope, or explain the gap. The Coverage Map is a control surface, not a table of contents.

**Source Strategy:**
Match source types to dimensions:
- primary/official sources → for facts, rules, and legal constraints
- academic sources → for mechanisms, evidence, and theoretical foundations
- industry/report sources → for market data, practice, and trends
- media/community sources → for phenomena, clues, and opinions only. Cannot alone support key conclusions.

Each key claim in the report must trace back to its source. Do not use one weak source to support a paragraph of strong judgment.

## Search Strategy for Long-Form Research

Every search in long-form research must have an expected gain. Do not "search broadly first and explore." Each search round targets a specific research dimension.

**Domain drilldown**: Before broad web_search, identify authoritative domains for the dimension. Use those domains with site: operators. If the first domain fails, try the next — do not remove the domain lock and search the whole web.

**Archive-first**: Before any new search, check raw_search/ for existing results. Use workspace_search to see what's already in the session. Re-reading an existing result is more efficient than re-searching.

**Structured tools first**: Match the dimension to the appropriate tool:
- Literature/theory → openalex_works, arxiv_search
- Biomedical → pubmed_search
- Law/regulation → law_retrieve
- Known entity → wikipedia_lookup
- Market/industry → web_search with domain lock
- General discovery → web_search (only as entry point, then drill into a returned domain)

**3-strike rule per dimension**: If 3 search rounds on one dimension produce no new evidence, either mark it out-of-scope and explain the gap, or re-frame the question to a narrower searchable version.

**No dry search**: Before each search, articulate: "I am searching for X because [reasoning]. If I find Y, it will [verify/falsify] Z." If you cannot complete this sentence, reason first.

**Search-mode labeling**: Before each batch, state the mode: discovery, domain_drilldown, verification, or cross_verify. The mode determines search breadth and tool choice.

## 思考外化：research_state 草稿纸

`research_state` 是一张自由格式的草稿纸。调 `research_state(content="...")` 时，**系统会把完整草稿内容写在返回值里**，模型立刻看到。不传 content 调用就只读当前草稿。

**写法示例：**
```
research_state(content="
## 维度覆盖
- 基本扣除标准演变: covered
- 专项附加扣除设计: weak (只搜到官方文件，缺实证)
- 纳税人数量变化: not_started
- 日本比较: covered
- 德国比较: not_started

## 当前工作
正在深挖：专项附加扣除的实证效果
已搜：site:cnki.net 个税专项扣除 实施效果
发现：一篇 CHFS 数据的研究，正在 web_read
缺口：2019 年的第一年数据

## 疑问
- 子女教育和赡养老人扣除有重复？需要核实
- 德国 Grundfreibetrag 2024 年调整到多少？
")
```

**调用时机**：切换维度、更新覆盖后、有了新发现时随时调。长时间未调用系统会温和提示。


## Evidence Synthesis

For key claims, extract as ECRI (Evidence, Claim, Reasoning, Impact), plus counterevidence, scope, and confidence. ECRI is a synthesis discipline, not a visible template that every sentence must follow. Do not pile web summaries into a report — each key claim must have:
- What specific evidence supports it (with source)
- What the claim actually means (not just re-stating evidence)
- How the evidence leads to the claim (reasoning chain)
- Why this claim matters for the overall judgment (impact)

## Argument Structure

Each section must have: a central claim → supporting evidence → limitations → contribution to overall judgment. Sections must form an inference chain, not a parallel material library. If evidence is mixed, state what is established, what is plausible, and what remains unresolved. Distinguish facts, interpretations, inferences, and recommendations. Distinguish correlation from causation. Conclusion strength must not exceed evidence strength.

## Citation Verification Protocol

报告初稿先写入 `drafts/`，**然后 spawn 引用校验子 Agent** 对 `drafts/` 中的文件做验证。先写 draft 再校验，没有归档文件时无法验证引用真实性。

**Spawn 校验子 Agent（使用 citation_checker 系统提示词）：**
```
spawn(
  task="校验以下报告的参考文献是否真实存在。对每条引用，用 file_tree, file_grep, file_list, file_read 回溯检查：\n\n报告全文如下：\n{全文}",
  tools=["file_tree", "file_grep", "file_list", "file_read"],
  subagent_type="explore",
  max_iterations=15,
  system_prompt=citation_checker,
)
```

**并行文件操作原则（减少往返轮次）：**
- 先 `file_tree raw_search/` 看清目录结构
- 然后在同一轮内并行发起多个 `file_read` + `file_grep` + `file_list`（如一次读 4 个文件、同时 grep 多个关键词）
- 不要一个文件一个文件地串行读

**处理校验结果：**
- 通过 → 保留
- 存疑 → 修正引用字段使其与归档一致，或降低置信度标注
- 无归档 → 删除引用，正文标注 "据推断/未核实"

校验通过并完成自我 review 后，从 `drafts/` 复制到 `research/`。校验**未**通过则留在 `drafts/` 修正后再复检。

## Report Review Gate

Before output, check:
- Does the report answer the user's actual decision or question?
- Are major dimensions covered, or are gaps explicit?
- Does every important claim have source support?
- Are strong opposing views represented fairly?
- Are causal claims distinguished from correlation?
- Are confidence and update conditions stated?
- Is the report structured for the reader, not for the research log?

## Report Output

Default structure: executive summary, method/scope, key findings, analysis, uncertainties, sources, next questions. Adjust to user format requirements. 初稿先写入 `drafts/`，校验通过后复制到 `research/`。初稿的引用验证、self review 都在 `drafts/` 完成。校验未通过的稿子不要移到 `research/`。若结论影响未来工作，另写 `research/memory/` 并更新 `MEMORY.md`。

## Report Writing Protocol

When writing the final report, follow these rules:

1. **Report Contract**: Confirm report type, audience, purpose, length, tone. Default to professional readers, concise but complete.
2. **Structure Rules**: Headings establish logical hierarchy. Each section answers one central question. Start with a claim, then evidence, explanation, limitations. Do not write research process as a diary.
3. **Citation Rules (GB/T 7714)**:
   - **HARD RULE: 每条引用必须来自本次会话中实际检索获取的来源。禁止使用预训练记忆中的文献信息——你训练数据里的作者、年份、DOI 不可靠，必须经本会话中真实调用的检索工具（web_search / web_read / openalex_works / pubmed_search / wikipedia_lookup 等）返回并归档到 raw_search/ 后才可引用。**
   - 引用前，先确认：这条信息的原始来源有没有在本会话中被检索到并归档？没有 → 不引用，标注"据推断/未核实"。
   - 期刊论文的作者名、题名、刊名、年份、页码必须从实际获取的原始页面中逐字摘抄，不要靠记忆补全缺漏字段。
   - **In-text**: Every factual claim, data point, or quoted analysis MUST carry an inline citation marker: `[1]`, `[2]`, etc. Multiple sources for one claim: `[1][3]` or `[1,3]`. Citations numbered in order of first appearance.
   - **References section**: At the end of the report, list all cited sources in standard format. Do NOT use loose format like "source: title, URL". Follow the formats below:

   | Source type | Format | Example |
   |---|---|---|
   | 网页/在线资源 [EB/OL] | 责任者. 题名[EB/OL]. (发布日期)[引用日期]. URL. | 国家统计局. 2024年国民经济运行情况[EB/OL]. (2025-01-17)[2026-05-23]. https://www.stats.gov.cn/... |
   | 期刊论文 [J] | 作者. 题名[J]. 刊名, 年份, 卷(期): 页码. | 赵秉志. 中国死刑改革问题研究[J]. 中国法学, 2011(3): 55-70. |
   | 政府文件/法律法规 [Z] | 发布机关. 题名[Z]. 发布日期. | 全国人大常委会. 中华人民共和国刑法修正案(八)[Z]. 2011-02-25. |
   | 报告 [R] | 责任者. 题名[R]. 出版地: 出版者, 年份. | Amnesty International. Death Sentences and Executions 2024[R]. London: Amnesty International, 2025. |
   | 报纸 [N] | 作者. 题名[N]. 报纸名, 日期(版次). | 张军. 限缩死刑适用是当前主要任务[N]. 法制日报, 2014-06-15(3). |
   | 图书 [M] | 作者. 书名[M]. 出版地: 出版社, 年份. | 陈兴良. 死刑备忘录[M]. 北京: 法律出版社, 2006. |

   - **Archived source**: If a source was retrieved via web_search and archived to `raw_search/`, ALSO include the archive path: `... URL. (归档: raw_search/web_search/20240501_query.md)`
   - **Every number in the report body must be traceable to a citation.** If a claim has no source, it is an inference — label it as such ("据估算" / "据推断").
4. **Formula and Number Rules**: Formulas must define variables, units, applicable conditions, calculation basis. Numbers must explain time, region, sample, or statistical basis. Do not compare data with different bases.
5. **Tables and Figures**: Tables serve comparison, classification, timelines, or evidence matrices — not decoration. Headers must be comparable dimensions. Each row traceable to a source.
6. **Logic Rules**: Distinguish facts, interpretations, inferences, recommendations. Distinguish correlation from causation. Conclusion strength ≤ evidence strength. Present opposing views fairly.
7. **Professional Style**: Delete empty clichés ("值得注意的是", "深入探讨", "综上所述"). Use fewer adjectives, more verifiable facts, comparisons, limitations, judgments. Prefer precise transitions: because, however, therefore, under this scope.
8. **Final QA Gate**: Structure clear? Claims have evidence? Citations correct? Numbers/formulas have bases? Opposing views covered? Limitations explicit? Summary can be read independently?

## Chinese Humanize: AI 写作痕迹消除

写完报告初稿后，逐段执行以下检查。这是提交前的最后一道清洗工序。

### 必须删除的空洞套话

| 模式 | 示例 | 替换 |
|------|------|------|
| 无信息量的开场 | "值得注意的是"、"深入探讨"、"众所周知" | 直接进入事实 |
| 段落结尾水词 | "综上所述"、"总而言之"、"由此可见" | 用具体结论替代 |
| 意义膨胀 | "具有重大意义"、"发挥关键作用"、"里程碑式" | 改为精确描述：解决了什么、影响了谁、程度如何 |
| 过度评价 | "极为有效"、"显著提升"、"大幅改善" | 给出数字：提升了 X% (来源: [1]) |

### 必须修改的 AI 高频词汇

以下词汇一律替换为精确、具体的表述：

| AI 高频词 | 改为 |
|-----------|------|
| 赋能 | 为...提供技术支持 / 帮助...实现... |
| 抓手 | 切入点 / 主要措施 |
| 闭环 | 完整流程 / 从...到...的循环 |
| 倒逼 | 推动 / 促使 |
| 加持 | 借助 / 利用 |
| 底层逻辑 | 根本原因 / 基本机制 |
| 持续优化 / 深化 | 具体说明做了什么优化 |
| 多维度 / 全方位 / 系统性 | 列出具体是哪些维度 |

### 语气审查

| 问题 | 检查方法 |
|------|---------|
| 保险过多 | 统计"可能"、"或许"、"一定程度上"出现次数。保留证据强度匹配的部分，删掉多余的 |
| 被动泛滥 | "被认为"、"被实施"、"被采用" → 能改成主动就改 |
| 每段结尾千篇一律 | 随机抽 5 段看最后一句，句式重复超过 3 段就修 |
| 学术八股 | "首先...其次...最后..."、"一方面...另一方面..." → 拆开，改自然过渡 |
| 中文西化 | "对...进行...处理" → "处理了..."；"在...的基础上" → 删 |

### 自检清单

- [ ] 全文搜索"值得注意的是"，删到 0
- [ ] 全文搜索"综上所述"，删到 0
- [ ] AI 高频词表中的词全替换
- [ ] 每个数据点都带了引用标记 [n]
- [ ] 保险词密度 ≤ 每 500 字 1 个
- [ ] 连续 3 句以上开头相同 → 修
- [ ] 连续 3 段以上结尾句式相同 → 修

## English Humanize: AI Writing Pattern Removal

After drafting any English report, run this pass on every section. Adapted from paper-writer Phase 4.

### Patterns to Remove

| # | Pattern | Example / Fix |
|---|---------|---------------|
| 1 | Significance inflation | "pivotal", "groundbreaking", "paradigm-shifting" → state actual impact |
| 2 | Notability claims | "landmark study", "renowned expert" → cite the study, name the expert |
| 3 | Superficial -ing phrases | "highlighting the importance of..." → "because..." |
| 4 | Promotional language | "remarkable results", "dramatic improvement" → give the numbers |
| 5 | Vague attributions | "Studies have shown" → "[1] found that..." |
| 6 | Formulaic challenges | "Despite challenges... future outlook..." → state the challenge |
| 7 | AI vocabulary | "additionally", "crucial", "delve", "landscape", "pivotal" → replace |
| 8 | Copula avoidance | "serves as" / "stands as" → "is" |
| 9 | Negative parallelisms | "Not only... but also..." → split into two sentences |
| 10 | Rule of three | Forcing unrelated ideas into groups of three → let content decide |
| 11 | Synonym cycling | "Patients... Participants... Subjects..." → pick one, stick to it |
| 12 | False ranges | "from X to Y" on unrelated scales → use separate statements |
| 13 | Em dash overuse | > 2 em dashes per page → convert to periods or commas |
| 14 | Unnecessary Title Case | "the Research Method" → "the research method" |
| 15 | Curly quotes | "smart quotes" → "straight quotes" |
| 16 | Filler phrases | "In order to", "It is important to note", "comprehensive investigation" → delete |
| 17 | Excessive hedging | "may suggest", "have the potential to" → match evidence strength |
| 18 | Generic conclusions | "The future looks bright" → state specific implication |

### Verify

- [ ] No "Additionally" / "Furthermore" at sentence start (max 1 per section)
- [ ] No "pivotal" / "crucial" / "landscape" / "delve"
- [ ] No "-ing" phrases tacked on for fake depth
- [ ] No "serves as" / "stands as" (use "is")
- [ ] Em dashes used sparingly (< 2 per page)
- [ ] Consistent terminology (no synonym cycling)
- [ ] Sentence rhythm varies (short and long sentences mixed)
- [ ] Hedging proportionate to evidence strength

## Expanded QA Gate

提交前完成以下检查：

**结构**
- [ ] 报告回答了用户的实际问题
- [ ] 每个章节回答一个中心问题
- [ ] 摘要可独立阅读

**证据**
- [ ] 每个关键声明有来源支持
- [ ] 每个数据点可追溯到引用 [n]
- [ ] 引用格式符合 GB/T 7714
- [ ] 弱来源没有被包装成强证据
- [ ] **每条引用有对应的 raw_search/ 归档文件——web_search、web_read、openalex_works 等工具的结果均自动归档，引用前确认存在**

**逻辑**
- [ ] 区分了事实、解读、推断、建议
- [ ] 区分了相关性和因果性
- [ ] 结论强度不超过证据强度
- [ ] 对立观点得到公平呈现

**完整性**
- [ ] 明确标注了数据缺口和不确定区间
- [ ] 明确标注了推断（"据估算"、"基于...的推断"）
- [ ] 更新条件已说明（什么新信息会改变结论）

**文风**
- [ ] Humanize 清单全过
- [ ] 空洞套话清零
- [ ] 文风一致（不混用口语/学术/新闻体）
