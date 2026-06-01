# Research Strategy Architecture Redesign 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法跟踪进度。不要把此计划理解成继续加 prompt 规则；目标是重构模型的外显策略层。

**目标：** 把当前 deep research 从“线性状态机 + prompt 约束 + 搜索 guardrail”升级为“显式问题图 + 路径选择 + 工具动作模板 + 证据/假设分离”的研究策略架构。

**架构：** Kernel 保持通用；新增能力放在 `research_state` 工具、skills 和少量工具返回 hint 中。核心不是硬挡 `web_search`，而是在检索前后给模型一个轻量、可见、可复用的策略工作台：先画问题链条，比较正向/反向/锚点路径，选择最窄节点，再执行工具动作模板。状态工具只做 advisory 和记录，terminal 状态才硬停。

**技术栈：** Python 3.11+，AgentOS tools/skills，pytest，Markdown skills。

---

## 设计判断

当前小修小补失败的原因不是某条 prompt 不够强，而是策略架构有错位：

- `research_state` 更像线性流程控制器，不像研究策略工作台。
- `known_facts` 和 `reasoning_paths` 混在一起，模型容易把未验证假设写成事实。
- 工具选择靠 prompt 提醒，模型在压力下仍会选择低摩擦的 `web_search`。
- guardrail 一旦加强，又会回到“工具被挡、模型死循环”的老问题。
- 对链式谜题，系统没有要求模型比较路径方向：正向、反向、从最窄节点切入。

新的方向：

1. 不再新增强制检索前硬门。
2. 不再试图控制 hidden thinking。
3. 不再要求模型先完美推理再搜索。
4. 改为提供显式、短小、可执行的策略结构，让模型每轮能“看见自己正在走哪条路”。

---

## 文件结构

- 修改：`agent_os/tools/research.py`
  - 新增 `strategy_frame` / `path_choice` / `claim_inventory` 操作。
  - 在 public state 中区分 `verified_facts`、`hypotheses`、`chosen_path`、`rejected_paths`。
  - `inventory_known_facts` 保持兼容，但返回提示，建议迁移到 `claim_inventory`。

- 修改：`agent_os/tools/descriptions/research_state.txt`
  - 用例子描述新操作，而不是长规则。

- 修改：`skills/short_answer_research/SKILL.md`
  - 将短答案协议重心从线性 gate 改成“问题图 + 路径选择 + 候选验证”。
  - 增加链式问题模板：broad person → award → later work → cited specialist → study → society meeting 这类题必须比较路径方向。

- 修改：`skills/retrieval_strategy/SKILL.md`
  - 补充“先选节点，再选工具”的 action traces。
  - 明确 `web_search` 不是禁用对象，而是路径中的一种动作。

- 修改：`agent_os/prompts/agent_system.txt`
  - 收敛抽象原则，保留最小策略语言：问题图、最窄节点、证据/假设分离。

- 修改：`tests/test_research_state_tool.py`
  - 新增 strategy frame、path choice、claim inventory 测试。

- 修改：`tests/test_short_answer_research_protocol.py`
  - 增加 skill 文本包含关键 action trace 的静态测试。

---

## 任务 1：加入证据/假设分离的 claim inventory

**文件：**
- 修改：`agent_os/tools/research.py`
- 测试：`tests/test_research_state_tool.py`

- [ ] **步骤 1：编写失败测试**

在 `tests/test_research_state_tool.py` 增加：

```python
@pytest.mark.asyncio
async def test_claim_inventory_separates_verified_facts_from_hypotheses():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state

    set_session_context(work_dir="", session_id="claim-inventory-test")
    await handle_research_state(operation="start", question_model={"answer_type": "person"})

    out = await handle_research_state(
        operation="claim_inventory",
        verified_facts=[
            "2018 Lantern Prize feature winners include two digital museum publications"
        ],
        hypotheses=[
            "One listed critic may have written the later conservation review"
        ],
        unknown=[
            "which later review references a conservation-science study"
        ],
    )

    assert out.success
    state = out.data["state"]
    assert state["claim_inventory"]["verified_facts"] == [
        "2018 Lantern Prize feature winners include two digital museum publications"
    ]
    assert state["claim_inventory"]["hypotheses"] == [
        "One listed critic may have written the later conservation review"
    ]
    assert "hypotheses_are_not_facts" in out.data["guidance"]
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest -q tests/test_research_state_tool.py::test_claim_inventory_separates_verified_facts_from_hypotheses
```

预期：失败，`claim_inventory` 未实现。

- [ ] **步骤 3：实现最小状态字段**

在 `_empty_state()` 增加：

```python
"claim_inventory": {
    "verified_facts": [],
    "hypotheses": [],
    "unknown": [],
},
```

在 `_public_state()` 增加：

```python
"claim_inventory": deepcopy(state.get("claim_inventory", {})),
```

在 `handle_research_state()` 增加分支：

```python
if op == "claim_inventory":
    state["claim_inventory"] = {
        "verified_facts": _as_list(kw.get("verified_facts")),
        "hypotheses": _as_list(kw.get("hypotheses")),
        "unknown": _as_list(kw.get("unknown")),
    }
    _save_state(state)
    result = _next_action(state)
    result["claim_inventory_recorded"] = True
    result["guidance"] = [
        "hypotheses_are_not_facts",
        "use retrieval to verify hypotheses before promoting them to evidence",
    ]
    return ToolResult.ok(data=result)
```

并在 tool schema `operation.enum` 加入 `claim_inventory`，properties 加入 `verified_facts`、`hypotheses`、`unknown`。

- [ ] **步骤 4：运行测试确认通过**

运行同上命令，预期 PASS。

- [ ] **步骤 5：兼容旧 inventory_known_facts**

保留旧操作，但在返回 data 中加入：

```python
result["guidance"] = [
    "Only include verified facts in known_facts. Put guesses in claim_inventory.hypotheses."
]
```

这样不破坏现有调用，但逐步引导模型不再把假设写进 known facts。

---

## 任务 2：加入问题图 strategy_frame

**文件：**
- 修改：`agent_os/tools/research.py`
- 测试：`tests/test_research_state_tool.py`

- [ ] **步骤 1：编写失败测试**

```python
@pytest.mark.asyncio
async def test_strategy_frame_records_problem_graph_nodes_and_edges():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state

    set_session_context(work_dir="", session_id="strategy-frame-test")
    await handle_research_state(operation="start", question_model={"answer_type": "person"})

    out = await handle_research_state(
        operation="strategy_frame",
        nodes=[
            "critic",
            "digital feature prize",
            "later review",
            "referenced conservation scientist",
            "three-author conservation study",
            "heritage materials workshop presenter",
        ],
        edges=[
            "critic won prize",
            "critic wrote later review",
            "review references scientist",
            "scientist coauthored study",
            "one coauthor presented workshop five years before prize",
        ],
        anchors=[
            "heritage society workshop records",
            "OpenAlex conservation publications",
            "digital feature prize winner lists",
        ],
    )

    assert out.success
    frame = out.data["state"]["strategy_frame"]
    assert "heritage materials workshop presenter" in frame["nodes"]
    assert "OpenAlex conservation publications" in frame["anchors"]
    assert out.data["next_action"] in {"choose_path", "discriminating_search", "focus_constraint"}
```

- [ ] **步骤 2：实现状态字段**

在 `_empty_state()` 增加：

```python
"strategy_frame": {
    "nodes": [],
    "edges": [],
    "anchors": [],
},
"path_choice": {},
```

在 `_public_state()` 暴露这两个字段。

- [ ] **步骤 3：实现 operation**

```python
if op == "strategy_frame":
    state["strategy_frame"] = {
        "nodes": _as_list(kw.get("nodes")),
        "edges": _as_list(kw.get("edges")),
        "anchors": _as_list(kw.get("anchors")),
    }
    _save_state(state)
    result = _next_action(state)
    result["strategy_frame_recorded"] = True
    result["next_action"] = "choose_path"
    result["action_card"] = {
        "required_output": "Choose forward, backward, or anchor-first path. Prefer the path with the narrowest searchable node.",
        "allowed_next_tools": ["research_state"],
        "blocked_next_tools": [],
        "search_needed": "after_path_choice",
    }
    return ToolResult.ok(data=result)
```

- [ ] **步骤 4：更新 schema 并跑测试**

运行：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest -q tests/test_research_state_tool.py::test_strategy_frame_records_problem_graph_nodes_and_edges
```

---

## 任务 3：加入路径选择 path_choice

**文件：**
- 修改：`agent_os/tools/research.py`
- 测试：`tests/test_research_state_tool.py`

- [ ] **步骤 1：编写失败测试**

```python
@pytest.mark.asyncio
async def test_path_choice_prefers_narrowest_searchable_node():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state

    set_session_context(work_dir="", session_id="path-choice-test")
    await handle_research_state(operation="start", question_model={"answer_type": "person"})
    await handle_research_state(
        operation="strategy_frame",
        nodes=["critic", "award list", "later review", "conservation study", "workshop presenter"],
        anchors=["award list", "workshop presenter"],
    )

    out = await handle_research_state(
        operation="path_choice",
        candidate_paths=[
            "forward: critic -> prize -> review -> scientist -> workshop",
            "backward: workshop presenter -> conservation study -> cited article -> critic",
            "anchor-first: prize list + workshop records intersection",
        ],
        chosen_path="backward: workshop presenter -> conservation study -> cited article -> critic",
        narrowest_node="workshop presenter / specialist publication cluster",
        first_action="pubmed_search(query=\"conservation scientist workshop materials study\")",
        reject_reason=[
            "forward path starts from broad critic universe",
            "award list alone has many media candidates",
        ],
    )

    assert out.success
    choice = out.data["state"]["path_choice"]
    assert choice["narrowest_node"] == "workshop presenter / specialist publication cluster"
    assert "openalex_works" in choice["first_action"]
    assert out.data["path_choice_recorded"] is True
```

- [ ] **步骤 2：实现 operation**

```python
if op == "path_choice":
    state["path_choice"] = {
        "candidate_paths": _as_list(kw.get("candidate_paths")),
        "chosen_path": str(kw.get("chosen_path", "")).strip(),
        "narrowest_node": str(kw.get("narrowest_node", "")).strip(),
        "first_action": str(kw.get("first_action", "")).strip(),
        "reject_reason": _as_list(kw.get("reject_reason")),
    }
    _save_state(state)
    result = _next_action(state)
    result["path_choice_recorded"] = True
    result["guidance"] = [
        "execute the first_action if still appropriate",
        "if it fails, pivot to the next candidate path rather than rotating keywords",
    ]
    return ToolResult.ok(data=result)
```

- [ ] **步骤 3：更新 schema 并跑测试**

运行：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest -q tests/test_research_state_tool.py::test_path_choice_prefers_narrowest_searchable_node
```

---

## 任务 4：短答案 skill 改成问题图优先

**文件：**
- 修改：`skills/short_answer_research/SKILL.md`
- 测试：`tests/test_short_answer_research_protocol.py`

- [ ] **步骤 1：新增静态测试**

在 `tests/test_short_answer_research_protocol.py` 增加：

```python
def test_short_answer_skill_teaches_problem_graph_and_path_choice():
    text = Path("skills/short_answer_research/SKILL.md").read_text(encoding="utf-8")
    assert "strategy_frame" in text
    assert "path_choice" in text
    assert "narrowest searchable node" in text
    assert "forward" in text and "backward" in text
    assert "hypotheses are not facts" in text.lower()
```

- [ ] **步骤 2：修改 skill 前部协议**

在 `Copyable Action Traces` 前增加：

```markdown
## Strategy Spine

For chain puzzles, do not start by searching the first entity mentioned. First externalize the problem graph:

1. `strategy_frame`: nodes, edges, anchors.
2. `path_choice`: forward path, backward path, anchor-first path.
3. Choose the narrowest searchable node.
4. Run one action from the chosen path.
5. Promote only verified evidence to facts; keep guesses as hypotheses.
```

加入示例：

```markdown
Bad path:
`critic -> prize -> later review -> cited specialist` because critic/review space is huge.

Better path:
`society workshop presenter -> specialist publication cluster -> cited review -> critic` because society/publication records are narrower and structured.
```

- [ ] **步骤 3：跑静态测试**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest -q tests/test_short_answer_research_protocol.py::test_short_answer_skill_teaches_problem_graph_and_path_choice
```

---

## 任务 5：retrieval_strategy 从工具表升级为节点选择示例

**文件：**
- 修改：`skills/retrieval_strategy/SKILL.md`
- 测试：`tests/test_short_answer_research_protocol.py`

- [ ] **步骤 1：新增静态测试**

```python
def test_retrieval_strategy_teaches_node_then_tool():
    text = Path("skills/retrieval_strategy/SKILL.md").read_text(encoding="utf-8")
    assert "Choose the node before the tool" in text
    assert "narrow node" in text
    assert "broad node" in text
    assert "specialist publication cluster" in text
```

- [ ] **步骤 2：新增段落**

在 `Copyable Retrieval Traces` 前加入：

```markdown
## Choose the Node Before the Tool

Do not ask "which keyword next?" Ask "which node in the problem graph is narrowest and searchable?"

| Node | Width | Tool shape |
|---|---|---|
| critic who wrote a later review | broad | avoid as first path |
| digital feature prize winners in one year | medium | domain-locked web search |
| specialist coauthors in OpenAlex/CrossRef | narrow | `pubmed_search` / `openalex_works` |
| society workshop presenter in one year | narrow | domain-locked web search / official PDF |
```

- [ ] **步骤 3：跑测试**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest -q tests/test_short_answer_research_protocol.py::test_retrieval_strategy_teaches_node_then_tool
```

---

## 任务 6：research_state 描述改成示例优先

**文件：**
- 修改：`agent_os/tools/descriptions/research_state.txt`

- [ ] **步骤 1：改写描述**

把描述前半部分改成：

```text
Externalize research strategy state. Use this to separate facts from hypotheses and to choose a path through a multi-hop question.

Common patterns:
1. strategy_frame(nodes=[...], edges=[...], anchors=[...])
2. path_choice(candidate_paths=[forward, backward, anchor-first], chosen_path=..., narrowest_node=..., first_action=...)
3. claim_inventory(verified_facts=[...], hypotheses=[...], unknown=[...])
4. round_update(progress=..., progress_note=...)
```

保留原有 state operations 列表，但把新操作排在前面。

- [ ] **步骤 2：运行注册测试**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest -q tests/test_research_state_tool.py::test_research_state_tool_is_registered
```

---

## 任务 7：清理旧 tool_strategy 设计文档

**文件：**
- 修改或删除：`docs/superpowers/specs/2026-05-22-tool-strategy-phase-design.md`

- [ ] **步骤 1：替换旧文档状态**

将旧文档顶部状态改为：

```markdown
**状态：废弃**

此方案废弃原因：它把工具选择设计成一个强制阶段，并禁止检索，容易复现 reason_from_known_facts 死锁。后续采用 `2026-05-23-research-strategy-architecture-redesign.md` 中的问题图/路径选择方案。
```

或者直接删除该文档，并在本计划中说明废弃原因。

- [ ] **步骤 2：检查无旧术语依赖**

运行：

```bash
rg -n "tool_strategy|strategy_completed|禁止检索" docs agent_os skills tests
```

预期：只在废弃文档或本计划中出现。

---

## 任务 8：集成测试与提交

**文件：**
- 修改：上述全部

- [ ] **步骤 1：运行相关测试**

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest -q \
  tests/test_research_state_tool.py \
  tests/test_short_answer_research_protocol.py \
  tests/test_search_tools.py \
  tests/test_openalex_tools.py \
  tests/test_tool_registration.py
```

预期：全部 PASS。

- [ ] **步骤 2：编译检查**

```bash
uv run python -m compileall agent_os/tools/research.py agent_os/kernel/agent_loop.py agent_os/tools/search.py agent_os/tools/openalex.py
```

预期：无错误。

- [ ] **步骤 3：人工检查设计边界**

确认：

- Kernel 没有新增 deep research 业务流程。
- 没有新增硬封 `web_search` 的策略。
- `claim_inventory` 明确区分事实和假设。
- `path_choice` 鼓励反向/锚点路径，但不强迫某一种路径。
- Skills 使用 example traces，不再主要靠抽象禁令。

- [ ] **步骤 4：Commit**

```bash
git add agent_os/tools/research.py \
  agent_os/tools/descriptions/research_state.txt \
  skills/short_answer_research/SKILL.md \
  skills/retrieval_strategy/SKILL.md \
  tests/test_research_state_tool.py \
  tests/test_short_answer_research_protocol.py \
  docs/superpowers/plans/2026-05-23-research-strategy-architecture-redesign.md

git commit -m "design: add research strategy architecture plan"
```

---

## 风险与约束

- 不要把 `strategy_frame` 做成强制硬门。它应是强建议和可见脚手架，不是检索许可系统。
- 不要让状态字段膨胀成报告。每个字段必须短，适合在上下文里反复读取。
- 不要让工具选择变成新的长表格。用 3 条路径 + 1 个最窄节点，比 15 个工具比较更有效。
- 不要破坏 KV cache：动态策略状态仍然通过 tool result / session state 注入，不改 system prompt 的动态部分。
- 不要用“反向路径”过拟合某题。原则是：比较路径宽度，选择最窄可检索节点。

---

## 成功标准

一次类似虚构多跳链式题，模型应表现为：

1. 先画节点链，而不是立即从 宽入口人物搜起。
2. 明确比较 forward / backward / anchor-first 三条路径。
3. 选择最窄节点，例如 society/specialist publication cluster。
4. 使用 `pubmed_search` / `openalex_works` / domain-locked web search 的组合。
5. 把“某记者可能写过目标文章”放入 hypotheses，而不是 known facts。
6. 如果路径失败，切换路径，而不是继续换关键词。
