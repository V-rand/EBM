# Skills 提示词设计模式

> Skills 是 AgentOS 最独特的设计之一：零代码工作流，纯 Markdown 定义。本分析深入研究所有内置 SKILL.md 的提示词工程模式。

## Skill 架构

### 加载机制

```
skill_use("long_form_research")
  │
  ├── SkillLoader.get("long_form_research")
  │     └── 从 skills/long_form_research/SKILL.md 读取
  │
  ├── 返回 skill_content 块
  │     └── 完整的 SKILL.md 内容
  │
  └── 注入会话
        └── 作为 tool 结果进入 context
```

### KV Cache 友好架构

关键设计：只有 skill name + description 在 system prompt 的 skills index 中：

```xml
<skills_index>
  <skill name="long_form_research" description="结构化报告研究..."/>
  <skill name="short_answer_research" description="约束驱动短答案..."/>
</skills_index>
```

完整内容在调用 `skill_use()` 后通过 tool result 注入 — 不污染 KV cache prefix。

### 条件激活

```yaml
# SKILL.md frontmatter
paths:
  include: ["research/"]
  exclude: ["**/temp/**"]
```

当 agent 操作匹配路径的文件时，条件 skill 自动加载。

## 内置 Skill 提示词分析

### 1. long_form_research

**场景**：需要撰写结构化分析报告、比较、综合。

**状态机**：
```
Step 1: Coverage Mapping
  └── 确定覆盖范围、边界和深度
      └── 产出：coverage_map

Step 2: Source Strategy
  └── 为每个覆盖区域规划检索策略
      └── 产出：source_strategy

Step 3: Collection
  └── 按策略执行检索
      └── 产出：raw_materials

Step 4: Organization
  └── 将材料组织成逻辑结构
      └── 产出：outline

Step 5: Drafting
  └── 撰写完整报告
      └── 产出：report_draft

Step 6: Quality Check
  └── 验证引用、准确性
      └── 产出：quality_report

Step 7: Humanize
  └── 语言润色、可读性优化
      └── 产出：final_report
```

**设计要点**：
- 每个步骤有明确的入口和出口条件
- 产出口碑化的 artifact（coverage_map, source_strategy 等）
- 写作阶段的引用协议（GB/T 7714 格式）

### 2. short_answer_research

**场景**：单事实/数字/实体，或谜题式多线索答案。

**状态机**：
```
Phase 1: Parse
  └── 解析问题，提取约束和线索
      └── 产出：constraint_set

Phase 2: Discover
  └── 初始搜索，建立候选集
      └── 产出：candidates

Phase 3: Test
  └── 测试每个候选
      └── 产出：test_results

Phase 4: Update
  └── 根据测试结果修正
      └── 产出：refined_candidates

Phase 5: Pivot
  └── 如果所有候选都失败，换方向
      └── 回到 Phase 2

Convergence Rules:
  - 某候选获得强证据 → 锁定
  - 所有候选被排除 → pivot
  - 搜索面饱和 → 选择最佳候选
```

**设计要点**：
- 搜索配方（search recipes）不是搜索关键词，而是搜索策略
- 收敛规则（convergence rules）：何时确定，何时放弃
- 锁定和回退机制

### 3. retrieval_strategy

**场景**：多步检索方法论。

**协议**：
```
Staged Search:
  Stage 1: Query → 锁定领域
  Stage 2: site: → 锁定权威源
  Stage 3: 深度阅读
  Stage 4: 回溯引用

Node Selection:
  - 从高价值节点开始（综述、教科书、权威站点）
  - 利用引用网络扩展

Domain Locking:
  - 确定领域后，使用 domain_sites 查询权威源
  - 保持在同一领域内深入
```

### 4. domain_sites

**场景**：50+ 领域权威网站目录。

```yaml
_domain_site_map:
  mathematics: ["mathoverflow.net", "arxiv.org/search/?searchtype=..."]
  physics: ["arxiv.org", "inspirehep.net"]
  chemistry: ["pubs.acs.org", "pubchem.ncbi.nlm.nih.gov"]
  biology: ["ncbi.nlm.nih.gov", "biorxiv.org"]
  ...
```

**设计要点**：
- 每个领域映射到 2-3 个权威 `site:` 操作符
- 作为 skill 而非代码 — 可被非技术用户编辑
- 在提示词中指导 agent 根据领域选择对应 site

### 5. constraint_reasoning

**场景**：多约束推理问题的破解。

**透镜（Lenses）**：
```
1. Associative Lens: 关联联想
   └── 什么概念与此相关？

2. Linguistic Lens: 语言分析
   └── 词语的多重含义、翻译

3. Geographic Lens: 地理视角
   └── 地点、位置线索

4. Causal Lens: 因果
   └── 因为A所以B
```

**设计要点**：
- 每个透镜是一种思考框架
- agent 可以切换透镜来获得不同视角
- 因果分解：将复杂约束分解为因果链

## SKILL.md 编写最佳实践

### 结构模板

```markdown
---
name: my-skill
layer: domain
description: 一句话描述
when_to_use: 什么场景触发
allowed-tools: [web_search, file_read, ...]
paths:
  include: ["research/"]
  exclude: ["**/temp/**"]
---

# Skill 名称

## 状态机
1. 步骤一：入口条件 → 动作 → 出口条件
2. 步骤二：...

## 约束规则
- 规则 1
- 规则 2

## 停止条件
- 什么时候任务完成
- 什么时候放弃

## 输出规范
- 期望的输出格式
</markdown>
```

### 设计原则

1. **给状态机，不给指令列表**
   - 坏的：依次做 1,2,3,4,5
   - 好的：每个阶段的目标 + 进入/退出条件 + 失败处理

2. **给出约束，不给模板**
   - 约束比模板更鲁棒，适应更多情况
   - 模板只适合纯格式要求

3. **给出迁移条件**
   - 什么时候从 A 到 B
   - 什么时候需要折回

4. **允许失败和修正**
   - 搜索面饱和的定义
   - 候选全失败的应对

5. **面向长程任务设计**
   - 包含"休息点"（research_state 检查点）
   - 包含进度评估机制

### 反模式

1. **过度指定** — "使用 xxx 工具" 而不是 "产生 xxx 效果"
2. **与 system prompt 冲突** — skill 应该增强而不是覆盖核心原则
3. **无退出条件** — agent 会循环直到超时
4. **忽略 KV cache** — 不要在 skill 中放大量静态内容
5. **混合多种路由模式** — 一个 skill 只做一类事
