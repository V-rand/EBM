# SubAgent 架构

`agent_os/kernel/sub_agent.py` — 595 行。

## 设计目标

- 隔离执行：子 agent 有自己的 session，不影响父 session 的上下文
- 共享工作区：子 agent 可以读写父 session 的文件
- 可观察：父 agent 可以查看子 agent 的进展
- 可控制：父 agent 可以发送消息或终止子 agent
- 安全：子 agent 不能创建子 agent（禁止嵌套）

## 架构

```
Parent Session
    │
    ├── spawn(task_description, allowed_tools, ...)
    │     │
    │     ├── Child Session
    │     │   ├── id = uuid
    │     │   ├── parent_session_id = parent.id
    │     │   ├── work_dir = parent.work_dir（共享！）
    │     │   ├── 独立消息历史（不写入父 messages 表）
    │     │   ├── 工具集（可限制）
    │     │   └── 最大迭代（sub_agent_max_iterations, 默认 32）
    │     │
    │     └── 异步执行 Task
    │           └── AgentLoop (子)
    │                 └── 自己的 ReAct 循环
    │
    ├── send_message(child_id, message)
    │     └── 在子 agent 下一轮迭代前注入
    │
    └── task_stop(child_id)
          └── 触发子 agent 中断
```

## 创建流程

```python
class SubAgent:
    async def run(self, task_description: str) -> dict[str, Any]:
        # 1. 创建子 session
        child = await self.session_manager.create(
            name=f"sub_{slugify(task_description)[:20]}",
            parent_session_id=self.parent_session_id,
        )
        
        # 2. 注入任务说明
        await self.session_manager.add_message(
            child.id, role="user", content=task_description
        )
        
        # 3. 构建子 agent 上下文
        system_prompt = self._build_sub_agent_prompt(child, task_description)
        
        # 4. 异步执行 ReAct 循环
        task = asyncio.create_task(
            self._run_loop(child, system_prompt)
        )
        
        # 5. 注册子 agent
        self._active_children[child.id] = {
            "task": task,
            "session": child,
            "status": "running",
        }
        
        return child.id
```

### 子 Agent System Prompt

构建方式与父 agent 不同：

```python
def _build_sub_agent_prompt(self, child, task_description):
    # 1. agent_system.txt（同一份核心提示词）
    # 2. 父 session 的 SOUL.md / AGENT.md / MEMORY.md
    # 3. 任务说明包裹在 <task_notification> 中
    # 4. 工具说明（可用工具列表 + 用法）
    # 5. 输出格式要求（必须以 <task_result> 结尾）
    return prompt
```

## 通信协议

### 子 Agent → 父 Agent

子 agent 完成时返回 `<task_result>` XML：

```xml
<task_result>
<status>completed</status>
<summary>研究了 A 公司的股权结构，发现实际控制人是 B</summary>
<key_findings>
- 实际控制人：B（持股 51%）
- 关联公司：C 有限公司
</key_findings>
<artifacts>
- research/ownership_analysis.md
</artifacts>
</task_result>
```

### 父 Agent → 子 Agent

通过 `send_message` 工具，在当前迭代结束后注入：

```python
# 父 agent 调用
send_message(child_id="abc", message="重点关注 B 公司的对外投资")
```

消息存储在子 session 的 messages 表中，在下一轮工具执行前注入。

### 状态追踪

子 agent 状态写入 JSONL 文件：

```
data/sessions/{parent_id}_name/raw_search/subagents/{child_id}.jsonl

{"type": "status", "phase": "running", "iteration": 3, "tool": "web_search", "timestamp": "..."}
{"type": "status", "phase": "completed", "iteration": 12, "summary": "...", "timestamp": "..."}
```

父 agent 可以通过 `file_read` 读取此文件获取子 agent 进展。

## 限制

### 禁止嵌套

```python
# SubAgent 的 allowed_tools 默认排除 spawn
_default_subagent_allowed_tools = [
    "file_read", "file_write", "file_list",
    "web_search", "web_read",
    "research_state", "todowrite",
]
```

### 工具限制

- 默认只有文件 + 检索工具
- 可通过 `allowed_tools` 参数扩展
- 不能调用 `spawn`、`task_stop`、`send_message`（不安全）

### 并发限制

- 当前无硬限制（不限制同时运行的子 agent 数量）
- 但每个子 agent 占用一个完整的 AgentLoop 实例
- 太多子 agent 可能导致 API 限流

## 结果处理

### 父 Agent 的工作流

```python
# 父 agent 调用 spawn 后典型工作流:
1. result = spawn("研究 A 公司的股权结构")
2. task_id = result["task_id"]
3. # 可以继续做其他工作
4. research_state(content="等待子 agent 完成...")
5. # 子 agent 完成后，读取 work_dir 中的文件
6. findings = file_read("research/ownership_analysis.md")
7. # 审核结果，决定是否采用
```

### 结果不写入父 session 的 messages

子 agent 的所有消息（包括 tool_call、tool_result）只写入子 session 的 messages 表。父 session 只看到 `spawn` 工具返回的 task_id。

这是父 session 上下文不被污染的关键设计。

## 对比：SubAgent vs 直接工具调用

| 场景 | SubAgent | 直接工具调用 |
|------|----------|-------------|
| 独立的子任务 | ✓ 合适 | ✗ 上下文污染 |
| 简单检索 | ✗ 过度工程 | ✓ 直接 |
| 需要隔离的敏感操作 | ✓ 安全 | ✗ 可能影响上下文 |
| 长耗时任务 | ✓ 异步 | ✗ 阻塞 |
| 需要与主任务交互 | ✓ send_message | ✗ |
