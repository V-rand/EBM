---
name: pico-formulation
description: Use when the research requires building a structured PICO (Patient, Intervention, Comparison, Outcome) framework for a clinical question before searching. Load this skill before any search for therapy/diagnosis/prognosis/etiology questions.
---

# PICO Framework — 循证医学临床问题构建

## 何时使用

当你需要回答一个临床问题，需要在**系统检索**之前先构建 PICO 框架时使用。PICO 将模糊的临床问题转化为结构化的检索策略。

## PICO 框架

| 要素 | 含义 | 示例 |
|------|------|------|
| **P** (Patient/Population/Problem) | 患者群体、疾病或状况 | 2型糖尿病患者，年龄≥65岁 |
| **I** (Intervention/Exposure) | 干预措施、诊断方法或暴露因素 | SGLT-2抑制剂（empagliflozin） |
| **C** (Comparison/Control) | 对照措施 | 二甲双胍或安慰剂 |
| **O** (Outcome) | 临床结局指标 | 主要不良心血管事件（MACE） |

## 问题类型匹配

| 问题类型 | PICO 侧重 | 最佳研究设计 | 推荐检索策略 |
|----------|-----------|-------------|-------------|
| Therapy（治疗） | 干预 vs 对照的效果 | RCT | `pubmed_search(article_type="rct", clinical_query="therapy")` |
| Diagnosis（诊断） | 诊断试验准确性 | 横断面研究 | `pubmed_search(clinical_query="diagnosis")` |
| Prognosis（预后） | 疾病结局预测 | 队列研究 | `pubmed_search(clinical_query="prognosis")` |
| Etiology/Harm（病因/危害） | 风险因素与结局 | 队列/病例对照 | `pubmed_search(clinical_query="etiology")` |
| Prevention（预防） | 预防措施效果 | RCT/队列研究 | `pubmed_search(article_type="rct")` |
| Economic（经济学） | 成本效益 | 经济学分析 | `web_search` + 特定数据库 |

## PICO 检索策略构建

### 步骤 1: 分解 PICO

先用 `pico_analysis` 工具或 `research_state` 写出 PICO 分解：

```
research_state(content="
## PICO 框架
P: 2型糖尿病患者（HbA1c > 7%，eGFR > 30）
I: Empagliflozin 10mg/d
C: Metformin 2000mg/d 或安慰剂
O: MACE（心血管死亡、非致死性心梗、非致死性卒中）
## 问题类型: therapy
## 纳入标准: RCT, ≥12个月随访
")
```

### 步骤 2: 构建检索策略

PICO 各要素转换为检索词并 **分步检索**：

1. **第一步** — 用 P+I 定位核心文献：
   ```
   pubmed_search(query="(type 2 diabetes) AND (empagliflozin OR SGLT-2 inhibitor)", article_type="rct", max_results=10)
   ```

2. **第二步** — 如需更精确：
   ```
   pubmed_search(query="EMPA-REG OUTCOME[Title] OR empagliflozin cardiovascular", year="2015-2024")
   ```

3. **第三步** — 系统评价/荟萃分析：
   ```
   pubmed_search(query="SGLT-2 inhibitor cardiovascular outcomes type 2 diabetes", article_type="systematic_review")
   ```

### 步骤 3: 补充检索

- `clinical_trials` — 查找正在进行的临床试验
- `cochrane_search` — 查找 Cochrane 系统评价
- `web_search(site:pubmed.ncbi.nlm.nih.gov)` — 特定文献
- `openalex_works(indexed_in="pubmed", ...)` — 扩展元数据

## PICO 质量检查清单

- [ ] P — 是否明确了患者群体（年龄、疾病阶段、合并症）？
- [ ] I — 干预是否具体（剂量、给药途径、频率）？
- [ ] C — 对照是否明确（安慰剂、标准治疗、无治疗）？
- [ ] O — 结局是否可测量（主要结局、次要结局、安全性）？
- [ ] 问题类型是否确定（therapy/diagnosis/prognosis/etiology）？
- [ ] 最佳研究设计是否匹配问题类型？
- [ ] 检索策略是否覆盖了 PICO 中的所有关键要素？

## 收敛规则

- 找到一篇匹配 PICO 的高质量系统评价/RCT → 仔细阅读，**不需要重复检索**
- 检索结果过多 → 添加更具体的 P 或 O 限定词
- 检索结果过少 → 放宽 I 或 C 的限定（如用药物类别代替具体药名）
- 2 轮无进展 → 检查 PICO 分解是否有误
