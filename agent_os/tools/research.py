"""
Research scratchpad tool — external thinking surface for the model.

The model's chain-of-thought is NOT visible in subsequent turns. This tool
writes thinking to a persistent scratchpad so the model can see its own
reasoning across turns, preventing drift in multi-turn research.

Usage:
- content="..." → replace the entire scratchpad (default)
- content="..." + append=true → append to existing scratchpad
- no content → read-only (returns current scratchpad)

NOT a task tracker — use todowrite for action items (to-do/doing/done).
This is a free-form thinking surface: hypotheses, candidates, constraints,
PICO framework, evidence matrix, coverage gaps, reasoning chains.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .registry import ToolResult, get_session_work_dir


def _read_or_empty(work_dir: str) -> str:
    path = Path(work_dir) / "research" / "scratchpad.md"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


async def handle_research_state(
    content: str = "",
    append: bool = False,
    lines: str = "",
    **kw: Any,
) -> ToolResult:
    """Write the research scratchpad — model's external thinking surface.

    content="full replacement content"  → overwrite scratchpad (default)
    content="..." + append=true         → append to existing scratchpad
    lines="single line" + append=true   → append one line (convenience)
    no content                          → read current scratchpad only
    """
    try:
        work_dir = get_session_work_dir()
        if not work_dir:
            return ToolResult.fail("No workspace available")

        text = (content or lines or "").strip()
        # lines= is a shortcut for append mode (single-line quick record)
        if lines and not content:
            append = True
        path = Path(work_dir) / "research" / "scratchpad.md"
        path.parent.mkdir(parents=True, exist_ok=True)

        if text:
            if append and path.exists():
                existing = path.read_text(encoding="utf-8")
                separator = "\n\n" if existing and not existing.endswith("\n") else "\n"
                path.write_text(f"{existing}{separator}{text}", encoding="utf-8")
            else:
                path.write_text(text, encoding="utf-8")

        full = _read_or_empty(work_dir)
        return ToolResult.ok(data={
            "written": bool(text),
            "appended": bool(text and append),
            "chars": len(text) if text else 0,
            "total_chars": len(full),
            "scratchpad": full,
            "hint": (
                "这是你跨轮次的思考草稿。下一轮你看不到当前轮的思维链，"
                "所以必须把候选假说、验证进度、证据缺口写到这里。"
                "用 append=true 追加新内容，不传 content 只读当前草稿。"
                "不要在这里写待办事项——那是 todowrite 的工作。"
            ),
        })
    except Exception as e:
        return ToolResult.fail(str(e))


def register_research_tools(r) -> None:
    r.register("research_state", "reasoning", {
        "name": "research_state",
        "description": (
            "跨轮次思考草稿纸——下一轮看不到当前轮的思维链，必须外化到这里。\n"
            "用 content= 全量替换，或 content= + append=true 追加。不传 content 为只读。\n"
            "写什么：候选假说、验证进度、PICO框架、证据矩阵、覆盖缺口、推理链。\n"
            "不写什么：待办事项（用 todowrite）、最终报告（用 file_write）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "草稿内容。全量替换模式（默认）或追加模式下的新内容。留空则只读当前草稿。",
                },
                "append": {
                    "type": "boolean",
                    "description": "true 则追加到现有草稿而非替换。适合增量更新。",
                },
                "lines": {
                    "type": "string",
                    "description": "快捷参数：追加单行内容（等价于 content= + append=true）。适合快速记录一个发现。",
                },
            },
            "required": [],
        },
    }, handle_research_state, read_only=False)
