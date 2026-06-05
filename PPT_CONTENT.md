# EBM Agent OS 汇报 PPT 内容
## 每页详细内容，可直接扔给 Gemini/Claude 生成 PPT

---

## 第 1 页：问题定位

**标题：** 临床医生找证据为什么这么难

**副标题：** A Clinical AI Agent for Evidence-Based Medicine

**核心矛盾：**

- 医学论文每天发表 5000+ 篇，PubMed 收录 3700 万篇。指南每年更新。一个外科医生遇到高血压+糖尿病患者，不知道该看 ADA、ACC/AHA 还是 ESC——他不可能同时跟踪所有专科的指南
- 通用 AI（ChatGPT、DeepSeek Chat）能回答临床问题，但**不说怎么来的**：编造引用（PMID 不存在）、混淆证据等级（把病例报告当 RCT 用）、无法交叉验证
- 循证医学（Evidence-Based Medicine, EBM）的核心理念是：**临床决策必须基于当前最佳可得证据，不是基于权威意见或病理推理。** 但"找到最佳证据"这件事本身就很耗时——需要检索多个数据库、阅读全文、评估偏倚风险、判断证据等级
- 现有工具要么是搜索引擎（PubMed）——返回论文列表但不解释——要么是通用对话 AI（ChatGPT）——解释得头头是道但不说来源。**中间缺一层：能自主检索、评估、合成、溯源证据的 AI Agent**

**一句话总结：**
我们做了一个循证医学专用的 AI Agent 系统——为临床研究问题提供**可追溯、可验证、证据分级的回答**。它不靠记忆，每条结论都能往回追到具体的指南条目或原始论文。

---

## 第 2 页：核心设计理念——证据金字塔驱动的搜索

**标题：** 不是"搜到啥信啥"，是"按证据层级逐层搜索"

**关键概念：证据金字塔（Hierarchy of Evidence）**

循证医学把所有可用的证据从"最不可信"到"最可信"排成金字塔：

```
第1层 临床实践指南 (Guideline)          ← 最后相信。不是一篇论文，
    例：NCCN 肿瘤指南、                         是一群顶级专家把该领域所有
    ESC心血管指南、KDIGO肾病指南                   研究读完后写的"操作手册"。
                                              医生遇到问题，先看有没有指南。
                                              
第2层 系统评价 / Meta分析                        ← 把已有的所有RCT汇总起来
    (Systematic Review / Meta-Analysis)          重新算一遍。解决的问题：
    例：Cochrane系统评价、                        单篇RCT可能碰巧有效——
    BMJ网络荟萃分析                                10篇RCT都有效才是真有效。

第3层 随机对照试验 (RCT)                          ← 证明"药有效"的最强证据。
    例：FLAURA试验（osimertinib）                  把病人随机分两组——一组吃
    EMPA-REG OUTCOME（empagliflozin）              真药、一组吃安慰剂。两组都
                                                 不知道自己吃的是啥。唯一的
                                                 区别就是药。

第4层 观察性研究                                   ← 不干预，只观察。只能报告
    (Cohort, Case-Control)                         "关联"，不能证明"因果"。
    例：Framingham心脏研究

第5层 病例报告 / 专家意见                          ← 最不可信。一个人说"我试
    (Case Report / Expert Opinion)                 了，有用"。可能是运气好。
```

**我们的设计：系统从金字塔顶往下搜索。**

不是"输入关键词查 PubMed 看返回什么"，而是：
1. 先搜 guidelines——有指南吗？没有？
2. 再搜 systematic reviews——有系统评价吗？没有？
3. 再搜 RCTs——有随机试验的数据吗？
4. 底层证据不能推翻上层结论。如果只有观察性研究，结论要标注"未能通过 RCT 验证，GRADE Low"

**这意味着什么：** 我们的系统不是在"搜索"，而是在"逐层排查证据"。每一层都是一个独立的检索验证步骤。这和 ChatGPT 的"搜一下网页然后用记忆回答"完全不同。

---

## 第 3 页：完整链路——一条真实查询跑到底

**标题：** osimertinib 在 EGFR 突变 NSCLC 中一线治疗证据如何？

**输入：** "EGFR突变晚期NSCLC中osimertinib一线治疗证据如何？请用循证医学方法回答。"

**实际运行 10 轮，逐轮展示系统做了什么：**

```
第1轮 · 理解问题（Ask）
  → 自动识别：therapy 问题
  → 加载 pico-formulation skill（Markdown 工作流，3000 字）
  → 在 thinking 中构建 PICO：
      P: EGFR突变（exon 19del / L858R）晚期NSCLC
      I: osimertinib 80mg qd
      C: 一代/二代 EGFR-TKI（吉非替尼、厄洛替尼）
      O: PFS（无进展生存）、OS（总生存）
  → 写入 research_state（跨轮次思考草稿纸）

第2-3轮 · 获取证据（Acquire）
  → pubmed_search(article_type="guideline", query="osimertinib EGFR NSCLC")
      返回：NCCN 指南 v3.2024——osimertinib 一线首选（Category 1）
  → pubmed_search(article_type="systematic_review", query="osimertinib first-line EGFR")
      返回：Zhao 2019 BMJ（18 RCTs, n=4,628）
            Zhang 2024 BMC（35 RCTs, n=9,718）
  → pubmed_search(article_type="rct", query="FLAURA osimertinib")
      返回：FLAURA——N=556, 双盲多中心, PFS HR 0.46 (0.37-0.57), OS HR 0.80 (0.64-1.00)
  → 每次检索结果自动归档到 raw_search/ 目录
     （文件命名：raw_search/pubmed_search/时间戳_query关键词.md）

第4轮 · 逐跳验证
  → 指南说"首选 osimertinib"→ 查指南引用了哪些系统评价？
     → 确认引用 Zhao 2019 BMJ、Zhang 2024 BMC
  → 系统评价的结论是否基于 FLAURA 等关键 RCT？
     → 确认：Zhao 2019 纳入 FLAURA，HR 0.44 (0.37-0.52)
  → 三层全通：指南 ↔ 系统评价 ↔ 原始 RCT
  → 证据链完整

第5轮 · 评价证据质量（Appraise）
  → 加载 evidence-appraisal skill（GRADE 框架）
  → 对每个结局逐跳评估：
      PFS：High（双盲 RCT + 窄 CI + 多重 NMA 验证，无降级因素）
      OS：Moderate（降 1 级：CI 触及 1.0，P=0.046 边界显著）
  → 讨论：对照组 40% 交叉至 osimertinib，OS 真实获益可能被低估

第6轮 · 写报告（Apply）
  → 加载 cat skill（Critically Appraised Topic 格式）
  → Clinical Bottom Line 放在最前面（不堆 PICO 表、不写检索策略）：
      「osimertinib 是 EGFR 突变晚期 NSCLC 的标准一线治疗。
      相比一代 TKI，PFS 从 10.2 月延长至 18.9 月
      （HR 0.46, 95%CI 0.37-0.57），证据等级 High。
      NCCN 指南为首选推荐（Category 1）。」
  → 展开 FLAURA 试验细节，每项引用在正文中解释，不做空洞的 [n]
  → 写 FLAURA2（联合化疗）和 MARIPOSA（竞争方案）的对比

第7轮 · 自审门控（Audit）
  → 加载 self-audit skill（5 项自审清单）
  → 逐一检查：
      ✅ 每条引用有 raw_search/ 归档——没有 "PMID: TBD"
      ✅ 效应量数字前后一致——HR 0.46 / 0.80 没有抄错
      ✅ GRADE 使用匹配证据强度——OS 不是 "证实" 而是 "显示获益"
      ✅ 没有编造的引用
  → 通过。bash cp drafts/ → research/。输出给用户。
```

**运行指标：**
- 总 10 轮，约 3 分钟
- 检索成果：3 篇指南 / 5 篇系统评价 / 2 项 RCT / 2 项序贯方案
- 归档：raw_search/ 中 18 个文件
- DeepSeek KV Cache 命中率：90-98%（系统提示词前缀稳定，动态内容以 user message 形式追加）
- 10 篇引用全部真实可查——无一条来自模型训练记忆

---

## 第 4 页：Skills 架构（核心）

**标题：** 8 个 Skills 组成完整 EBM 研究管线

**什么是 Skill：**
纯 Markdown 文件（YAML frontmatter + Markdown body）。放在 `skills/` 目录下即被自动发现。**不需要改一行 Python 代码。** 模型通过 `skill_use("skill-name")` 调用，系统返回完整 Markdown 正文作为 tool result 注入对话历史。

**为什么不用代码：**
- Skills 不进 system prompt → 不破坏 KV Cache 前缀
- 作为 tool result 进入对话历史 → DeepSeek 前缀 KV Cache 保持稳定
- 任何人都能新增 skill → 零代码门槛

**8 个 Skills 的完整图：**

```
                    ┌─────────────────────┐
                    │  task_router (未来)  │  ← 判断问题类型，选管线
                    └─────────┬───────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    指南速查路线          治疗对比路线          证据深研路线
          │                   │                   │
          │    ┌──────────────┼──────────────┐    │
          │    │              │              │    │
          ▼    ▼              ▼              ▼    ▼
    ┌─────────────────────────────────────────────────┐
    │              通用层（所有管线共享）               │
    ├─────────────────────────────────────────────────┤
    │ pico-formulation    检索前必加载                 │
    │ 将临床问题分解为 PICO 框架                       │
    │ 确定问题类型（therapy/diagnosis/prognosis/       │
    │ etiology）→ 确定最佳研究设计                     │
    │                                                 │
    │ retrieval-strategy  PICO 后、开始检索前必加载    │
    │ 按证据层级选工具：guideline→pubmed,              │
    │ SR→cochrane+pubmed, RCT→clinical_query=therapy   │
    │                                                 │
    │ evidence-appraisal  检索后、写结论前必加载        │
    │ 逐跳 GRADE 评级——不是单篇评估，是链中每跳独立打分 │
    │ 偏倚风险/不一致性/间接性/不精确性/发表偏倚       │
    │                                                 │
    │ self-audit          输出前必须加载（硬性门控）    │
    │ 5 项自审：引用真实 / 数字一致 / 结论匹配证据 /    │
    │ 断链标注 / 未核实内容标注                        │
    │                                                 │
    │ domain-sites        医学域名已自动注入            │
    │ 仅在需要额外领域时手动加载                       │
    └─────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌──────────┐    ┌──────────────────┐    ┌──────────────┐
    │   cat    │    │evidence-synthesis │    │  systematic- │
    │ 临床快评  │    │   证据综合报告     │    │    review    │
    │          │    │                  │    │  系统评价方法 │
    │ 推荐开头  │    │ IMRaD 结构       │    │              │
    │ 自然段落  │    │ GRADE 证据概览表  │    │ PRISMA 流程  │
    │ 引用展开  │    │ 完整证据链路      │    │ Meta 分析    │
    │ 1-2 页   │    │ Clinical Bottom   │    │ 发表级严谨性  │
    │ 床旁决策  │    │ Line              │    │              │
    └──────────┘    └──────────────────┘    └──────────────┘
```

**Skill 工作流示例（cat skill 的片段）：**
```markdown
---
name: cat
description: "**证据评估完成后、输出结论前必加载。**
              临床快评：推荐开头、自然段落、引用正文展开、不写检索策略。"
---

# Critically Appraised Topic (CAT) — 临床证据快评

## 核心原则
CAT 是写给**临床医生看**的，不是写给数据库看的。
**结论必须在最前面。** 临床医生可能只读前两段就做决策了。

## 输出格式
### 第一段：Clinical Bottom Line（放在最上面，不是最后面）
用 3-5 句自然段落直接回答 PICO 问题。不要用表格。

### 第二段：证据链路（一行）
ESC Ⅰ类推荐 [1] ← 3项SR [2-4] ← 6项RCT n=46,969 [5-10]。
链路完整，GRADE High。

### 第三段：关键发现（用段落，少用表）
选最重要的 1-3 项研究，每项 2-3 句写清设计、效应量+CI、质量问题。
```

**Skill 加载的 KV Cache 影响：**
- Skill 不进 system prompt → 随着用户对话以 user message 形式注入
- DeepSeek 前缀 KV Cache 在 12 轮对话中保持 90-98% 命中
- 每个 skill 加载产生 ~3,000-5,000 token 的开销（一次性）
- 后续轮次复用已加载的 skill（不需要重复加载）

---

## 第 5 页：工具矩阵——5 个 EBM 专用检索工具

**标题：** 不是 web_search 套壳——每个工具对应特定证据层级

| 工具 | 数据源 | 覆盖 | EBM 专用参数 | 证据层级 |
|------|--------|------|-------------|---------|
| pubmed_search | PubMed via NCBI E-utilities | 3,700 万引文 (MEDLINE + PMC) | article_type: systematic_review/rct/meta_analysis/guideline<br>clinical_query: therapy/diagnosis/prognosis/etiology<br>pmid: 精确查找 + grade_readiness | 全部层级 |
| cochrane_search | Cochrane Library + PubMed 回退 | Cochrane CDSR 系统评价数据库 | query | 系统评价 |
| clinical_trials | ClinicalTrials.gov API v2 | 全球临床试验注册 | condition, intervention, status, phase | 临床试验 |
| medrxiv_search | medRxiv API | 健康科学预印本 | query, category, date_from, date_to | 最新证据（未评议） |
| openalex_works | OpenAlex API | 2.7 亿论文 | indexed_in="pubmed", references 指纹 | 扩展检索/引用链 |

**pubmed_search 是核心工具——示例用法：**

```
# 搜索系统评价（最高层级检索）
pubmed_search(query="SGLT-2 inhibitor MACE", article_type="systematic_review")

# 搜索RCT + 临床治疗查询（PubMed 验证的检索策略）
pubmed_search(query="osimertinib EGFR NSCLC", article_type="rct", clinical_query="therapy")

# PMID 精确查找（返回完整元数据 + grade_readiness 分类）
pubmed_search(pmid="34101387")
→ 返回：标题、37 位作者、期刊、DOI、PMCID、摘要全文、MeSH 词、publication_type、
         grade_readiness: {status: "grade_ready", label: "可作为 GRADE 评估素材"}

# 批量 PMID
pubmed_search(pmids="34101387 37937763")
→ 返回每篇文献的 grade_readiness 分类
```

**技术实现要点：**
- 所有工具直连目标 API（requests.Session().trust_env = False），绕过代理问题
- PubMed 速率限制：无 key 3 次/秒，有免费 NCBI key 10 次/秒
- `ebm.py` 模块在 EBM 适配中新增 —— 只含真正调 API 的检索工具（不把 GRADE/PICO 做成 tool，归 skill 管）
- `arxiv_search` 和 `crossref_search` 已禁用（config.yaml disabled_tools）—— arXiv 偏物理/CS，Crossref 与 PubMed 重复

**工具描述采用英文（接近 OpenAI function schema 风格）：**
- pubmed_search: "Search PubMed biomedical literature. Filter by article_type to target evidence level."
- medrxiv_search: "...NOT peer-reviewed — check for subsequent journal publication before citing as strong evidence."

---

## 第 6 页：与通用 AI 的核心差异

**标题：** 为什么这不是 ChatGPT + 插件

| 维度 | 通用 AI（ChatGPT/DeepSeek Chat） | EBM Agent OS |
|------|----------------------------------|-------------|
| 引用来源 | 可能编造 PMID，来源不可查 | 每条引用对应 raw_search/ 中真实归档文件，完整审计追踪 |
| 检索逻辑 | 关键词搜索 → 网页摘要 | 证据金字塔：指南 → SR → RCT，自上而下逐层检索 |
| 证据分级 | 不分级——把病例报告和 RCT 等同 | GRADE：High/Moderate/Low/Very Low + Oxford CEBM 1a-5 |
| 结论可追溯 | 结论是黑箱——"三个来源支持" | 逐跳证据链——每层标注来源和 GRADE，断链处诚实标注 |
| 自审机制 | 无——输出即终稿 | self-audit：5 项自审清单，通过后才输出 |
| 输出格式 | 通用对话 | CAT 临床快评 / Evidence Synthesis 深度报告——按 AFP 临床综述标准写 |
| 模型记忆 vs 实际检索 | 依赖训练记忆（PMID 常编错，5/13 证实错误） | 禁止凭记忆输入 PMID——必须用实际检索结果 |
| 报告结构 | "值得注意的是""综上所述"——AI 套话 | 推荐开头 → 自然段落 → 引用正文展开 → 不写检索策略 |

**最核心的区别用一个场景说明：**

用户问："SGLT-2 抑制剂能降低 T2DM 患者的 MACE 吗？"

ChatGPT 可能回答：
"SGLT-2 抑制剂可能降低 MACE 风险，根据多项研究 [1,2,3]。建议咨询医生。" —— [1] 可能不存在。

我们的系统回答：
"SGLT-2 抑制剂可降低 T2DM 合并 ASCVD 患者的 MACE 风险约 14%（HR 0.86, 95%CI 0.74-0.99），
基于 EMPA-REG OUTCOME 试验（n=7,020, 双盲RCT）。该结论由 ESC 2023 Ⅰ 类 A 级推荐 [1]、
3 项系统评价 [2-4]、6 项 RCT [5-10] 支持。证据链完整，GRADE High。
每治疗 39 名患者 3 年可预防 1 例 MACE。
安全性：截肢风险需关注（canagliflozin HR 1.97），应优先使用 empagliflozin 或 dapagliflozin。"
—— [1]~[10] 全部可查、可追溯、有原始行踪。

---

## 第 7 页：技术架构

**标题：** AgentOS 内核 + EBM 业务层

```
┌─────────────────────────────────────────┐
│           CLI (cli.py)                  │  Rich TUI + prompt_toolkit
│         EBM Agent OS 命令行界面          │  /new /switch /sessions /interrupt
├─────────────────────────────────────────┤
│            AgentOS 组装层                │
│  Session · Config · SkillLoader         │
│  ToolRegistry · ContextCompiler         │
├─────────────────────────────────────────┤
│            Kernel (核心引擎)             │
│  AgentLoop (ReAct)                      │  模型调用 → 流式解析 → 工具执行 → 观察
│  SubAgent (spawn, 并行)                 │  独立会话、共享工作区、可中断
│  ResultFilter (已禁用——EBM 需原始结果)   │
├──────────────┬──────────────────────────┤
│   Memory     │      Storage             │
│ Context      │  SQLite (FTS5 + Embed)   │
│ Compiler     │  6 表 + 2 FTS5 虚拟表    │
│ Workspace    │  Session · Message       │
│ Retriever    │  Artifact · Todo · Remind │
└──────────────┴──────────────────────────┘
```

**关键技术决策：**

1. **ReAct 循环**：每轮 = 模型决策（thinking）→ 解析工具调用 → 并行执行工具 → 观察结果 → 下一轮。默认 64 轮上限，自动触发冷静提醒（第 8/15 轮），连续检索 9 轮未写 research_state 触发盲搜提示。

2. **KV Cache 保护**：系统提示词前缀编译后冻结。时间戳、domain_hint、skill 内容都以 user message 追加 → DeepSeek 前缀 Cache 稳定 90-98% 命中——12 轮对话中每次模型请求节省 ~15,000 token。

3. **Session = 独立工作区**：`data/sessions/{id}_{name}/` 下 uploads/（原始材料）、drafts/（草稿）、research/（已验证报告）、raw_search/（检索归档）、MEMORY.md（跨 session 记忆索引）。

4. **网络策略（仅 Jina 走代理，其余直连）**：学术工具（PubMed/OpenAlex/Cochrane/medRxiv）直连通过 trust_env=False，web_read 的 Jina 走代理（国内可用），Firecrawl/Trafilatura 为无代理回退方案，MinerU 直连 `trust_env=False`。

5. **Domain Hints 自动注入**：8 类医学/EBM 域名（medical, medical_cn, clinical_trials, biomedical, elite_multidisciplinary, ebm_chinese, gov_cn_health, academic）在会话启动时静态注入到 user message。不需要额外的模型调用来路由域名——相比原版每次对话调一次路由模型，节省 ~200 token/次。

6. **上下文截断保护**：file_read 内容展示从 3000 字提升到 12000 字；result_filter（LLM 摘要压缩）已禁用——EBM 需要保留完整的效应量和 CI 信息。

---

## 第 8 页：真实测试结果

**标题：** 我们用 3 条真实临床问题测试了系统

**测试 1（简单）：SGLT-2 抑制剂能否降低 T2DM 患者 MACE 风险？**
- 效果：15 轮完成，证据链完整（ESC 指南 → 4 篇 SR → 6 项 RCT）
- 问题：第 1 轮用记忆猜了 3 个错误 PMID，第 2 轮自行纠正
- 改进：加"禁止凭记忆输入 PMID"规则，后续测试完全避免

**测试 2（困难）：75 岁以上老年人，他汀一级预防能否降低全因死亡？**
- 效果：正确识别证据不足——USPSTF I 声明（证据不足），ALLHAT-LLT 趋势危害
- 亮点：诚实报告"链路多处断开"而非硬编结论
- 用时：~15 轮，构建了 5 层证据链路 + 断链标注

**测试 3（专业）：osimertinib 在 EGFR 突变 NSCLC 中的一线治疗证据**
- 效果：精准——10 轮完成 CAT 报告，10 篇引用全部真实（PMID 可通过 PubMed 验证）
- 亮点：自动检索 FLAURA2（联合化疗）和 MARIPOSA（竞争方案），给出了分层 CBL
- KV Cache：90-98% 命中率

**在 3 次测试中发现并修复的系统问题：**
1. 模型用记忆猜 PMID → 加"用 query + year + au 搜索，禁止凭记忆输入 PMID"
2. 引用没有展开（"[3-5]" 空洞）→ 加"每篇引用在正文中解释设计、n、效应量"
3. 报告全是表，不像人写的 → CAT skill 重写为推荐开头、自然段落、表只用于对比
4. 报告写得像填表（PICO 表→检索策略→RoB 表→GRADE 表→CBL 最后）→ CBL 移到最前面

---

## 第 9 页：当前状态与下一步规划

**标题：** 已完成 vs 讨论中

**已完成的完整功能：**
- ✅ 8 个 Skills，组成完整 EBM 5A 管线（Ask → Acquire → Appraise → Apply → Audit）
- ✅ 5 个 EBM 专用检索工具，覆盖 4 个数据源
- ✅ 3 次真实测试全部通过，PubMed 引用 100% 可查
- ✅ DeepSeek KV Cache 90%+ 命中率
- ✅ GitHub 公开，完整 README 含环境配置指南
- ✅ 代理策略优化——仅 Jina 走代理，其余直连
- ✅ 上下文截断保护——file_read 展示量提升 4 倍

**讨论中的下一步：**

1. **任务路由（task routing）**
   目前系统只有一条管线——不管用户问什么，都走 PICO→检索→评估→报告。
   讨论：加一个 task_router skill，识别"指南速查"vs"治疗对比"vs"多病共患"vs"证据深研"，分别走不同管线。

2. **输出模板设计（output templates）**
   每条管线配固定段落结构（类似论文 IMRaD），模型分段写作而非一次性生成整篇报告。
   讨论：不同报告类型的具体 section 结构有待专家参与设计。

3. **引用深度（citation depth）**
   目前每条引用标注 [n] 但不附带原文片段。
   讨论：利用现有 Embedding 系统做一个 cite_source 工具，根据 claim 在 raw_search/ 归档中检索匹配的原文段落并返回，实现"句句可溯源"。

4. **个性化患者管理（personalized patient management）**
   后续接入患者数据时，需要在每个推荐后追加一层判断："这个推荐是否适用于当前患者？"
   讨论：这是更大的架构变更，目前仅从需求层面识别。

---

## 第 10 页：总结

**标题：** EBM Agent OS — 为循证医学设计的 AI Agent

**我们做了什么：**
一个临床研究 AI Agent 系统，不是通用对话 AI。它按循证医学的方法论（证据金字塔 → GRADE 评级 → 证据链追溯 → 自审门控）自主检索和综合临床证据。

**和现有方案的关键区别：**
- 不是 ChatGPT —— 不靠记忆编造引用，每条结论有真实的 raw_search/ 审计轨迹
- 不是 PubMed 搜索 —— 不是返回论文列表，是"读完全文、逐层评估、合成一个可操作的 Clinical Bottom Line"
- 不只是关键词检索 —— 是按证据层级逐层排查：先指南 → 再系统评价 → 再 RCT

**可以汇报的技术亮点：**
- Skills 系统：纯 Markdown 工作流，零代码扩展，不进 system prompt 保护 KV Cache
- 完整的 EBM 管线：PICO → 检索 → GRADE → CAT/Synthesis → Self-Audit
- 真实测试验证：3 次完整跑通，PubMed 引用 100% 可查
- 证据链追溯：不是"三个来源支持"，是从指南向下逐跳追踪到原始 RCT 的完整链路
