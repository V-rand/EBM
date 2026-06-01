# EBM Agent OS — 循证医学深度研究系统

基于 Agent OS 内核的循证医学 AI 研究助手。自动构建 PICO 框架、按证据层级检索（指南→系统评价→RCT）、逐跳 GRADE 评级、输出 Clinical Bottom Line。

## 环境准备

### 你需要什么

| 项目 | 是否必需 | 说明 |
|------|---------|------|
| Python 3.11+ | ✅ 必需 | `python --version` 确认。没有的话 [python.org](https://python.org) 下载 |
| Git | ✅ 必需 | `git --version` 确认 |
| uv（包管理器） | ✅ 必需 | 安装：`curl -LsSf https://astral.sh/uv/install.sh \| sh`（Linux/Mac）或 `pip install uv` |
| DeepSeek API Key | ✅ 必需 | [platform.deepseek.com](https://platform.deepseek.com) 注册，在「API Keys」页面创建，新用户有免费额度 |
| NCBI API Key | 可选 | [NCBI 注册](https://www.ncbi.nlm.nih.gov/account/)，填后 PubMed 从 3次/秒 → 10次/秒 |
| Tavily API Key | 可选 | [tavily.com](https://tavily.com) 注册，提升网页搜索质量。不填也能用（走 Serper 回退） |
| Jina API Key | 可选 | [jina.ai](https://jina.ai) 注册，用于网页全文读取。不填也能用（走 Firecrawl/Trafilatura 回退） |
| MinerU Token | 可选 | PDF/Office 文档解析。不填则用本地 pymupdf4llm 解析 |

### 安装步骤

```bash
# 1. 克隆项目
git clone git@github.com:V-rand/EBM.git
cd EBM

# 2. 安装依赖（uv 自动创建虚拟环境）
uv sync

# 3. 配置 API Key
cp .env.example .env
```

编辑 `.env`，填入 DeepSeek API Key（其他可选）：
```bash
# 必需
DEEPSEEK_API_KEY=sk-your-deepseek-key

# 可选：提升 PubMed 速率
NCBI_API_KEY=your-ncbi-key

# 可选：提升网页搜索质量
TAVILY_API_KEY=tvly-your-key
JINA_API_KEY=jina-your-key
```

### 验证安装

```bash
# 启动 CLI
uv run python cli.py
```

看到 `EBM Agent OS — 循证医学深度研究助手` 标题和 `EBM 未选择>` 提示符即为成功。

输入 `SGLT-2抑制剂在T2DM中能否降低MACE风险？` 测试是否正常回答问题。

## CLI 操作

进入后看到 `EBM 未选择>` 提示符。**不需要先 `/new`——直接输入问题就会自动创建工作区**。

| 命令 | 作用 |
|------|------|
| `/sessions` | 列出所有工作区 |
| `/switch <编号>` | 切换工作区（不同研究主题分开） |
| `/new <名称>` | 手动创建命名工作区 |
| `/close` | 关闭当前工作区 |
| `/delete` | 删除当前工作区及数据 |
| `/status` | 查看当前运行状态 |
| `/interrupt` | 中断正在运行的任务 |
| `/help` | 完整命令列表 |

输入 `exit` 或 Ctrl+C 退出。

## 自定义 Skill

Skills 是纯 Markdown 文件，放在 `skills/` 下即可被自动发现，**不需要改任何代码**。

### 创建一个 Skill
```bash
mkdir -p skills/my_skill
```

写 `skills/my_skill/SKILL.md`：
```markdown
---
name: my-skill
description: 简短描述——模型看到这个来决定是否加载
---

# 你的 Skill 标题

这里写 skill 内容。可以是方法论指导、领域知识、报告模板等。
模型通过 `skill_use("my-skill")` 加载后，会读到这里的全部内容。
```

重启 CLI 生效。Skill 还支持附件：
```
skills/my_skill/
├── SKILL.md          # 必需
├── references/       # 可选：参考资料
├── templates/        # 可选：模板文件
└── assets/           # 可选：其他资源
```

### 放在项目外
在 `config.yaml` 中：
```yaml
extra_skill_dirs:
  - /path/to/your/skills
```

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

## 注意

- 这是一个**研究工具**，不是医生。个人健康问题会做轻量分析但不启动完整研究管线。
- PubMed 有速率限制。如果频繁 429 错误，去 NCBI 注册免费 API key 填入 `.env`。
- 完整研究（深度报告）约 3-5 分钟，快速 CAT 约 1-2 分钟。
- 报告写入 `data/sessions/<id>/research/`，检索归档在 `raw_search/`。

## 技术栈

Python 3.11+ · asyncio · DeepSeek API · SQLite (FTS5) · uv 包管理
