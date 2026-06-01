# EBM Agent OS — 循证医学深度研究系统

基于 Agent OS 内核的循证医学 AI 研究助手。自动构建 PICO 框架、按证据层级检索（指南→系统评价→RCT）、逐跳 GRADE 评级、输出 Clinical Bottom Line。

## 快速开始（5 分钟）

### 1. 环境要求
- Python 3.11+
- Git
- 一个 DeepSeek API Key（[platform.deepseek.com](https://platform.deepseek.com) 

### 2. 克隆并安装
```bash
git clone git@github.com:V-rand/EBM.git
cd EBM
uv sync
```

### 3. 配置 API Key
```bash
cp .env.example .env
```
编辑 `.env`，填入你的 DeepSeek API Key：
```bash
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
```

### 4. 启动
```bash
uv run python cli.py
```

看到 `EBM 未选择>` 提示符就成功了。输入自然语言开始。

### 5. 跑一个测试问题
```
EGFR突变晚期NSCLC中osimertinib一线治疗证据如何？请用循证医学方法回答。
```

系统会自动：加载 PICO 技能 → 检索 Cochrane/PubMed 指南和系统评价 → 读取关键 RCT → GRADE 评估 → 输出 Clinical Bottom Line。

## 它是什么

EBM Agent OS 不是聊天机器人——它是一个**自主研究 Agent**。给定一个临床问题，它会：

1. **构建 PICO** — 把问题分解为患者/干预/对照/结局
2. **自上而下检索** — 先找指南和系统评价，再验证底层 RCT
3. **逐跳 GRADE 评级** — 证据链路中每一层独立评估质量
4. **构建证据链路** — 每条结论标注「指南←SR←RCT」的完整追溯路径
5. **输出 Clinical Bottom Line** — 临床医生可直接用的操作结论

与 ChatGPT/通用 AI 的关键区别：
- 不靠训练记忆编造引用——每条引用对应本次会话实际检索到的来源
- 证据链可追溯——你知道结论是从哪篇指南、哪项 RCT 来的
- 断链诚实标注——找不到证据就说找不到，不硬编

## 工具体系

| 工具 | 用途 | 示例 |
|------|------|------|
| `pubmed_search` | PubMed 生物医学文献，支持 EBM 过滤 | `pubmed_search(article_type="systematic_review")` |
| `cochrane_search` | Cochrane 系统评价 | `cochrane_search(query="SGLT-2 inhibitor MACE")` |
| `clinical_trials` | ClinicalTrials.gov 临床试验 | `clinical_trials(condition="diabetes", intervention="metformin")` |
| `medrxiv_search` | medRxiv 预印本（未评议最新研究） | `medrxiv_search(query="long COVID treatment")` |
| `openalex_works` | 扩展学术检索/引用链追踪 | `openalex_works(indexed_in="pubmed")` |

## 技能管线

系统有 8 个可加载的技能，模型会根据任务自动选择：

| 技能 | 触发时机 | 作用 |
|------|---------|------|
| `pico-formulation` | 检索前 | 构建 PICO 框架，确定最佳研究设计 |
| `retrieval_strategy` | PICO 后 | 规划检索策略，按证据层级选工具 |
| `evidence-appraisal` | 检索后 | GRADE 逐跳评估证据质量 |
| `cat` | 快速决策 | 1-2 页 Critically Appraised Topic + Clinical Bottom Line |
| `evidence-synthesis` | 深度报告 | 完整 IMRaD 报告 + GRADE 证据概览表 |
| `systematic-review` | 系统评价 | PRISMA 标准全流程 |
| `self-audit` | 输出前 | 自审引用真实性/数字一致性/结论强度 |
| `domain_sites` | 需要额外领域 | 补充特定领域权威网站 |

## 测试用例

以下问题覆盖了 EBM 的不同场景，用于评估系统表现：

### 治疗类（Therapy）
```
在2型糖尿病合并CVD患者中，SGLT-2抑制剂能否降低MACE风险？用循证医学方法回答。
```
> 预期：自上而下检索（guideline→SR→RCT），输出 FLAURA/EMPA-REG 等 landmark trial 的 HR+CI，构建完整证据链路。

```
对于75岁以上老年人，他汀类药物一级预防能否降低全因死亡？获益是否大于风险？
```
> 预期：识别证据链路断点（USPSTF I 声明、ALLHAT-LLT 趋势危害），诚实地标注"证据不足，不能推荐"而非强行给结论。

```
EGFR突变晚期NSCLC中osimertinib一线治疗证据如何？
```
> 预期：检索 NCCN/ESMO 指南 + FLAURA RCT，对比单药 vs 联合化疗，给出分层 Clinical Bottom Line。

### 诊断类（Diagnosis）
```
低剂量CT筛查肺癌在高危人群中的敏感性和特异性如何？是否有过度诊断的证据？
```

### 预后类（Prognosis）
```
急性心肌梗死后射血分数保留（HFpEF）患者的5年生存率及主要预后因素？
```

### 病因/危害类（Etiology/Harm）
```
长期使用质子泵抑制剂（PPI）是否与胃癌风险增加相关？证据强度如何？
```

### 预防类（Prevention）
```
维生素D补充在社区老年人中预防跌倒的效果如何？不同剂量和人群的效应差异？
```

### 快速 CAT
```
用CAT格式快速回答：缺血性卒中急性期，替奈普酶（tenecteplase）相比阿替普酶（alteplase）的疗效和安全性？
```
> 预期：自动加载 CAT skill，输出 1-2 页结构化快评。

## 评估指标

测试时关注以下几点：

| 维度 | 检查项 |
|------|--------|
| **证据层级** | 是否先搜 guideline/SR，再搜 RCT？ |
| **引用真实性** | 是否有 "PMID: TBD" 或记忆编造的引用？ |
| **效应量完整性** | 是否附带 95% CI？是否标注 GRADE？ |
| **证据链** | 是否标注了从指南到 RCT 的追溯路径？ |
| **断链标注** | 证据不足时是否诚实标注而非硬编？ |
| **Clinical Bottom Line** | 结论是否可直接用于临床决策？ |
| **自审** | 报告写入后是否加载 self-audit 检查？ |

## 常见问题

**Q: 需要什么 API Key？**
DeepSeek API Key 即可（[platform.deepseek.com](https://platform.deepseek.com)），新用户有免费额度。可选配置：NCBI_API_KEY（提升 PubMed 速率限制）、TAVILY_API_KEY（提升网页搜索质量）。

**Q: 一次完整研究要多久？**
快速 CAT 约 1-2 分钟。深度证据综合报告约 3-5 分钟。取决于证据量和网络速度。

**Q: 为什么有时候报错？**
PubMed 有速率限制（3 次/秒无 key，10 次/秒有 key）。系统会自动重试。如果频繁 429 错误，去 [NCBI](https://www.ncbi.nlm.nih.gov/account/) 注册免费 API key 填入 `.env`。

**Q: 我能问个人健康问题吗？**
系统会回答，但不会启动完整研究管线（不搜 PubMed、不写 CAT）。这类问题得到的是轻量常识分析 + 免责声明。它是个研究工具，不是医生。

## 项目结构
```
EBM/
├── cli.py                    # CLI 入口
├── config.yaml               # 运行配置
├── agent_os/                 # 核心运行时
│   ├── kernel/               # AgentLoop (ReAct) + 守护机制
│   ├── tools/                # 检索工具（pubmed/cochrane/ebm...）
│   ├── memory/               # 上下文编译/工作区记忆
│   ├── prompts/              # 系统提示词（agent_system.txt 等）
│   └── skills/               # Skill 加载器
├── skills/                   # 零代码工作流（Markdown）
│   ├── pico_formulation/     # PICO 框架
│   ├── retrieval_strategy/   # 检索策略
│   ├── evidence_appraisal/   # GRADE 评估
│   ├── cat/                  # Critically Appraised Topic
│   ├── evidence_synthesis/   # 证据综合报告
│   ├── systematic_review/    # 系统评价方法
│   ├── self_audit/           # 输出前自审
│   └── domain_sites/         # 领域站点
└── data/                     # 会话数据（工作区/归档）
```

## 运行示例

```
EBM> EGFR突变晚期NSCLC中osimertinib一线治疗证据如何？

系统自动执行：
 ✓ 加载 pico-formulation → 构建 PICO 框架
 ✓ 加载 retrieval_strategy → 规划检索策略
 ✓ pubmed_search(article_type="guideline") → 检索 NCCN/ESMO/CSCO 指南
 ✓ cochrane_search + pubmed_search(article_type="systematic_review") → SR
 ✓ pubmed_search(article_type="rct") → 验证 FLAURA 关键 RCT
 ✓ 加载 evidence-appraisal → GRADE 逐跳评级
 ✓ 加载 cat → 写 CAT 报告
 ✓ 加载 self-audit → 自审引用和数字
 → 输出 Clinical Bottom Line
```

## 技术栈

Python 3.11+ · asyncio · DeepSeek API (OpenAI 兼容) · SQLite (FTS5) · Rich TUI · uv 包管理
