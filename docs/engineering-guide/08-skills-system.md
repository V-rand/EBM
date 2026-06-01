# Skills 系统

`agent_os/skills/loader.py` — 229 行。

## 设计哲学

Skills 是零代码工作流定义。不是"技能"在传统 AI 意义上（如"说英语"），而是**领域特定的方法论、约束和行为指南**。

## 文件系统结构

```
skills/
├── long_form_research/
│   └── SKILL.md        # 结构化报告研究
├── short_answer_research/
│   └── SKILL.md        # 短答案研究
├── retrieval_strategy/
│   └── SKILL.md        # 多步检索方法论
├── domain_sites/
│   └── SKILL.md        # 领域权威网站目录
└── constraint_reasoning/
    └── SKILL.md        # 多约束推理
```

## 发现与加载

### SkillLoader

```python
class SkillLoader:
    def __init__(self, skills_dir=None, extra_skill_dirs=None):
        # 默认搜索 skills/ 目录
        # extra_skill_dirs 可额外指定
    
    def discover_all(self):
        # 遍历所有子目录
        # 查找 SKILL.md 文件
        # 解析 YAML frontmatter
        # 构建元数据索引
        return {name: skill_metadata}
    
    def get(self, name):
        # 按名称获取 skill
        return self._skills.get(name)
```

### 发现优先级

```python
# 1. 主目录: <project>/skills/
# 2. 额外目录: extra_skill_dirs 参数
# 3. 子嵌套: 支持层级目录（最多 2 层）
```

### SKILL.md 元数据

```yaml
---
name: long_form_research          # 唯一标识
layer: domain                      # system / domain
description: 结构化报告研究         # 简短描述
when_to_use: 分析报告、比较和综合   # 触发场景指引
allowed-tools:                      # 此 skill 允许的工具
  - web_search
  - workspace_search
  - file_write
paths:                             # 条件激活路径
  include: ["research/"]
  exclude: ["**/temp/**"]
profile:                           # 工作区模板（可选）
  folders: [uploads, research]
  files:
    cases.md: "# {{session_name}}"
---
```

## 激活机制

### 手动激活

Agent 调用 `skill_use("long_form_research")`：

1. SkillLoader 从文件系统加载完整内容
2. 返回 `skill_content` 块（整个 SKILL.md）
3. 内容作为 tool 结果注入会话
4. Agent 读取并遵循 skill 指令

### 条件路径激活

```python
# AgentLoop 中，当 agent 操作文件时检查：
if tool_name in _PATH_BEARING_TOOLS:
    path = tool_args.get("path", "")
    for skill in conditional_skills:
        if matches_path(path, skill["paths"]):
            inject_skill(skill)
```

当 agent 写入 `research/` 下文件时，自动激活 `long_form_research` skill。

### 前端索引

只索引 name + description 到 system prompt：

```xml
<skills_index>
  <skill name="long_form_research" desc="结构化报告研究"/>
  <skill name="short_answer_research" desc="约束驱动短答案"/>
</skills_index>
```

完整内容在运行时按需加载。

## Skill 的作用方式

Skill 不修改 kernel 行为，而是改变 Agent 的决策：

| 注入时机 | 效果 |
|---------|------|
| skill_use 调用 | 增加额外的约束和指导 |
| 条件路径匹配 | 自动调整行为 |
| 未激活 | 无影响 |

### 与 Tool 的区别

```python
# Tool: 执行外部动作
web_search(query="...")  # 发起 HTTP 请求

# Skill: 改变决策逻辑
skill_use("long_form_research")  # → "应该使用覆盖率映射方法"
```

## 编写 Skill 的原则

参见 [Prompt Skills 设计](13b-prompt-skills-design.md)。

## 示例：最简单的 Skill

```markdown
---
name: quick-check
layer: domain
description: 快速事实检查
---

# 快速事实检查

1. 确定需要验证的事实
2. 搜索：web_search(query="确切的查询词")
3. 验证：比较搜索结果中的多个来源
4. 记录：file_write 记录验证结果
```

## Skill 提案机制

```python
# agent 通过 skill_propose 提出新 skill
skill_propose(
    name="custom_workflow",
    content="# 自定义工作流\n...",
)
# 写入 research/skill_proposals/custom_workflow.md
# 等待人类审核后移入 skills/
```
