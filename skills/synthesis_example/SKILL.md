---
name: synthesis-example
description: "写 Evidence Synthesis 深度报告之前必加载。真实世界的证据综合范例——WHO 指南 GRADE 证据概览。用 web_read 打开看一遍 GRADE SoF 表和证据到推荐框架怎么写。"
---

# Evidence Synthesis 写作范例——WHO 指南 GRADE 证据概览

## 这是什么

WHO 指南（通过 NCBI Bookshelf 免费公开）是证据综合的黄金标准——完整的 GRADE Summary of Findings 表、证据到推荐（EtD）框架、分层的推荐强度。适合作为 evidence-synthesis 写作参考。

## 在写 Evidence Synthesis 之前

用 `web_read` 打开以下 1 篇，重点看它的 SoF 表和推荐是怎么连接的：

### 推荐范例

**WHO 贫血血红蛋白阈值指南（2024）——含完整 GRADE SoF 表**
```
web_read(url="https://www.ncbi.nlm.nih.gov/books/NBK602197/")
```
这是一份 WHO 指南的 GRADE 证据概览附件。核心看点：GRADE 表如何呈现每个结局的偏倚风险/不一致性/间接性/不精确性/发表偏倚评估，以及这些评估如何汇聚成一条临床推荐。

### 看什么

打开页面后，只看这几样东西：
1. **SoF 表的结构**——每个结局一行，GRADE 维度为列。表后有没有文字解释为什么降级？
2. **推荐怎么从证据中推导出来**——是"因为 GRADE High 所以 强推荐"还是更微妙的逻辑？
3. **不确定性怎么表达**——当证据等级低时，推荐语言如何调整？
4. **读者能根据这张表做出临床决策吗**——还是需要回到正文才能理解？

### 看完后写

- 写你自己的 SoF 表——每个关键结局一行，5 个降级维度 + 效应量 + GRADE 最终评级
- 写"从证据到推荐"——一段文字解释为什么这个证据等级导致这个推荐强度
- 不要抄范例的结构——你的报告不需要和 WHO 指南一样长。抓核心：SoF 表 + 证据逻辑链
