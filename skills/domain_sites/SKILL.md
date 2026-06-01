---
name: domain-sites
description: 'Use when the research domain is known and authoritative source domains would materially improve web_search. Provides site operator patterns for web_search. Skip for quick open discovery, simple lookups, or when structured tools are better.'
---

# 权威站点目录

当领域明确且权威来源可预测时，在 `web_search` 之前调用 `domain_sites(domain)` 来获取 `site_operators`。这是一个精确工具，不是每次搜索的必需步骤。

## 核心规则

**已知领域 + 需要精确 → `domain_sites(domain)` → 将 `site_operators` 拼入 query 的 `site:` 操作符。**

对于多领域问题，每个重要领域调用一次，并组合 site_operators 列表。对于探索性发现，先从高信息熵查询开始，在来源类别出现后再添加域名锁定。

## 可用领域

### 法律·司法（按场景拆分）
`legal_cn_judicial` — 法院裁判、检察、公安（判决/执行/失信/检察）
`legal_cn_legislative` — 法律法规、全国人大、国务院行政法规
`legal_cn_business` — 企业信用、市场监管、金融证券、税务、知识产权
`legal_cn_labor` — 劳动社保、土地房产、婚姻继承、退役军人、公务员
`legal_cn_professional` — 律师、公证、仲裁、法律数据库、法学会
`legal_cn_admin` — 司法部、信访、档案、审计、应急管理
`legal_cn_regulatory` — 教育、环保、出入境、网络数据、新闻出版、广电、港澳台、外汇、宗教
`legal_en` — 英美法系
`legal_historical` — 历史法律

### 政府数据（按职能拆分）
`gov_cn_economic` — 经济统计、财政、商务、海关、发改、市场监管、税务
`gov_cn_health` — 卫生健康、医保、药监、中医药
`gov_cn_science` — 工信、科技、自然科学基金
`gov_cn_infra` — 交通、民航、铁路、邮政、能源、水利
`gov_cn_rural` — 农业农村、林草
`gov_cn_culture` — 文旅、文物、民族、体育
`government_en` — 英美政府开放数据

### 医疗·生物医药
`medical` — 国际医学：WHO、NIH、PubMed、FDA、Lancet、NEJM、BMJ、UpToDate
`medical_cn` — 中国临床：卫健委、医保局、药监局、医师协会、医脉通
`biomedical` — 生物医学科研：NCBI、UniProt、临床试验注册、基金委、中科院

### 计算机·AI
`cs_conferences` — CCF、人工智能学会、自动化学会、顶会、知网

### 金融
`finance` — 国际金融：IMF、WorldBank、Bloomberg
`finance_cn` — 中国金融：央行、证监会、交易所、外汇、债券

### 自然科学
`biology` `materials` `chemistry` `environment` `mathematics` `physics`

### 通用
`elite_multidisciplinary` `academic` `patents` `standards` `film_media` `geography` `historical` `encyclopedia` `common_knowledge`

## 多领域配方

| 问题类型 | 调用这些 |
|---|---|
| 关于某个基因的生物学论文 | `domain_sites("elite_multidisciplinary")` + `domain_sites("biology")` |
| CS 会议论文 | `domain_sites("cs_conferences")`（如果是顶级的则 + `domain_sites("elite_multidisciplinary")`） |
| 材料属性查找 | `domain_sites("materials")` + `domain_sites("elite_multidisciplinary")` |
| 关于环境的中国法律 | `domain_sites("legal_cn")` + `domain_sites("environment")` |
| 谁发明了 X，Y 年 | `domain_sites("common_knowledge")` |
| 电影演员阵容和上映年份 | `domain_sites("film_media")` + `domain_sites("common_knowledge")` |

## 使用模式

```
# 单领域：
sites = domain_sites(domain="legal_cn")
# 将 site_operators 拼入 query: web_search(query="... " + " OR ".join(sites.site_operators))

# 多领域：
elite = domain_sites(domain="elite_multidisciplinary")
field = domain_sites(domain="biology")
# 合并 site_operators: all_ops = elite.site_operators + field.site_operators
# web_search(query="CRISPR gene editing mechanism " + " OR ".join(all_ops))
```
