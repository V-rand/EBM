# EBM Agent OS — 循证医学深度研究系统

基于 Agent OS 内核的循证医学 AI 研究助手。自动构建 PICO 框架、按证据层级检索（指南→系统评价→RCT）、逐跳 GRADE 评级、输出 Clinical Bottom Line。

## 快速开始

### 1. 环境要求
- Python 3.11+
- Git
- DeepSeek API Key（[platform.deepseek.com](https://platform.deepseek.com) 注册即送额度）

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
```
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
```

可选：申请 [NCBI API Key](https://www.ncbi.nlm.nih.gov/account/) 填入 `NCBI_API_KEY=xxx`，提升 PubMed 速率限制（无 key 时 3 次/秒，有 key 时 10 次/秒）。

### 4. 启动
```bash
uv run python cli.py
```

## CLI 操作

进入后看到的提示符是 `EBM>`。常用命令：

| 命令 | 作用 |
|------|------|
| `/new` | 创建新的研究工作区 |
| `/sessions` | 列出所有工作区 |
| `/use <编号>` | 切换到指定工作区 |
| `/close` | 关闭当前工作区 |
| `/delete` | 删除当前工作区 |
| `/status` | 查看当前运行状态 |
| `/interrupt` | 中断正在运行的任务 |
| `/help` | 查看完整命令列表 |

**直接输入自然语言即可开始研究。** 系统会自动判断问题类型、加载技能、检索证据、输出结论。

输入 `exit` 或 Ctrl+C 退出。

## 它是什么

EBM Agent OS 是一个**自主研究 Agent**，不是聊天机器人：

1. **构建 PICO** — 把临床问题分解为患者/干预/对照/结局
2. **自上而下检索** — 先找指南和系统评价，再验证底层 RCT
3. **逐跳 GRADE 评级** — 证据链路中每一层独立评估质量
4. **构建证据链路** — 每条结论标注「指南←SR←RCT」的完整追溯路径
5. **输出 Clinical Bottom Line** — 临床医生可直接用的操作结论

与 ChatGPT 的关键区别：
- 不靠训练记忆编造引用——每条引用对应本次会话实际检索到的来源
- 证据链可追溯——你知道结论是从哪篇指南、哪项 RCT 来的
- 断链诚实标注——找不到证据就说找不到，不硬编

## 工具体系

| 工具 | 用途 |
|------|------|
| `pubmed_search` | PubMed 生物医学文献，支持 EBM 过滤（article_type / clinical_query） |
| `cochrane_search` | Cochrane 系统评价 |
| `clinical_trials` | ClinicalTrials.gov 临床试验注册 |
| `medrxiv_search` | medRxiv 预印本（最新研究，未经同行评议） |
| `openalex_works` | 扩展学术检索 / 引用链追踪 |

## 技能管线

系统有 8 个技能，模型根据任务自动加载：

| 技能 | 触发时机 | 作用 |
|------|---------|------|
| `pico-formulation` | 检索前 | 构建 PICO 框架，确定最佳研究设计 |
| `retrieval_strategy` | PICO 后 | 规划检索策略，按证据层级选工具 |
| `evidence-appraisal` | 检索后 | GRADE 逐跳评估证据质量 |
| `cat` | 快速决策 | Critically Appraised Topic + Clinical Bottom Line |
| `evidence-synthesis` | 深度报告 | IMRaD 报告 + GRADE 证据概览表 + 证据链路 |
| `systematic-review` | 系统评价 | PRISMA 标准全流程 |
| `self-audit` | 输出前 | 自审引用真实性 / 数字一致性 / 结论强度 |
| `domain_sites` | 额外领域 | 补充特定领域权威网站（医学域名已自动注入） |

## 评估系统表现

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

## 注意

- 这是一个**研究工具**，不是医生。个人健康问题会做轻量分析但不启动完整研究管线。
- PubMed 有速率限制。如果频繁 429 错误，去 NCBI 注册免费 API key 填入 `.env`。
- 完整研究（深度报告）约 3-5 分钟，快速 CAT 约 1-2 分钟。
- 报告写入 `data/sessions/<id>/research/`，检索归档在 `raw_search/`。

## 技术栈

Python 3.11+ · asyncio · DeepSeek API · SQLite (FTS5) · uv 包管理
