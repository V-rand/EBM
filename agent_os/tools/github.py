"""
GitHub Search tool — code, repos, issues, commits, topics, users.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

import requests as _requests

from .registry import ToolResult

_github_session = _requests.Session()
_github_session.trust_env = False  # bypass proxy — academic APIs faster direct from China

GITHUB_API = "https://api.github.com"
_GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
_DESC_DIR = Path(__file__).resolve().parent / "descriptions"
_last_github_call: float = 0
_github_lock = asyncio.Lock()
_GITHUB_RATE = 2.1  # authenticated: 30/min, unauthenticated: 10/min; use 2.1s for safety


def _load_desc(name: str) -> str:
    path = _DESC_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _github_api_get(url: str) -> _requests.Response:
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "AgentOS-github-search"}
    if _GITHUB_TOKEN:
        headers["Authorization"] = f"token {_GITHUB_TOKEN}"
    return _github_session.get(url, headers=headers, timeout=15)


_ACCEPT_MAP = {
    "repositories": "application/vnd.github.v3+json",
    "code": "application/vnd.github.v3.text-match+json",
    "issues": "application/vnd.github.v3.text-match+json",
    "commits": "application/vnd.github.v3.text-match+json",
    "topics": "application/vnd.github.mercy-preview+json",
    "users": "application/vnd.github.v3.text-match+json",
}


async def handle_github_search(
    query: str = "",
    search_type: str = "repositories",
    sort: str = "",
    order: str = "desc",
    per_page: int = 20,
    **kw: Any,
) -> ToolResult:
    global _last_github_call
    q = (query or "").strip()
    if not q:
        return ToolResult.fail("query is required")
    st = search_type.strip() or "repositories"
    if st not in _ACCEPT_MAP:
        return ToolResult.fail(f"Invalid search_type: {st}. Must be one of: {', '.join(_ACCEPT_MAP)}")
    if per_page < 1 or per_page > 100:
        return ToolResult.fail("per_page must be 1-100")

    params: dict[str, Any] = {"q": q, "per_page": min(per_page, 100)}
    if sort:
        params["sort"] = sort
    if order in ("asc", "desc"):
        params["order"] = order

    url = f"{GITHUB_API}/search/{st}"

    try:
        async with _github_lock:
            elapsed = time.time() - _last_github_call
            if elapsed < _GITHUB_RATE:
                await asyncio.sleep(_GITHUB_RATE - elapsed)
            _last_github_call = time.time()

        loop = asyncio.get_running_loop()
        r = await loop.run_in_executor(None, lambda: _github_session.get(
            url,
            headers={
                "Accept": _ACCEPT_MAP.get(st, "application/vnd.github.v3+json"),
                "User-Agent": "AgentOS-github-search",
                **({"Authorization": f"token {_GITHUB_TOKEN}"} if _GITHUB_TOKEN else {}),
            },
            params=params,
            timeout=15,
        ))

        if r.status_code == 403 and "rate limit" in r.text.lower():
            reset_time = int(r.headers.get("X-RateLimit-Reset", 0))
            wait_s = max(reset_time - int(time.time()), 30) if reset_time else 60
            return ToolResult.fail(f"GitHub rate limit exceeded. Reset in ~{wait_s}s. Set GITHUB_TOKEN for higher limits.")

        if r.status_code == 422:
            return ToolResult.fail(f"GitHub search failed (422): query may be invalid. {r.text[:300]}")

        if not r.ok:
            return ToolResult.fail(f"GitHub API error {r.status_code}: {r.text[:300]}")

        data = r.json()
        total = data.get("total_count", 0)
        items_raw = data.get("items", [])
        if total > 1000:
            note = f"GitHub caps search results at 1000. Showing first {len(items_raw)}. Narrow your query for better precision."
        else:
            note = ""

        results: list[dict[str, Any]] = []
        for item in items_raw:
            entry: dict[str, Any] = {}
            if st == "repositories":
                entry = {
                    "full_name": item.get("full_name"),
                    "description": (item.get("description") or "")[:300],
                    "url": item.get("html_url"),
                    "stars": item.get("stargazers_count"),
                    "forks": item.get("forks_count"),
                    "language": item.get("language"),
                    "topics": item.get("topics", []),
                    "updated_at": item.get("updated_at"),
                    "license": item.get("license", {}).get("spdx_id") if item.get("license") else None,
                }
            elif st == "code":
                repo = item.get("repository", {})
                entry = {
                    "repo": repo.get("full_name"),
                    "repo_url": repo.get("html_url"),
                    "path": item.get("path"),
                    "file_url": item.get("html_url"),
                    "text_matches": [
                        {"fragment": m.get("fragment", ""), "object_url": m.get("object_url", "")}
                        for m in item.get("text_matches", [])[:5]
                    ],
                }
            elif st == "issues":
                entry = {
                    "repo": item.get("repository_url", "").rsplit("/", 2)[-2] + "/" + item.get("repository_url", "").rsplit("/", 1)[-1] if item.get("repository_url") else "",
                    "title": item.get("title")[:200],
                    "url": item.get("html_url"),
                    "state": item.get("state"),
                    "labels": [lb.get("name") for lb in item.get("labels", [])],
                    "comments": item.get("comments"),
                    "created_at": item.get("created_at"),
                    "body_snippet": (item.get("body") or "")[:300],
                }
            elif st == "commits":
                entry = {
                    "repo": item.get("repository", {}).get("full_name"),
                    "sha": item.get("sha", "")[:8],
                    "url": item.get("html_url"),
                    "message": (item.get("commit", {}).get("message", ""))[:200],
                    "author": item.get("commit", {}).get("author", {}).get("name"),
                    "date": item.get("commit", {}).get("author", {}).get("date"),
                }
            elif st == "topics":
                entry = {
                    "name": item.get("name"),
                    "display_name": item.get("display_name"),
                    "short_description": item.get("short_description"),
                    "created_by": item.get("created_by"),
                }
            elif st == "users":
                entry = {
                    "login": item.get("login"),
                    "url": item.get("html_url"),
                    "name": item.get("name"),
                    "bio": (item.get("bio") or "")[:200],
                    "public_repos": item.get("public_repos"),
                    "followers": item.get("followers"),
                }
            if entry:
                results.append(entry)

        return ToolResult.ok(data={
            "query": q,
            "search_type": st,
            "total_count": total,
            "returned": len(results),
            "results": results,
            "note": note,
            "usage_hint": (
                "搜索结果只包含元数据和代码片段。"
                "要查看完整文件内容，使用 raw.githubusercontent.com URL + web_read。"
                "如 web_read(url=\"https://raw.githubusercontent.com/OWNER/REPO/main/PATH\")"
            ),
        })

    except Exception as e:
        return ToolResult.fail(f"GitHub search error: {e}")


def register_github_tools(r) -> None:
    r.register("github_search", "retrieval", {
        "name": "github_search",
        "description": _load_desc("github_search"),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "GitHub 搜索查询。支持限定符：language:python、stars:>1000、org:facebook、path:src/、created:>2024-01-01。使用空格分隔多个限定符。"},
                "search_type": {
                    "type": "string",
                    "enum": ["repositories", "code", "issues", "commits", "topics", "users"],
                    "description": "搜索类型：repositories=仓库、code=代码内容、issues=Issue/PR、commits=提交、topics=主题标签、users=用户。默认 repositories。",
                },
                "sort": {"type": "string", "enum": ["stars", "forks", "updated", "comments", "created", ""], "description": "排序依据。repositories: stars/forks/updated；issues: comments/created/updated；commits: committer-date。"},
                "order": {"type": "string", "enum": ["desc", "asc"], "description": "排序方向。默认 desc。"},
                "per_page": {"type": "integer", "description": "每页结果数（最大 100，默认 20）。"},
            },
            "required": ["query"],
        },
    }, handle_github_search, concurrency_safe=True, read_only=True)
