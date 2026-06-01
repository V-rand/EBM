# 关键设计决策

记录开发过程中几个重要的取舍——不是标准答案，只是在当时约束下认为最合理的选择。

## 1. 通用 AgentOS，不是法律 Workflow 引擎

**选了什么**：构建通用的 Agent 操作系统，法律场景只是默认入口。

**没选什么**：为法律场景定制一套 workflow 引擎。

**为什么**：法律场景的需求变化太快。今天需要法规检索，明天需要案例对比，后天需要证据分析。固定 workflow 每次都要改代码，用户（律师）等不起。通用架构 + Skills（纯 Markdown 可配）的组合让非技术用户也能定制行为。

**代价**：学习曲线比专用引擎高一些。第一次用的人需要理解 Session、Tool、Skill 这些概念。

## 2. Session 完全隔离

**选了什么**：Session 之间不共享任何状态，通过 work_dir 文件间接协作。

**没选什么**：全局记忆池，按权限过滤。

**为什么**：法律案件有保密要求——案 A 的律师不应该看到案 B 的信息。完全隔离是最简单的安全模型。压缩链中的父子 session 共享 work_dir，这提供了足够的协作能力（子 session 能读到父 session 写入的所有文件）。

**代价**：不能直接跨 session 共享"经验"。如果要让系统从历史 session 中学习，需要额外的机制（当前通过 MEMORY.md 手动管理）。

## 3. KV cache 保护是第一优先级

**选了什么**：system prompt 编译后冻结，动态内容追加在尾部，tool 参数排序序列化。

**没选什么**：每次请求动态组装 system prompt。

**为什么**：DeepSeek 的 KV cache 价格差异太大了——命中 0.02 元/M tokens，未命中 1 元/M tokens，差 50 倍。对于长期运行的 session（可能持续数天），cache 命中率直接决定运营成本。冻结 prefix 是最有效的保命中策略。

**代价**：不能动态修改 system prompt 的内容。如果 skill 变了，需要显式调用 cleanup_session 让缓存失效。在牺牲灵活性的同时换来了可预测的成本。

## 4. SQLite 单文件，不带向量索引

**选了什么**：SQLite + FTS5，embedding 以 JSON 存，查询时全表遍历。

**没选什么**：PostgreSQL + pgvector，或者其他向量数据库。

**为什么**：零运维。不需要部署数据库服务。数据文件可以带着 session 一起打包和迁移。对于单用户或小团队的使用场景（法律案件通常如此），SQLite 完全够用。

**代价**：没有原生向量索引，10K+ chunks 时性能下降。embedding 存储为 JSON 字符串，查询效率较低。但当前场景（单 session <5K chunks）可接受。

## 5. 工具注册制 + contextvars 注入

**选了什么**：工具通过 ToolRegistry 注册，session 上下文通过 contextvars 注入，基础设施通过 set_tool_deps() 一次性注入。

**没选什么**：工具作为类继承基类，或者每个工具自己构造依赖。

**为什么**：函数式 handler 比类更简单，更容易测试。contextvars 让 handler 不需要显式传 session 参数。基础设施一次性注入避免了每个工具都去 new 一个 retriever 或 workspace_memory。

**代价**：contextvars 在异步代码中需要注意传播（只能用在 async function 内部）。新开发者可能不熟悉 contextvars 这种隐式传参模式。

## 6. 双事件系统

**选了什么**：内部通信用 EventBus（pub/sub），用户面向输出用 AsyncGenerator（TypedDict）。

**没选什么**：统一事件流。

**为什么**：两者的消费者不同。EventBus 是给系统组件用的——scheduler 触发提醒后通知其他组件，不需要顺序保证。AsyncGenerator 是给用户界面用的——需要顺序消费，一次 yield 一个事件给终端渲染。

**代价**：两个事件系统的类型定义分开维护。EventBus 目前不持久化（已知局限）。

## 7. Skills 是纯 Markdown，不包含代码

**选了什么**：Skill 定义在 Markdown 文件中，Python 代码里没有对应的逻辑。

**没选什么**：Skills 作为 Python 模块，可包含可执行逻辑。

**为什么**：非技术用户（律师、研究员）可以编辑和创建 Skills。提示词工程独立于代码开发。KV cache 友好——name+description 放在 system prompt，完整内容通过 tool result 按需加载。

**代价**：Skills 不能执行代码、不能调 API。它们是指令性的——依赖 Agent 理解并遵循。

## 8. 外部检索结果通过 LLM 压缩

**选了什么**：外部检索工具的输出通过 ResultFilterAgent（用 LLM 压缩）再注入上下文。

**没选什么**：原始结果直接注入。

**为什么**：搜索结果的原文经常超过 50K 字符。全量注入会快速膨胀上下文，触发压缩。LLM 压缩比简单截断保留更多关键信息。原始结果归档到 raw_search/，需要时可通过 file_read 读全文。

**代价**：每次检索多一次 LLM 调用（增加 1-3 秒延迟）。压缩质量依赖压缩模型的能力。

## 9. 提示词模板化到 .txt 文件

**选了什么**：所有提示词放在 agent_os/prompts/*.txt 中。

**没选什么**：硬编码为 Python 常量字符串。

**为什么**：调提示词不需要改代码。非开发者也能编辑。未来可以做多版本 A/B 测试。

**代价**：不支持热加载（改完需要重启）。.txt 文件中不能包含 Python 逻辑。

## 10. 压缩 + Fork，不是滑动窗口

**选了什么**：上下文超阈值时 fork 出一个新 session，注入摘要，父 session 标记 compressed。

**没选什么**：滑动窗口（丢弃最早的消息）。

**为什么**：完整历史保留在 SQLite 中（审计需要）。LLM 生成的摘要保留了因果推理链（"做了什么→发现了什么→因此做了什么"）。共享 work_dir 确保所有文件在压缩后仍然可见。

**代价**：Session ID 会变化（对外接口需要感知）。压缩后需要重新加载 skills（cleanup_session）。
