"""
Research scratchpad tool — simple external thinking surface.

Replaces the previous complex state machine. Model calls research_state(content=...)
to externalize thinking; the FULL scratchpad content is returned in the tool result,
so the model sees it immediately. Call with no content to just read current scratchpad.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .registry import ToolResult, get_session_work_dir


def _read_or_empty(work_dir: str) -> str:
    path = Path(work_dir) / "research" / "scratchpad.md"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


async def handle_research_state(content: str = "", **kw: Any) -> ToolResult:
    """Write the research scratchpad. A free-form external thinking surface.

    The FULL scratchpad content is returned in the tool result so you see it
    immediately. Call with no content to read the current scratchpad.
    """
    try:
        work_dir = get_session_work_dir()
        if not work_dir:
            return ToolResult.fail("No workspace available")
        text = (content or "").strip()
        if text:
            path = Path(work_dir) / "research" / "scratchpad.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        full = _read_or_empty(work_dir)
        return ToolResult.ok(data={
            "written": bool(text),
            "chars": len(text) if text else 0,
            "scratchpad": full,
            "hint": "Write whatever helps your thinking via the content parameter. No fixed structure.",
        })
    except Exception as e:
        return ToolResult.fail(str(e))


def register_research_tools(r) -> None:
    r.register("research_state", "reasoning", {
        "name": "research_state",
        "description": (
            "Externalize your thinking on the research scratchpad. "
            "Call with content= to write; the FULL scratchpad is returned in the result. "
            "Call with no content to read the current scratchpad. "
            "Use for candidates, constraints, evidence, dimension coverage, "
            "gaps, questions, next moves. No fixed structure."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The full scratchpad content (replaces previous). Omit to just read.",
                },
            },
            "required": [],
        },
    }, handle_research_state, read_only=False)
