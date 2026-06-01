---
name: cat
description: "**证据评估完成后、输出结论前必加载。** 快速临床决策格式：PICO→检索策略→证据概要→批判性评价→Clinical Bottom Line。1-2页，床旁决策用。比 evidence-synthesis 轻量，比裸搜严谨。"
---

# Critically Appraised Topic (CAT) — 临床证据快评

## 这是什么

CAT 是循证医学中最实用的快速证据评估格式。它回答一个聚焦的 PICO 临床问题，对 1-5 篇最佳可得文献进行批判性评价，输出一个可操作的 Clinical Bottom Line。典型长度 1-2 页，20 分钟内可完成。

**适用场景：**
- 查房时遇到的具体临床问题
- 某种治疗是否有证据支持
- 某个诊断方法的准确性
- 门诊时需要快速决策

**不适用场景：**
- 需要全面系统评价的主题（用 `evidence-synthesis`）
- 需要 PRISMA 标准的正式系统综述（用 `systematic-review-methodology`）

## CAT 标准结构

### 1. 临床问题 (Clinical Question)
```
P: [患者群体、疾病、分期]
I: [干预、诊断方法、暴露因素]
C: [对照：安慰剂/标准治疗/无干预]
O: [关键临床结局]
问题类型: therapy / diagnosis / prognosis / etiology
```

### 2. 检索策略 (Search Strategy)
- 数据库：PubMed, Cochrane
- 检索词：（列出实际使用的检索式）
- 纳入/排除标准
- 检索日期

**检索优先级（CAT 中尤其重要）：**
1. 先找现成的系统评价/CAT → `pubmed_search(article_type="systematic_review")`
2. 再找 RCT → `pubmed_search(article_type="rct", clinical_query="therapy")`
3. 补充指南 → `cochrane_search`

### 3. 证据概要 (Evidence Summary)

用表格对比纳入的研究：

| 研究 | 设计 | 样本量 | 干预 vs 对照 | 主要结局 | 效应量 | GRADE |
|------|------|--------|-------------|---------|--------|-------|
| Smith 2023 | RCT, 双盲 | n=1,200 | Drug A vs Placebo | 死亡率 | RR 0.72 (0.58-0.90) | ⊕⊕⊕⊕ High |
| Jones 2022 | RCT, 开放 | n=800 | Drug A vs Standard | 死亡率 | RR 0.85 (0.68-1.06) | ⊕⊕⊕○ Moderate |

### 4. 批判性评价 (Critical Appraisal)

对每项纳入研究评估：

**RCT（Cochrane RoB 2.0）：**
- 随机化：是否充分？
- 盲法：是否设盲？谁被设盲？
- 失访：ITT 分析？失访率？
- 选择性报告：是否预设结局均有报告？
- 其他偏倚：提前终止？基线不均衡？

**系统评价（AMSTAR 2）：**
- 是否预先注册方案？
- 检索是否全面？
- 是否评估纳入研究的偏倚风险？
- 是否使用适当方法合并结果？

### 5. 证据链评估 (Evidence Chain)

```
本 CAT 的证据层级：
    ↑ 最高证据层：[是否有指南推荐？]
    ↑ 中级证据层：[是否有系统评价？]
    ↑ 基层证据：[本 CAT 纳入的研究]
```

标注每层是否存在、质量如何、链路是否完整。

### 6. 临床底线 (Clinical Bottom Line)

**这是 CAT 最重要的部分——临床医生只读这部分。** 必须用 1-3 句可操作的陈述回答原始 PICO 问题：

```
格式：
[干预] 在 [人群] 中 [效果方向]，基于 [证据量和质量]。

示例：
「Empagliflozin 在 T2DM 合并 CVD 患者中可降低心血管死亡风险
（HR 0.62, 95%CI 0.49-0.77），基于 1 项高质量 RCT (EMPA-REG, n=7,020)
和 2 项系统评价。证据链完整，GRADE 高质量。」

反面示例（糟糕的 Clinical Bottom Line）：
「本 CAT 检索了多项文献，发现 empagliflozin 可能有多种作用，
需要进一步研究。」—— 没有回答 PICO 问题，不能用于临床决策。
```

### 7. 适用性与局限性 (Applicability & Limitations)
- 证据是否适用于你的患者群体？（年龄、合并症、疾病分期）
- 结局指标是否对患者有意义？（替代终点 vs 临床终点）
- 本 CAT 的局限性：（检索限制、未纳入灰色文献、单一评估者）
- 更新条件：（什么新证据会改变结论？建议多久后重新评估？）

## CAT vs 其他 EBM 格式

| | CAT | Evidence Synthesis | Systematic Review |
|---|---|---|---|
| 范围 | 1 个 PICO，1-5 篇 | 多个维度 | 1 个 PICO，全面检索 |
| 深度 | 批判性评价 + CBL | 证据链 + GRADE 表 | 完整 PRISMA + Meta |
| 时间 | 20 min - 2 hr | 数小时 | 数周-数月 |
| 输出 | 1-2 页 + CBL | 结构化报告 | 正式出版物 |
| 更新 | 新证据出现时 | 定期 | 定期 + 方案 |

## CAT 质量检查

- [ ] PICO 是否聚焦且可回答？（不是"某疾病的治疗"，而是"某药在某人中是否优于某对照"）
- [ ] 检索是否按证据层级自上而下？（先找 SR，再找 RCT）
- [ ] 每项纳入研究是否做了批判性评价？（不是简单抄摘要）
- [ ] Clinical Bottom Line 是否可直接用于临床决策？（含糊 = 不合格）
- [ ] 适用性是否明确？（对谁说、在什么条件下成立）
- [ ] 局限性是否诚实？（检索不全？证据薄弱？明确说）
