# Parallel Feasibility Probe + Tool Rebalancing：设计文档

> **目标：** 解决模型在 short-answer-research 中"第一轮选错搜索方向就回不来"的问题，通过并行探测 + 工具描述再平衡打破 web_search 路径依赖。

**状态：** 设计完成 · **关联：** `agent_os/tools/research.py`, `agent_os/tools/base_tools.py`, `agent_os/kernel/sub_agent.py`, `skills/short_answer_research/SKILL.md`

---

## 1. 问题复现

两次 BrowseComp 测试（bc_en_015, bc_en_??2）均失败：

| 指标 | 运行 1（改前） | 运行 2（改后） |
|------|-------------|-------------|
| 总轮数 | 31+ | 32+ |
| web_search | 16 次 | 15+ 次 |
| 结构化工具 | 0 次 | 1 次（openalex_works 用错参数） |
| 答案命中 | ❌ | ❌ |

**工具描述精简后模型行为未改善**——说明问题不在描述层面，而在模型一次推理中无法同时考虑"工具选择 + 问题策略"。

**核心 deadlock：** 模型第一轮就锁定正推方向（宽入口人物→奖项→后续文章→被引用专家），从此所有后续搜索都在强化这个错误路径。没有机制在初始阶段并行验证多个方向。

---

## 2. 已完成：工具选择再平衡

### 2.1 工具描述精简（已提交改动）

- arxiv: 27 → 11 行，openalex_works: 23 → 14 行，pubmed: 16 → 11 行
- 每个工具加 3-5 个 preset 示例（copy-paste 即用）
- openalex_works 新增 `query` 字段（和 web_search 一样的"一句话调用"）

### 2.2 web_search 加摩擦（已提交改动）

- 描述开篇警告：Before using this for academic/entity/biomedical tasks, consider structured tools
- 底部约束：If 2-3 searches don't change candidates, change tool/frame/source/domain
- 结果返回 `next_search_hint`：自动抽取 top 3 域名，给 domain drilldown 模板

### 2.3 系统提示重构（已提交改动）

`<tool_guide>` 从表格改为 "action shapes 菜单"：
- `lookup` → wikipedia / crossref
- `match/search` → openalex / arxiv / pubmed
- `disambiguate` → openalex_entity → openalex_works
- `domain-lock` → domain_sites → web_search
- `open web` → web_search（最后手段）

---

## 3. 待实现：并行可行性探测

### 3.1 核心思路

`focus_constraint` 完成后，不直接进入 `discriminating_search`，而是 spawn 2-3 个子 agent 从不同方向并行探测。每个子 agent 限制工具集和调用次数，返回 feasibility report。主 agent 汇总后选最优路线。

### 3.2 阶段流变更

**当前：**
```
focus_constraint → discriminating_search → ...
```

**变更后：**
```
focus_constraint → probe → discriminating_search → ...
```

### 3.3 probe 阶段

**触发条件：** `active_constraint` 刚设置（`probe_completed == False`）

**执行流程：**
1. 主 agent 收到 `probe` action_card，要求制定探测计划
2. 调用 `spawn` 并行启动 2-3 个子 agent
3. 每个子 agent 从不同角度探测，返回 feasibility report
4. 主 agent 汇总，决定从哪个方向切入

### 3.4 子 Agent 配置

| 子 Agent | 方向 | 允许工具 | `max_tool_calls` |
|----------|------|---------|-----------------|
| A（结构化反推） | 从问题末端的结构化实体反推 | `pubmed_search, openalex_works, openalex_entity` | 2 |
| B（web 正推） | 从 web 公开信息正向搜索 | `web_search, web_read, domain_sites` | 2 |
| C（混合自由） | 不预设方向，自由探测 | 全工具（除 spawn） | 2 |

### 3.5 Feasibility Report 格式

每个子 agent 返回纯文本，主 agent 解析：

```
## Feasibility Report

**angle:** structured-reverse
**feasibility:** HIGH
**key_findings:**
- Found a specialist coauthor presenting at the relevant society meeting
- Found that presenter coauthored the target study with two other specialists
**open_questions:**
- Which later article cited this study?
**recommended_next_tool:** openalex_works(references="target study title")
**rationale:** 已定位具体 PT 和合著关系，只需找引用即可完成链条
```

### 3.6 子 Agent 超时和中断

- 每个子 agent 最多 2 次工具调用（由 `max_tool_calls` 控制）
- 达到上限后自动 conclude 并返回报告
- 主 agent 有总体超时（60 秒），超时后使用已完成的报告决策

### 3.7 Guardrail 交互

probe 阶段为非 terminal 阶段，仅 advisory——`enforce_research_state_action_card` 不硬封锁。主 agent 汇总后进入 `discriminating_search`。

---

## 4. State 变更

```python
@dataclass
class ResearchState:
    ...
    probe_completed: bool = False
    probe_reports: list[dict] = field(default_factory=list)
```

---

## 5. 需要改的代码

| 文件 | 变更 |
|------|------|
| `agent_os/tools/research.py` | `_next_action()` 新增 `probe` 分支；`_action_card()` 新增 probe 卡片；`ResearchState` 新增 `probe_completed` / `probe_reports` |
| `agent_os/tools/base_tools.py` | `spawn()` 新增 `max_tool_calls` 参数 |
| `agent_os/kernel/sub_agent.py` | 支持 `max_tool_calls` 限制，达到后自动 conclude |
| `skills/short_answer_research/SKILL.md` | 补充 probe 阶段说明和 feasibility report 格式 |
| `tests/test_research_state_tool.py` | 新增 probe 相关测试 |

---

## 6. 风险

| 风险 | 缓解 |
|------|------|
| 2 次调用全浪费 | 子 agent 只做可行性判断，不要求完整答案。命中 1 个线索就算成功 |
| 并行 spawn 增加 token 开销 | 每个子 agent 2 次调用，上下文最多 3 轮，开销可控 |
| 子 agent 也陷入局部路径 | 限制工具集强制子 agent 只能用特定数据库，防止它们也跑回 web_search |

---

## 7. 未纳入范围

- 动态决定子 agent 数量（暂固定 2-3 个）
- 子 agent 间的共享工作内存（暂独立运行）
- probe 失败后的自动 pivot（暂由主 agent 人工判断）
