---
name: constraint-reasoning
description: Use when a short-answer, puzzle, or multi-constraint research task stalls on a clue that may require inference, association, wording analysis, geography, timing, relations, or causal reasoning rather than more search.
---

# 约束推理

当搜索无法推动一个活跃约束前进时，将此用作推理工作台。不要将其视为报告格式；它是用来决定下一步行动的。

## 核心动作

对于活跃约束，在再次搜索之前，从已知事实中写出 2-5 条可能的推理链。

每条链应说明：
- known fact（已知事实）
- lens used（使用的透镜）
- inference（推理）
- supports / excludes / unclear（支持/排除/不明确）
- whether search is still needed only for verification（搜索是否仍仅用于验证）

### 示例：联想性线索

问题："Which writer born in the year of the Green Serpent wrote a novel adapted into a musical?"

约束："born in the year of the Green Serpent"

| known fact | lens | inference | result | search needed? |
|---|---|---|---|---|
| "Green Serpent" is a zodiac year | etymology / Chinese zodiac | 乙巳年 = Wood Snake year | supports | no |
| 乙巳年 cycles: 1965, 1977, 1989, 2001... | temporal | birth year in this set | narrows candidates | only to verify author birth year |

### 示例：因果线索

问题："What regulation most reduced infant mortality in Country X between 2000-2020?"

约束："most reduced infant mortality"

| known fact | lens | inference | result | search needed? |
|---|---|---|---|---|
| Infant mortality = neonatal + post-neonatal | decomposition | which component changed most? | unclear | yes — find mortality breakdown |
| Neonatal mortality driven by birth conditions | mechanism | maternal health interventions likely largest cause | supports | verify which specific regulation |

## 透镜

| 约束类型 | 可尝试的透镜 |
| --- | --- |
| associative（联想性） | 字面措辞；翻译/汉字；词源/姓氏起源；国籍/地理；传记/职业；文化原型；领域隐喻 |
| linguistic（语言性） | 原始措辞；翻译变体；字符；发音/同音词；词源；领域特定含义 |
| geographic（地理性） | 出生地/居住地/户籍所在地；区域层级；地标；历史地理；文化区域 |
| temporal（时间性） | 事件日期；批准/推出/生产/出版区分；历法系统；来源出版日期 |
| relational（关系性） | 角色成员；演员阵容/团队/组织关系；别名/翻译；来源特定措辞 |
| causal（因果性） | 机制；必要条件；充分条件；替代解释；反例 |

## 因果分解（特殊情况）

当任务询问"什么导致了 X"、"什么改进了 X"、"什么政策影响了 X"，或任何答案类别与问题表面领域不同的搜索——使用这个 4 步分解法，而不是先按类别搜索。

### 陷阱

当被问及"什么法规/技术/政策实现了结果 X"时，直觉是：
1. 将 X 映射到领域类别（例如，"更长的寿命" → "医疗法规"）
2. 在该类别内搜索匹配项
3. 如果没有找到，在同一类别内轮换关键词

这种方法会失败，因为**贡献最大的原因**通常位于直觉所暗示的领域之外。

### 方法

```
Step 1: DECOMPOSE（分解）— 将目标分解为可测量的成分。
         Target = Σ (component_i × weight_i)
         问：构成因素是什么？如何测量？

Step 2: IDENTIFY（识别）— 找出变化贡献最大的成分。
         问：哪个因素的变化解释了结果的大部分？

Step 3: TRACE（追溯）— 从该成分回溯因果链。
         问：是什么驱动了该变化？近因是什么？
         持续追溯，直到达到制度/法律/技术杠杆。

Step 4: MATCH（匹配）— 将根本杠杆映射到结构性约束。
         问：哪个实体匹配结构性线索，并且位于链条的末端？
```

### 示例

问题："What policy most increased life expectancy in Japan between 1950-2000?"

| Step | Action | Result |
|---|---|---|
| DECOMPOSE | Life expectancy = infant mortality + adult mortality + elderly mortality | 3 components |
| IDENTIFY | Infant mortality dropped ~90% in this period; adult/elderly changes were smaller | infant mortality is largest contributor |
| TRACE | What reduced infant mortality? → Infectious disease control → What enabled that? → Universal health insurance + sanitation infrastructure → What policy? → 1961 Universal Health Insurance Act | chain: insurance → disease control → lower infant mortality → higher life expectancy |
| MATCH | Does 1961 Act match temporal and structural clues? | Yes |

### 为什么这有效

| 常规搜索 | 因果分解 |
|---|---|
| "X 属于类别 Y，搜索 Y" | "X = Σ 因素，哪个因素占主导？" |
| 需要预先的领域知识 | 通过分解发现领域 |
| 错误类别 = 无限死胡同 | 错误成分 = 检查另一个因素 |
| 关键词轮换为主要策略 | 因果链收窄为主要策略 |

### 反模式

- 将 X 映射到领域类别并在其中搜索 — 类别假设
- "让我尝试 [类别] + [结构性线索]" — 错误类别中的关键词汤
- "也许它是不同类型的 [类别]" — 在相同错误框架内轮换
- 在分解之前就跳到匹配 — 匹配你不理解的东西

### 何时不使用因果分解

- 问题直接声明了领域（例如，"which programming language..."）
- 答案类型已经狭窄且明确定义（例如，"what year..."）
- 简单实体查找（直接使用 wikipedia_lookup 或 web_search）

## 停止搜索信号

如果两次搜索无法解决同一约束且你已有候选事实，在再次 web 搜索之前切换到推理。只有在推理链识别出具体的缺失事实后才进行搜索。

## 常见错误

- 为联想性线索寻找精确文本匹配。
- 将搜索结果的缺失视为推理路径的缺失。
- 在硬约束失败后仍然保留候选。
- 将来源片段作为证明使用，而不是验证特定约束。
