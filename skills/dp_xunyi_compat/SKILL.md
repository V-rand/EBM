---
name: dp-xunyi-compat
description: "DP循医前端兼容输出规范：中文优先、首屏显著结论、权威建议卡、分层策略、可靠性分析、引用归档与幻觉自审。用于临床问题、循证问答、文献/报告/病例分析和需要可视化渲染的 EBM Agent 输出。"
when_to_use: "用户要求中文循证回答、DP循医展示、可靠性分析、证据链评分、引用可追溯、幻觉检查、报告/文献/病例分析。"
---

# DP循医兼容输出规范

## 目标

输出必须适合 DP循医 Web 前端渲染：首屏就能看懂结论，正文每条关键医学判断都有引用编号，参考文献能被折叠/展开和点击核验。优先使用中文；英文缩写首次出现时给中文解释。

不要把检索元数据评分写成 official GRADE。只有抽取到指南原文的 official GRADE / recommendation strength 时，才可明确称为正式 GRADE。

## 推荐输出结构

每次回答尽量使用下面的 Markdown 结构。标题必须保持中文，便于前端识别和高亮。

```markdown
## 证据状态

已分析 X 条来源，优先采用 X 条高等级证据；本轮结论属于：高可信候选 / 中等可信候选 / 初筛线索。

## 权威建议

用 2-4 句话给出最重要结论。必须写清楚适用人群、触发条件、推荐方向和不确定性。关键 claim 后接引用编号，如 [1][2]。

## 分层策略

- **适用人群 A**：推荐/不推荐/需复核什么，为什么 [1]。
- **适用人群 B**：推荐/不推荐/需复核什么，为什么 [2]。
- **特殊情况**：如分子分型、合并症、妊娠、儿童、肾功能不全、治疗线数变化等。

## 证据链

| 层级 | 来源 | 关键发现 | 可靠性 | 弱点 |
|---|---|---|---|---|
| 指南 | PMID/DOI/URL | recommendation / GRADE signals | 高/中/低 | 如仅摘要、未取全文 |
| 系统综述 | PMID/DOI/URL | outcome / effect size | 高/中/低 | 如异质性 |
| 原始研究 | PMID/DOI/URL | RCT/队列结果 | 高/中/低 | 如偏倚风险 |

## PICO

| 要素 | 内容 |
|---|---|
| P | 人群/疾病/场景 |
| I | 干预/暴露/检查 |
| C | 对照 |
| O | 结局 |

## 可靠性分析

| 维度 | 判断 | 说明 |
|---|---|---|
| 来源可靠性 | 高/中/低 | PubMed/PMC/指南/监管/上传文档等来源是否可追溯 |
| 证据类型 | 指南/SR/RCT/队列/病例/摘要 | 证据层级 |
| 直接性 | 高/中/低 | 是否匹配用户问题的 PICO |
| 抽取完整性 | 高/中/低 | 是否抽到 outcome/effect size/recommendation/citation span |
| 一致性 | 高/中/低 | 多来源结论是否一致 |
| 幻觉风险 | 低/中/高 | 是否有无证据 claim、疑似伪 PMID、引用不匹配 |

## 人工复核点

- 未完成全文 citation span 核验的地方。
- effect size 或 recommendation strength 未抽到的地方。
- 只有摘要或单一来源支持的地方。
- 与指南或其他研究冲突的地方。

## 参考文献

[1] 标题。来源/机构/期刊，年份。PMID: xxxxxxxx。URL
[2] 标题。来源/机构/期刊，年份。DOI: xxxxx。URL
```

## 写作规则

- 第一屏不要先写长篇方法学说明；先写“证据状态”和“权威建议”。
- 结论必须分层，不要把一个肿瘤、一个治疗阶段、一个检测阈值的建议泛化到全部患者。
- 每条关键医学 claim 后放引用编号。不要集中到段尾才列一串引用。
- 推荐强度、GRADE、HR/RR/OR/CI、样本量、年份必须来自本轮工具返回或上传文档，不要凭记忆补。
- 对观察性研究避免因果语气。
- 对患者问题加入“不能替代医生面诊”的安全边界；对临床/研究问题可用专业语气。
- 如果工具返回 `reliability`、`grade_readiness`、`source_database`、`reliability_scope`，优先写入“证据状态”“可靠性分析”和“证据链”。

## 可靠性分析规则

不要只给一个总分。至少拆成：

- `source_score`: 来源是否在白名单、是否有 PMID/DOI/NCT/URL。
- `design_score`: 指南、系统综述/meta、RCT、观察性研究、病例报告等证据层级。
- `validity_score`: GRADE / RoB 2 / ROBINS-I / AMSTAR 2 / QUADAS-2 / AGREE II 线索。
- `directness_score`: PICO 与用户问题是否匹配。
- `extraction_score`: 是否抽到 outcome、effect size、recommendation、citation span。
- `consistency_score`: 多来源方向是否一致。
- `recency_score`: 是否有较新指南或新研究。

链路级判断不要把所有概率简单相乘。可以用分组加权或几何均值，但必须对关键失败点做硬降级：无真实 PMID/DOI/URL、只有摘要却写成全文结论、没有 citation span 却给强临床建议、effect size 未抽到却写具体数值、多来源冲突但未说明。

## 幻觉自审

输出前检查：

- 每条关键医学 claim 是否能映射到本轮工具返回、上传文档或 raw_search 归档。
- PMID/DOI/NCT 是否来自工具返回，而不是凭记忆补写。
- 数值、年份、样本量、HR/RR/OR/CI 是否与引用一致。
- 不确定处必须标注“待复核”“仅摘要”“单一来源”或“未完成全文核验”。
