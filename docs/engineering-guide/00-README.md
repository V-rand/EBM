# AgentOS 工程文档

这个目录是一份围绕项目源码展开的深度工程笔记，目的是把系统设计的前因后果讲清楚。

## 从哪里开始看

如果你是第一次接触这个系统，建议按这个顺序读：

**第一轮：建立整体认知**
1. [架构总览](01-architecture-overview.md) — 先看系统长什么样，模块怎么分，数据怎么流
2. [核心概念](02-core-concepts.md) — Session 是什么，Event 系统为什么有两个，Tool 和 Skill 的区别
3. [配置参考](10-configuration-guide.md) — config.yaml 和 .env 怎么配

**第二轮：深入关键设计**
4. [ReAct 循环详解](03-agent-loop-deep-dive.md) — 最核心的循环，上下文压缩、KV cache 保护
5. [提示词设计](13-prompt-engineering.md) — 这个系统的灵魂，agent_system.txt 为什么那么写
6. [Skill 提示词模式](13b-prompt-skills-design.md) — 零代码工作流怎么写才有用

**第三轮：理解扩展性和边界**
7. [扩展系统架构](14-development-guide.md) — 怎么加 Tools、Skills、Plugins
8. [事件系统](09-event-system.md) — 为什么要有两个事件系统
9. [设计决策](16-design-decisions.md) — 关键取舍和背后的理由

## 文档清单

| # | 文档 | 一句话 |
|---|------|--------|
| 01 | 架构总览 | 系统长什么样，模块怎么分 |
| 02 | 核心概念 | Session / Event / Tool / Skill 的定义和关系 |
| 03 | ReAct 循环详解 | 上下文怎么编译、怎么压缩、KV cache 怎么保护 |
| 04 | Session 生命周期 | 创建、fork、压缩、删除的全过程 |
| 05 | 工具系统 | ToolRegistry 怎么工作，23+ 工具怎么分类 |
| 05b | 网页工具设计分析 | web_search 和 web_read 的设计思路 |
| 05c | 学术检索工具设计 | 6 个学术工具为什么分开，怎么协作 |
| 05d | 文件系统工具设计 | 路径沙箱、edit 双模式、文档解析管道 |
| 06 | 记忆与检索 | FTS5 + Embedding + RRF 混合检索 |
| 07 | 存储层 | SQLite 6 张表的设计，FTS5，WAL |
| 08 | Skills 系统 | 零代码工作流怎么发现和加载 |
| 09 | 事件系统 | EventBus 和 AsyncGenerator 双轨设计 |
| 10 | 配置参考 | config.yaml + .env 完整说明 |
| 11 | SubAgent | 子 Agent 怎么隔离、通信、限制 |
| 12 | 调度与中断 | 定时提醒、飞书通知、运行时中断 |
| 13 | 提示词设计 | agent_system.txt 逐节解析，设计哲学 |
| 13b | Skill 提示词模式 | 每个内置 skill 的状态机分析 |
| 14 | 扩展架构 | Tools/Skills/Plugins 三个扩展维度的设计 |
| 15 | 运营架构 | 部署结构、数据流、可观测性 |
| 16 | 设计决策 | 10 个关键取舍和理由 |
| 17 | 架构局限 | 当前已知的权衡和边界 |

## 为什么这样组织

这个文档集的定位不是 API 文档（代码就在那里），也不是教程，而是**工程设计笔记**。每篇文章试图回答三个问题：

1. 这个模块为什么存在，解决什么问题
2. 它的核心抽象是什么，为什么这么设计
3. 有什么边界和已知局限

所有分析都基于实际源码（标注了文件路径和行号），不是空中楼阁。
