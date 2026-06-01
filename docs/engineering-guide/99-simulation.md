好，我们真实模拟一遍。场景是：律师李四在 CLI 上第二次给 AgentOS 发消息，第一次聊过"帮我查一下这个案子的相关法条"。

---

进入 cli.py 主循环

CLI 在终端上打印了 prompt 符号，等待用户输入。李四敲了一行字："整理一下刚才查到的那几条法规的对比分析，写一份报告。"

CLI 收到输入，不是 / 开头的命令，是普通消息。调用了 `os.chat(session_id, message)`。这个方法是个异步生成器，返回一串事件。CLI 准备好了一个 `async for` 循环来消费这些事件。

---

AgentOS.chat() → AgentLoop.process()

进入 process，第一件事是上锁。AgentOS 每个 session 有一个 `asyncio.Lock`——保证李四如果同时发了多条消息，不会乱序处理。现在只有这一条，直接拿到锁。

---

Phase 0：初始化准备

调 `_get_or_init_session_context()`。去 SQLite 里找到李四的 session 记录——上次聊过，session 还在。从 `_session_contexts` 缓存里拿到上次编译好的 system prompt（编译时冻结的，没变）。

然后检查 session 有没有未完成的压缩——没有。加载历史消息：上次的"帮我查法条"、当时的 tool call、工具返回结果、AI 的回复。一共 8 条消息，加起来不到 5000 token。

把李四的新消息存进 SQLite messages 表，kind="chat"，role="user"。yield 一个 `context.compiled` 事件——CLI 收到后打印了一行"上下文已加载"。

清理上一轮的 subagent 临时目录。检查 uploads/ 目录有没有新文件——没有。

把李四的消息追加到 `messages` 列表里。调 `convert_tools_for_model()` 把 23 个工具的 schema 转成 OpenAI 格式。初始化循环变量：

- iteration = 0
- final_content = None
- forced_final_turn = False
- consecutive_tool_rounds = 0
- consecutive_blind_search_rounds = 0
- state = _LoopState(messages=messages)

进入 while 循环。

---

第一轮迭代（iteration = 1）

先把 state.transition 重置为 None。

**Step 1：检查中断信号**。`_interrupt_events` 字典里没有李四的 session，没中断请求。

**Step 2：_inject_turn_attachments**

检查 uploads/ 有什么新文件——没有。检查 interventions 表有没有 pending 的人工干预——没有。检查 `_pending_messages` 有没有缓存的注入消息——没有（李四是第一次发，没有 concurrent 消息）。估算当前 messages 的 token——大约 5500，远没到 600K 阈值，不用压缩。

**Step 3：请求模型**

yield `model.requested` 事件。CLI 打印"第 1 轮决策中"。

构建请求参数：messages（system prompt + 历史 + 当前消息）+ tools（23 个 schema）+ extra_body（reasoning_effort=high）。调 `_request_model_with_retry()`——里面用 OpenAI SDK 发 POST 请求到 `api.deepseek.com/v1/chat/completions`。

模型流式返回。`_parse_streaming_response` 逐 chunk 消费，三种 chunk 分别处理：

- 有 reasoning_content 字段 → yield `ThinkingStreamEvent`（CLI 打印灰色推理文字）
- 有 content 字段 → yield `ContentStreamEvent`（CLI 逐字打印回复）
- 有 tool_calls 字段 → 累加，等到流结束时拿到完整的 tool_calls 数组

流结束了。这次模型没有直接给答案，而是返回了三个 tool_calls：
1. `workspace_search(query="刚才查到的法规")`
2. `web_search(query="对比分析方法 法律 法规")`
3. `file_list(path="research/")`

yield `model.completed` 事件，payload 里带着 prompt_tokens=5800, completion_tokens=120, cache_hit_rate=0.97。CLI 打印了"模型完成(5800 tokens, 97% 缓存命中)"。

**Step 4：判断——有 tool_calls 吗？**有，三个。进入工具执行分支。

**Step 5：研究护栏检查**

`_research_search_guardrail()` 检查。workspace_search 和 web_search 都是 retrieval 工具，算搜索轮次。consecutive_blind_search_rounds 从 0 变成 1。还没到 9，不触发护栏。

**Step 6：持久化 tool call**

`_persist_assistant_tool_call()` 把模型返回的 tool_calls 写入 SQLite messages 表，kind="tool_call"。

**Step 7：执行工具**

三个工具，检查 concurrency_safe：

- workspace_search：标记了 concurrency_safe=False（当前不是）
- web_search：concurrency_safe=False
- file_list：concurrency_safe=True

不是全部 safe，走串行路径。

第一个：workspace_search(query="刚才查到的法规")。在 SQLite 的 chunks 表里做 FTS5 + embedding + RRF 混合检索。找到了上次 session 查到的 5 条法规。返回结果。yield `ToolResultEvent`。

第二个：web_search(query="对比分析方法 法律 法规")。调 Tavily API，返回几条关于法律对比分析的方法论文章。yield `ToolResultEvent`。

第三个：file_list(path="research/")。列出 research/ 目录下的文件。上次 session 写了一个 `research/laws.md`。yield `ToolResultEvent`。

检查有没有 todowrite 调用——没有。检查有没有 research_state 调用——没有。consecutive_tool_rounds 变成 1。

state.transition = "next_turn"。continue——回到 while 循环。

---

第二轮迭代（iteration = 2）

state.transition 重置为 None。

中断检查——没有。_inject_turn_attachments——没什么要注入的。token 估算——现在 messages 里多了 tool_calls 和 tool_results，大约 12000 token。远没到阈值。

调模型。这次模型看到了 workspace_search 回来的 5 条法规、web_search 回来的方法论、和 research/ 目录下的文件列表。

模型流式返回。这次没有 tool_calls，直接返回了纯文本——一段法规对比分析报告。

yield `ContentStreamEvent`（CLI 逐字打印报告）。

**Step 4：判断——有 tool_calls 吗？**没有。进入纯文本分支。

检查 pending_messages——李四没有 mid-turn 注入。output_text 不为空——不是空回复。

final_content = output_text。break——退出 while 循环。

---

Phase 4：结束

final_content 不为空。写入 SQLite assistant 消息。

yield `run.completed` 事件 + `ContentEvent`（CLI 打印完报告）。

检查 `_context_dirty_sessions`——没有工具修改了文件系统（workspace_search 和 web_search 都是只读的）。session context cache 不动，下次请求不用重新编译 system prompt。content_filter_quarantine 状态正常，是纯净的。

函数返回。async for 循环结束。CLI 重新打印 prompt 符号，等待下一次输入。

---

如果李四在模型执行到一半时按了 Ctrl+C

这时候事情会不一样。

李四看到模型在输出，"等一下，我不要对比分析了，帮我直接写起诉状。"

李四按下 Ctrl+C。CLI 的 keyboarInterrupt handler 触发，调用 `os.request_interrupt(session_id)`。这设置了 `_interrupt_events[session_id]` asyncio.Event。

AgentLoop 在下一轮 while 循环开始时检查中断信号——发现 `interrupt_event.is_set()`，clear 掉，yield `run.interrupted` 事件，break。CLI 打印"收到中断请求，正在停止"。

李四在终端上看到消息被中断了，可以重新输入。

---

整个过程的宏观视角

从李四的角度看，他就是在终端上打了一行字，等了几秒钟，看到了一份报告。

但从系统角度看，经过了：
1. SQLite 读 session + 历史 + 工具 schema
2. system prompt 编译（冻结的，直接取缓存）
3. 一次模型调用 → 三个工具执行
4. 第二次模型调用 → 最终回复
5. SQLite 写 assistant 消息
6. 整个流程用事件流式输出到 CLI

如果用 `run_events.jsonl` 回头看这轮对话，能看到的每一行日志事件：context.compiled → run.started → model.requested → thinking_stream（若干）→ content_stream（若干）→ model.completed → tool_call（workspace_search）→ tool_call（web_search）→ tool_call（file_list）→ tool_result（×3）→ model.requested → content_stream（若干）→ model.completed → run.completed → content。这和上面模拟的每一步是完全对应的。
