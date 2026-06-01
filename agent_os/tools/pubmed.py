"""
PubMed E-utilities API — biomedical literature search with EBM filters.

PubMed is the U.S. National Library of Medicine's database of biomedical literature:
- ~37 million citations (MEDLINE + PubMed Central + Bookshelf)
- Free, no API key required for moderate use
- NCBI E-utilities: esearch (search) + efetch (retrieve) + esummary (summaries)
- Rate limit: 3 requests/sec without key, 10/sec with API key (NCBI_API_KEY env var)

EBM enhancements:
- article_type: built-in PubMed filters for RCT, systematic review, meta-analysis, guideline
- clinical_query: PubMed Clinical Queries (therapy, diagnosis, prognosis, etiology)
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import requests as _requests

from .registry import ToolResult

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_KEY = os.getenv("NCBI_API_KEY", "")
_DESC_DIR = Path(__file__).resolve().parent / "descriptions"
_last_pubmed_call: float = 0  # NCBI asks 3 req/sec without key
_pubmed_lock = asyncio.Lock()


def _load_desc(name: str) -> str:
    path = _DESC_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _pubmed_api(url: str, params: dict[str, Any]) -> _requests.Response:
    """Sync NCBI API call via requests."""
    p = dict(params)
    p.setdefault("tool", "AgentOS")
    p.setdefault("email", "agentos@example.com")
    if NCBI_KEY:
        p["api_key"] = NCBI_KEY
    r = _requests.get(url, params=p, timeout=20,
                      headers={"User-Agent": "AgentOS/1.0"})
    r.raise_for_status()
    return r


# EBM Clinical Queries filters (PubMed Clinical Queries categories)
# These are validated PubMed search strategies for evidence-based medicine
_CLINICAL_QUERY_FILTERS = {
    "therapy": {
        "broad": "(clinical[Title/Abstract] AND trial[Title/Abstract]) OR clinical trials[MeSH Terms] OR clinical trial[Publication Type] OR random*[Title/Abstract] OR random allocation[MeSH Terms] OR therapeutic use[MeSH Subheading]",
        "narrow": "(randomized controlled trial[Publication Type] OR (randomized[Title/Abstract] AND controlled[Title/Abstract] AND trial[Title/Abstract]))",
    },
    "diagnosis": {
        "broad": "sensitivity[Title/Abstract] OR specificity[Title/Abstract] OR diagnostic[Title/Abstract] OR diagnosis[MeSH Subheading] OR diagnostic use[MeSH Subheading] OR predictive value[Title/Abstract] OR ROC curve[MeSH Terms]",
        "narrow": "(sensitivity[Title/Abstract] AND specificity[Title/Abstract]) OR (predictive value*[Title/Abstract]) OR (ROC curve[MeSH Terms])",
    },
    "prognosis": {
        "broad": "incidence[MeSH Terms] OR mortality[MeSH Terms] OR follow-up studies[MeSH Terms] OR prognosis[MeSH Subheading] OR predict*[Title/Abstract] OR course[Title/Abstract]",
        "narrow": "(prognosis[MeSH Subheading] OR survival analysis[MeSH Terms]) OR (cohort studies[MeSH Terms]) OR (follow-up studies[MeSH Terms])",
    },
    "etiology": {
        "broad": "risk[Title/Abstract] OR cohort studies[MeSH Terms] OR case-control studies[MeSH Terms] OR odds ratio*[Title/Abstract] OR relative risk[Title/Abstract] OR etiology[MeSH Subheading]",
        "narrow": "(cohort studies[MeSH Terms] OR case-control studies[MeSH Terms]) OR (risk[Title/Abstract] AND (odds ratio*[Title/Abstract] OR relative risk[Title/Abstract]))",
    },
}

# PubMed article type filters (standard PubMed publication type filters)
_ARTICLE_TYPE_FILTERS = {
    "rct": "randomized controlled trial[Publication Type]",
    "controlled_clinical_trial": "controlled clinical trial[Publication Type]",
    "clinical_trial": "clinical trial[Publication Type] OR clinical trial, phase i[Publication Type] OR clinical trial, phase ii[Publication Type] OR clinical trial, phase iii[Publication Type] OR clinical trial, phase iv[Publication Type]",
    "systematic_review": "systematic review[Publication Type] OR systematic reviews as topic[MeSH Terms]",
    "meta_analysis": "meta-analysis[Publication Type] OR meta-analysis as topic[MeSH Terms]",
    "guideline": "practice guideline[Publication Type] OR guideline[Publication Type] OR guidelines as topic[MeSH Terms]",
    "review": "review[Publication Type] OR literature review[Publication Type] OR narrative review[Publication Type]",
    "observational": "observational study[Publication Type] OR cohort studies[MeSH Terms] OR case-control studies[MeSH Terms]",
    "case_report": "case reports[Publication Type]",
    "editorial": "editorial[Publication Type]",
    "letter": "letter[Publication Type]",
    "comment": "comment[Publication Type]",
}


async def handle_pubmed_search(
    query: str = "",
    author: str = "",
    title: str = "",
    journal: str = "",
    year: str = "",
    mesh: str = "",
    article_type: str = "",
    clinical_query: str = "",
    clinical_query_sensitivity: str = "broad",
    max_results: int = 10,
    **kw,
) -> ToolResult:
    """Search PubMed for biomedical literature with EBM-specific filters.

    Supports:
    - article_type: rct, systematic_review, meta_analysis, guideline, etc.
    - clinical_query: therapy, diagnosis, prognosis, etiology (PubMed Clinical Queries)
    - clinical_query_sensitivity: broad (more results) or narrow (higher precision)
    """
    global _last_pubmed_call

    # Build query using PubMed field tags
    parts: list[str] = []
    if author:
        parts.append(f"{author}[Author]")
    if title:
        parts.append(f"{title}[Title]")
    if journal:
        parts.append(f"{journal}[Journal]")
    if mesh:
        parts.append(f"{mesh}[MeSH Terms]")
    if year:
        parts.append(f"{year}[Publication Date]")
    if query:
        parts.append(f"({query})")

    full_query = " AND ".join(parts) if parts else query
    if not full_query:
        return ToolResult.fail("At least one of query, author, title, journal, mesh, or year is required.")

    # Apply article_type filter (PubMed built-in publication type)
    applied_filters: list[str] = []
    if article_type:
        at_key = article_type.strip().lower().replace("-", "_")
        at_filter = _ARTICLE_TYPE_FILTERS.get(at_key)
        if at_filter:
            full_query = f"({full_query}) AND ({at_filter})"
            applied_filters.append(f"article_type={article_type}")
        else:
            # Try as raw PubMed filter string
            full_query = f"({full_query}) AND ({article_type}[Publication Type])"
            applied_filters.append(f"article_type={article_type}")

    # Apply Clinical Queries filter
    if clinical_query:
        cq_key = clinical_query.strip().lower()
        cq_filters = _CLINICAL_QUERY_FILTERS.get(cq_key)
        if cq_filters:
            sensitivity = clinical_query_sensitivity.strip().lower()
            if sensitivity not in ("broad", "narrow"):
                sensitivity = "broad"
            cq_string = cq_filters[sensitivity]
            full_query = f"({full_query}) AND ({cq_string})"
            applied_filters.append(f"clinical_query={clinical_query}({sensitivity})")

    # Step 1: search for IDs
    retmax = min(max_results, 20)
    search_params: dict[str, Any] = {
        "db": "pubmed", "term": full_query, "retmax": retmax,
        "retmode": "json", "sort": "relevance",
    }

    try:
        async with _pubmed_lock:
            elapsed = time.time() - _last_pubmed_call
            rate = 0.34 if NCBI_KEY else 0.35  # ~3 req/sec
            if elapsed < rate:
                await asyncio.sleep(rate - elapsed)
            _last_pubmed_call = time.time()

        loop = asyncio.get_running_loop()
        r = await loop.run_in_executor(None, _pubmed_api, f"{NCBI_BASE}/esearch.fcgi", search_params)
        search_data = r.json()
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        total = int(search_data.get("esearchresult", {}).get("count", 0))

        if not id_list:
            return ToolResult.ok(data={
                "query": full_query, "total_count": 0, "results": [], "count": 0,
                "filters_applied": applied_filters,
            })

        # Step 2: fetch summaries
        ids = ",".join(id_list)
        summary_params: dict[str, Any] = {
            "db": "pubmed", "id": ids, "retmode": "json",
        }
        r2 = await loop.run_in_executor(None, _pubmed_api, f"{NCBI_BASE}/esummary.fcgi", summary_params)
        summary_data = r2.json()
        summaries = summary_data.get("result", {})

        results = []
        for pmid in id_list:
            info = summaries.get(pmid, {})
            authors_raw = info.get("authors", [])
            authors = [a.get("name", "") for a in authors_raw if a.get("name")]
            results.append({
                "pmid": pmid,
                "title": info.get("title", ""),
                "authors": authors,
                "author_count": len(authors),
                "journal": info.get("source", ""),
                "pubdate": info.get("pubdate", ""),
                "doi": info.get("elocationid", "").replace("doi: ", "") if "doi:" in str(info.get("elocationid", "")) else "",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })

        return ToolResult.ok(data={
            "query": full_query,
            "total_count": total,
            "results": results,
            "count": len(results),
            "filters_applied": applied_filters,
        })
    except Exception as e:
        return ToolResult.fail(f"PubMed API error: {e}")


def register_pubmed_tools(r) -> None:
    r.register("pubmed_search", "retrieval", {
        "name": "pubmed_search",
        "description": _load_desc("pubmed_search"),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "通用搜索查询（关键词）"},
                "author": {"type": "string", "description": "作者名（如 \"Fauci AS\"）"},
                "title": {"type": "string", "description": "标题关键词"},
                "journal": {"type": "string", "description": "期刊名（如 \"Nature\"、\"Lancet\"、\"BMJ\"）"},
                "year": {"type": "string", "description": "发表年份（如 \"2023\"）"},
                "mesh": {"type": "string", "description": "MeSH 主题词（如 \"Diabetes Mellitus\"）"},
                "article_type": {
                    "type": "string",
                    "description": "文章类型过滤: rct（随机对照试验）, systematic_review（系统评价）, meta_analysis（荟萃分析）, guideline（临床指南）, controlled_clinical_trial（对照临床试验）, review（综述）, observational（观察性研究）, case_report（病例报告）",
                },
                "clinical_query": {
                    "type": "string",
                    "description": "EBM Clinical Queries 分类: therapy（治疗）, diagnosis（诊断）, prognosis（预后）, etiology（病因）。使用经验证的 PubMed 检索策略过滤",
                },
                "clinical_query_sensitivity": {
                    "type": "string",
                    "description": "Clinical Queries 灵敏度: broad（宽泛-更多结果）或 narrow（精确-更少但更相关），默认 broad",
                },
                "max_results": {"type": "integer", "description": "最大结果数（默认 10，最大 20）"},
            },
            "required": [],
        },
    }, handle_pubmed_search, concurrency_safe=True, read_only=True)
