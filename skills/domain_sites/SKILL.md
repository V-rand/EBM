---
name: domain-sites
description: "医学/EBM 域名已在会话启动时自动注入。仅在需要额外领域（如药理学、罕见病、特定监管机构）时手动加载。"
---

# 权威站点目录 — EBM 扩展

## 重要提示

**以下医学领域域名已在每次会话中自动注入，不需要手动调用：**
`medical` `medical_cn` `clinical_trials` `biomedical` `elite_multidisciplinary` `ebm_chinese` `gov_cn_health` `academic`

本 skill 仅在需要**超出自动注入范围**的域名时加载。

## 何时加载

当你需要以下领域的权威域名时：
- 特定国家监管机构（如 FDA 标签、EMA 审评报告）
- 罕见病数据库
- 特定专业学会指南（超出中华医学会范围的国际学会）
- 药品说明书官方来源
- 补充/替代医学

## EBM 扩展现有领域

`sites.yaml` 中包含但未自动注入的医学相关领域：

| 领域 key | 内容 |
|----------|------|
| `pharmacology` | FDA、NMPA、EMA、药品标签 |
| `biology` | 基因、蛋白、通路数据库 |
| `chemistry` | PubChem、药物化学 |
| `patents` | 药物专利 |
| `standards` | ISO、IEEE 医疗标准 |

加载方式：在 `web_search` 的 query 中拼入 domain_sites 返回的 site_operators。

## 使用

不传参数读取 `sites.yaml` 全部内容：
```
domain_sites() → 返回所有领域列表
```

按领域获取：
```
domain_sites(domain="pharmacology") → 返回 FDA/NMPA/EMA 等 site: 操作符
```

将返回的 site_operators 拼入 web_search query 即可锁定来源。
