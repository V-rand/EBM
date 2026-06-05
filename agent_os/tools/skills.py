"""
Skill tool — loads a skill's full instructions into the conversation.

Skills are instruction bundles (pure Markdown), not kernel workflows.
Only names and descriptions appear in the system prompt; the full body
is retrieved via this tool and enters the chat as a tool result, leaving
the KV cache prefix undisturbed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .registry import ToolResult, get_session_work_dir, get_tool_dep
from ..kernel.helpers import slug


def _load_desc(name: str) -> str:
    p = Path(__file__).resolve().parent / "descriptions" / f"{name}.txt"
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


if TYPE_CHECKING:
    from ..skills.loader import SkillLoader


def _skill_loader() -> SkillLoader | None:
    return get_tool_dep("skill_loader")


async def handle_skill_use(name, **kw) -> ToolResult:
    """Return the full body of a skill wrapped in <skill_content>."""
    sl = _skill_loader()
    if sl is None:
        return ToolResult.fail("Skill loader not available")
    skill = sl.resolve_skill(name)
    if skill is None:
        return ToolResult.fail(f"Skill not found: {name}")
    content = str(skill.get("content", ""))
    body = str(sl.get_skill_body(name) or content)
    base = skill.get("path", "")
    files = _supporting_files(skill)
    lines = [
        f"<skill_content name=\"{skill.get('name', name)}\">",
        body,
        "",
        f"Base directory: {base}",
        "Relative paths in this skill are relative to this directory.",
    ]
    if files:
        lines.append("<skill_files>")
        lines.extend(f"  {f}" for f in files)
        lines.append("</skill_files>")
    lines.append("</skill_content>")
    return ToolResult.ok(data={
        "name": skill.get("name", name),
        "description": skill.get("description", ""),
        "content": "\n".join(lines),
    })


async def handle_skill_propose(name, content, description="", **kw) -> ToolResult:
    """Propose a new skill or improvement. Writes to research/skill_proposals/ for human review."""
    wd = get_session_work_dir()
    if not wd:
        return ToolResult.fail("Missing session work directory")
    safe_name = str(name or "").strip()
    if not safe_name:
        return ToolResult.fail("Skill name is required")
    proposals_dir = Path(wd) / "research" / "skill_proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    skill_md = f"""---
name: {safe_name}
description: {description or "由 AI 自动提议的 skill"}
---

{content}
"""
    proposal_path = proposals_dir / f"{slug(safe_name)}.md"
    proposal_path.write_text(skill_md, encoding="utf-8")
    return ToolResult.ok(data={
        "path": f"research/skill_proposals/{slug(safe_name)}.md",
        "name": safe_name,
        "description": description,
        "note": "提案已写入 research/skill_proposals/，需人工审核后方可移入 skills/ 目录生效。",
    })


def _supporting_files(skill: dict[str, Any]) -> list[str]:
    base = Path(str(skill.get("path", "")))
    if not base.exists():
        return []
    files: list[str] = []
    for sub in ("references", "templates", "scripts", "assets"):
        d = base / sub
        if d.exists():
            for item in sorted(d.rglob("*")):
                if item.is_file() and not item.is_symlink():
                    files.append(str(item.relative_to(base)))
    return files[:80]


async def handle_skill_file_grep(skill_name, pattern, file_path=None, **kw) -> ToolResult:
    """Search within a skill's supporting files for a pattern."""
    sl = _skill_loader()
    if sl is None:
        return ToolResult.fail("Skill loader not available")
    skill = sl.resolve_skill(skill_name)
    if skill is None:
        return ToolResult.fail(f"Skill not found: {skill_name}")
    base = Path(str(skill.get("path", ""))).resolve()
    search_dirs = ("references", "templates", "scripts", "assets")
    pattern_lower = str(pattern).lower()
    matches: list[dict[str, Any]] = []

    def _search_file(f: Path) -> None:
        """Search a single file for pattern matches."""
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            return
        rel = str(f.relative_to(base))
        for i, line in enumerate(content.splitlines(), 1):
            if pattern_lower in line.lower():
                matches.append({
                    "file": rel,
                    "line": i,
                    "content": line.strip()[:200],
                })

    for sub in search_dirs:
        d = base / sub
        if not d.exists():
            continue
        if file_path:
            search_target = d / str(file_path).lstrip("/")
            if not search_target.exists():
                continue
            if search_target.is_file():
                _search_file(search_target)
            else:
                for item in sorted(search_target.rglob("*")):
                    if item.is_file() and not item.is_symlink():
                        _search_file(item)
        else:
            for item in sorted(d.rglob("*")):
                if item.is_file() and not item.is_symlink():
                    _search_file(item)

    return ToolResult.ok(data={
        "skill_name": skill.get("name", skill_name),
        "pattern": pattern,
        "matches": matches[:50],
        "total_matches": len(matches),
        "truncated": len(matches) > 50,
    })


async def handle_skill_file_read(skill_name, file_path, **kw) -> ToolResult:
    """Read a supporting file from a skill's directory (references, templates, etc.)."""
    sl = _skill_loader()
    if sl is None:
        return ToolResult.fail("Skill loader not available")
    try:
        result = sl.read_skill_file(skill_name, file_path)
        return ToolResult.ok(data=result)
    except (ValueError, FileNotFoundError) as e:
        return ToolResult.fail(str(e))


def register_skill_tools(r) -> None:
    r.register("skill_use", "skills", {
        "name": "skill_use",
        "description": _load_desc("skill_use"),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill name as shown in <available_skills>"},
            },
            "required": ["name"],
        },
    }, handle_skill_use, concurrency_safe=True, read_only=True)
    r.register("skill_propose", "skills", {
        "name": "skill_propose",
        "description": _load_desc("skill_propose"),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill 名称（建议英文小写+下划线）"},
                "content": {"type": "string", "description": "Skill 的 Markdown 正文"},
                "description": {"type": "string", "description": "Skill 简短描述（可选）"},
            },
            "required": ["name", "content"],
        },
    }, handle_skill_propose)

    r.register("skill_file_read", "skills", {
        "name": "skill_file_read",
        "description": _load_desc("skill_file_read"),
        "parameters": {
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "Skill 名称"},
                "file_path": {"type": "string", "description": "相对 skill 目录的文件路径"},
            },
            "required": ["skill_name", "file_path"],
        },
    }, handle_skill_file_read, concurrency_safe=True, read_only=True)

    r.register("skill_file_grep", "skills", {
        "name": "skill_file_grep",
        "description": _load_desc("skill_file_grep"),
        "parameters": {
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "Skill 名称"},
                "pattern": {"type": "string", "description": "搜索模式（子字符串，大小写不敏感）"},
                "file_path": {"type": "string", "description": "可选，限定搜索范围到特定文件或子目录"},
            },
            "required": ["skill_name", "pattern"],
        },
    }, handle_skill_file_grep, concurrency_safe=True, read_only=True)