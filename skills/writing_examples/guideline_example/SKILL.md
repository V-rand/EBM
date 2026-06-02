---
name: guideline-example
description: "需要评估或引用临床指南时加载。真实世界的指南推荐范例——看推荐如何嵌入证据、推荐强度如何标注、临床可操作性如何保证。用 web_read 看 CDC 和 NICE 的推荐页面。"
---

# 指南推荐写作范例——CDC MMWR + NICE

## 这是什么

临床指南推荐有独特的写作逻辑：推荐在前、证据在后、强度明确、临床可操作。CDC MMWR 和 NICE 代表了两种主流格式——美国式和英国式。

### 推荐范例

**CDC MMWR 临床指南推荐（美国格式）**
```
web_read(url="https://www.cdc.gov/mmwr/volumes/73/rr/rr7301a1.htm")
```
CDC 的推荐格式：编号推荐语句 + 证据类型（如"GRADE type 2"）+ 实施指导。免费、结构化、可操作性极强。

**NICE 指南推荐页面（英国格式）**
```
web_read(url="https://www.nice.org.uk/guidance/ng238")
```
NICE 格式：推荐列表在左侧导航栏，右侧展开全文。推荐用 "Offer..." / "Consider..." / "Do not offer..." 的动词力度区分推荐强度。

### 看什么

1. **推荐语句的主语是谁**——CDC 会用 "clinicians should..." 还是 "is recommended"？
2. **推荐强度的语言**——如何用自然语言区分强推荐 vs 弱推荐（不是靠 GRADE 符号）？
3. **每一条推荐后面跟什么**——是证据摘要？实施建议？还是直接下一条？
4. **推荐的粒度**——是笼统的"应使用他汀"还是具体的"对 40-75 岁、LDL-C ≥190 的患者启动高强度他汀"？
