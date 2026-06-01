---
name: systematic-review-methodology
description: "正式 PRISMA 系统评价/Meta分析全流程：方案注册→检索策略→文献筛选→质量评估→数据提取→Meta分析→证据综合。需要发表级严谨性时使用。加载前需已完成 evidence-synthesis 基础报告。"
---

# Systematic Review Methodology — 系统评价方法学

## 何时使用

当需要进行**系统性的文献检索和证据综合**时使用。这包括：
- 回答一个聚焦的临床问题（PICO）
- 对现有证据进行全面、可复现的检索
- 评估纳入研究的质量
- 综合证据形成结论

## 流程概览

```
1. 确定问题 (PICO) → 2. 制定检索策略 → 3. 筛选文献 → 4. 质量评估 → 5. 数据提取 → 6. 证据综合
```

## Step 1: 明确问题

使用 `skill_use("pico-formulation")` 构建 PICO 框架。用 `research_state` 写下：

```
research_state(content="
## 系统评价方案
### PICO
P: ...
I: ...
C: ...
O: ...

### 纳入标准
- 研究设计: RCT
- 人群: ...
- 干预: ...
- 对照: ...
- 结局: ...
- 语言: 英文/中文
- 年份: 2015-2024

### 排除标准
- 非原始研究（综述/述评）
- 样本量 < 30
- 随访 < 3个月
")
```

## Step 2: 检索策略

### 核心检索（PubMed）
使用 `pubmed_search` 工具，**分线检索**：

```
# 线1: P+I 核心检索
pubmed_search(query="(type 2 diabetes) AND (empagliflozin)", article_type="rct", max_results=20)

# 线2: 系统评价检索
pubmed_search(query="SGLT-2 inhibitor cardiovascular outcomes", article_type="systematic_review")

# 线3: 扩展检索（相关药物/类别）
pubmed_search(query="(SGLT-2 inhibitor OR dapagliflozin OR empagliflozin OR canagliflozin) AND (MACE OR cardiovascular death)", article_type="rct")
```

### 补充检索

- `clinical_trials` — 查找未发表/进行中的试验
- `cochrane_search` — 查找 Cochrane 系统评价
- `openalex_works(indexed_in="pubmed")` — 扩展元数据（引用关系）
- `opencitations_search(doi="...")` — 查看引用网络
- `web_search` — 查找灰色文献/会议摘要

### PRISMA 流程图

在探索性检索后用 `research_state` 记录筛选过程：

```
research_state(content="
## PRISMA 筛选
- 数据库检索: PubMed n=245, Cochrane n=38, ClinicalTrials n=15
- 去重后: n=280
- 标题/摘要筛选: n=280 → 排除 n=210 (不相关/no PICO match)
- 全文获取: n=70
- 全文筛选: n=70 → 排除 n=45 (排除原因: 研究设计不符 n=20, 人群不匹配 n=15, 结局指标不符 n=10)
- 纳入: n=25（RCT n=18，系统评价 n=7）
")
```

## Step 3: 质量评估

对每篇纳入研究进行质量评估。使用 `evidence_level` 工具或手动评估：

```
evidence_level(study_type="rct", design="double-blind placebo-controlled", limitations="")
```

对每篇纳入研究记录:
- 研究设计
- 样本量
- 方法学质量（RoB 2.0 / ROBINS-I）
- GRADE 等级
- 局限性

## Step 4: 数据提取

用 `research_state` 或 `file_write` 创建数据提取表：

```
research_state(content="
## 数据提取表
| 研究 | 年份 | 样本量 | 干预 | 对照 | 主要结局 | 效应量 | 质量 |
|------|------|--------|------|------|---------|--------|------|
| EMPA-REG | 2015 | 7020 | Empagliflozin | 安慰剂 | 3-point MACE | HR 0.86 | High |
| DECLARE | 2019 | 17160 | Dapagliflozin | 安慰剂 | MACE | HR 0.93 | High |
| CANVAS | 2017 | 10142 | Canagliflozin | 安慰剂 | MACE | HR 0.86 | High |
")
```

## Step 5: 证据综合

### 判断是否可合并
- 临床异质性: PICO 是否足够相似？
- 方法学异质性: 研究设计是否一致？
- 统计学异质性: I² 统计量

### 撰写证据综合（写入 drafts/ 进行后续 review）

每项发现按以下结构呈现：
1. **发现** — 概括效应方向和大小
2. **证据基础** — 多少项研究、总样本量
3. **一致性** — 各项研究结果方向是否一致
4. **质量** — GRADE 等级
5. **局限性** — 证据缺口

## 报告格式

系统评价报告写入 `drafts/`，包含以下章节：

1. **背景** — 临床问题的重要性
2. **方法** — 检索策略、纳入标准、质量评估方法
3. **结果** — PRISMA 流程图、纳入研究特征、证据综合
4. **讨论** — 主要发现、局限性、与既往研究比较
5. **结论** — 临床意义、未来研究方向

引用格式（GB/T 7714 + PMID）：
> [1] Zinman B, Wanner C, Lachin JM, et al. Empagliflozin, Cardiovascular Outcomes, and Mortality in Type 2 Diabetes[J]. N Engl J Med, 2015, 373(22): 2117-2128. PMID: 26378978
