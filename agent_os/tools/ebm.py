"""
EBM (Evidence-Based Medicine) retrieval tools.

This module provides EBM-specific retrieval tools:
- ClinicalTrials.gov search — find interventional/observational trials
- Cochrane Library search — systematic reviews

GRADE evidence assessment and PICO framework are in skills/ (not tools),
following the design principle: tools = external API wrappers,
skills = model-level reasoning instructions.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import requests as _requests

from .registry import ToolResult

_DESC_DIR = Path(__file__).resolve().parent / "descriptions"

# ============================================================================
# ClinicalTrials.gov API
# ============================================================================

CTGOV_BASE = "https://clinicaltrials.gov/api/v2"
_last_ctgov_call: float = 0
_ctgov_lock = asyncio.Lock()
_CTGOV_RATE = 0.35  # ~3 req/sec for unauthenticated


def _load_desc(name: str) -> str:
    path = _DESC_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


async def _ctgov_api(params: dict[str, Any]) -> dict[str, Any] | None:
    """Call ClinicalTrials.gov API v2 studies endpoint."""
    global _last_ctgov_call
    try:
        async with _ctgov_lock:
            elapsed = time.time() - _last_ctgov_call
            if elapsed < _CTGOV_RATE:
                await asyncio.sleep(_CTGOV_RATE - elapsed)
            _last_ctgov_call = time.time()
        loop = asyncio.get_running_loop()
        r = await loop.run_in_executor(
            None,
            lambda: _requests.get(
                f"{CTGOV_BASE}/studies",
                params=params,
                timeout=20,
                headers={"User-Agent": "EBMAgentOS/1.0"},
            ),
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


async def handle_clinical_trials_search(
    query: str = "",
    condition: str = "",
    intervention: str = "",
    status: str = "",
    phase: str = "",
    sponsor: str = "",
    location: str = "",
    year: str = "",
    max_results: int = 10,
    **kw,
) -> ToolResult:
    """Search ClinicalTrials.gov for interventional/observational studies.

    Supports PICO-based search: condition + intervention.
    """
    try:
        # Build filter params using v2 API fields
        # See https://clinicaltrials.gov/api/v2/studies for available params
        params: dict[str, Any] = {
            "pageSize": min(max_results, 20),
            "format": "json",
            "countTotal": "true",
        }
        if query:
            params["query.term"] = query.strip()
        if condition:
            params["query.cond"] = condition.strip()
        if intervention:
            params["query.intr"] = intervention.strip()
        if sponsor:
            params["query.spons"] = sponsor.strip()
        if location:
            params["query.locn"] = location.strip()
        if year:
            params["filter.overallDate"] = f"RANGE[{year},{year}]" if "-" not in year else f"RANGE[{year}]"
        if status:
            status_map = {
                "recruiting": "RECRUITING",
                "active": "ACTIVE_NOT_RECRUITING",
                "completed": "COMPLETED",
                "terminated": "TERMINATED",
                "withdrawn": "WITHDRAWN",
            }
            params["filter.overallStatus"] = status_map.get(status.lower(), status)
        if phase:
            phase_map = {
                "1": "PHASE1",
                "2": "PHASE2",
                "3": "PHASE3",
                "4": "PHASE4",
                "early1": "EARLY_PHASE1",
            }
            params["filter.phase"] = phase_map.get(phase.lower(), phase)

        data = await _ctgov_api(params)
        if data is None:
            return ToolResult.fail("ClinicalTrials.gov API unavailable")

        studies = data.get("studies", [])
        total = data.get("totalCount", 0)

        results = []
        for study in studies:
            protocol = study.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            design_module = protocol.get("designModule", {})
            conditions_module = protocol.get("conditionsModule", {})
            arms_module = protocol.get("armsInterventionsModule", {})

            nct_id = id_module.get("nctId", "")
            title = id_module.get("briefTitle", "")
            overall_status = status_module.get("overallStatus", "")
            start_date = status_module.get("startDateStruct", {}).get("date", "")
            completion_date = status_module.get("completionDateStruct", {}).get("date", "")
            conditions = conditions_module.get("conditions", [])
            phase_info = design_module.get("phases", [])

            # Extract interventions
            interventions = []
            for arm in (arms_module.get("armGroups") or []):
                arm_type = arm.get("armType", "")
                arm_name = arm.get("label", "")
                interventions.append({"type": arm_type, "name": arm_name})

            results.append({
                "nct_id": nct_id,
                "title": title,
                "status": overall_status,
                "conditions": conditions,
                "phases": phase_info,
                "interventions": interventions,
                "start_date": start_date,
                "completion_date": completion_date,
                "url": f"https://clinicaltrials.gov/study/{nct_id}",
            })

        return ToolResult.ok(data={
            "query": condition or query or "",
            "total_count": total,
            "results": results,
            "count": len(results),
        })
    except Exception as e:
        return ToolResult.fail(f"ClinicalTrials.gov API error: {e}")


# ============================================================================
# Cochrane Library search (via PubMed / Crossref — Cochrane reviews indexed)
# ============================================================================

async def handle_cochrane_search(
    query: str = "",
    topic: str = "",
    year: str = "",
    max_results: int = 10,
    **kw,
) -> ToolResult:
    """Search Cochrane Database of Systematic Reviews (CDSR).

    Uses Cochrane's API and PubMed as fallback, since Cochrane reviews
    are indexed in both PubMed and Crossref.
    """
    try:
        # Primary: Cochrane API
        search_parts = [f'q={_url_encode(query)}'] if query else []
        if year:
            search_parts.append(f"field=Publication+Year&value={year}")
        search_url = f"https://www.cochranelibrary.com/api/search?{'&'.join(search_parts)}&limit={min(max_results, 10)}"

        try:
            loop = asyncio.get_running_loop()
            r = await loop.run_in_executor(
                None,
                lambda: _requests.get(
                    search_url,
                    timeout=15,
                    headers={"User-Agent": "EBMAgentOS/1.0", "Accept": "application/json"},
                ),
            )
            if r.status_code == 200:
                data = r.json()
                results = []
                for item in (data.get("results", data) if isinstance(data, dict) else (data or [])):
                    if isinstance(item, dict):
                        results.append({
                            "title": item.get("title", ""),
                            "authors": item.get("authors", ""),
                            "year": item.get("publicationYear", ""),
                            "doi": item.get("doi", ""),
                            "url": f"https://doi.org/{item.get('doi', '')}" if item.get("doi") else "",
                            "source": "Cochrane Library",
                        })
                if results:
                    return ToolResult.ok(data={
                        "query": query,
                        "results": results,
                        "count": len(results),
                    })
        except Exception:
            pass

        # Fallback: Use PubMed with Cochrane filter
        try:
            from .pubmed import handle_pubmed_search
            pubmed_result = await handle_pubmed_search(
                query=f"({query}) AND (Cochrane Database Syst Rev[Journal])",
                year=year,
                max_results=max_results,
            )
            if pubmed_result.success:
                data = pubmed_result.data or {}
                results = []
                for item in (data.get("results") or []):
                    results.append({
                        "title": item.get("title", ""),
                        "authors": item.get("authors", []),
                        "year": item.get("pubdate", ""),
                        "pmid": item.get("pmid", ""),
                        "doi": item.get("doi", ""),
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{item.get('pmid', '')}/",
                        "source": "PubMed (Cochrane)",
                    })
                return ToolResult.ok(data={
                    "query": query,
                    "total_count": data.get("total_count", 0),
                    "results": results,
                    "count": len(results),
                })
        except Exception:
            pass

        return ToolResult.ok(data={
            "query": query,
            "results": [],
            "count": 0,
            "note": "No results from Cochrane API; try pubmed_search with source=cochrane",
        })
    except Exception as e:
        return ToolResult.fail(f"Cochrane search error: {e}")


def _url_encode(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(s)



# ============================================================================
# Registration
# ============================================================================

def register_ebm_tools(r) -> None:
    """Register EBM-specific retrieval tools.

    Only tools that call external APIs are registered here.
    Reasoning helpers (GRADE, PICO) live in the corresponding SKILL files
    as model-level instructions — they don't need a dedicated tool.
    """
    r.register("clinical_trials", "retrieval", {
        "name": "clinical_trials",
        "description": "搜索 ClinicalTrials.gov 临床试验注册库。支持按疾病、干预、状态、分期筛选。用于查找临床试验证据。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "通用搜索词"},
                "condition": {"type": "string", "description": "疾病/状况名称（如 'diabetes type 2', 'breast cancer'）"},
                "intervention": {"type": "string", "description": "干预措施名称（如 'metformin', 'radiation therapy'）"},
                "status": {"type": "string", "description": "试验状态: recruiting, active, completed, terminated"},
                "phase": {"type": "string", "description": "试验分期: 1, 2, 3, 4, early1"},
                "sponsor": {"type": "string", "description": "赞助方"},
                "location": {"type": "string", "description": "地点/国家"},
                "year": {"type": "string", "description": "年份（如 '2022' 或 '2020-2024'）"},
                "max_results": {"type": "integer", "description": "最大结果数（默认 10，最大 20）"},
            },
            "required": [],
        },
    }, handle_clinical_trials_search, concurrency_safe=True, read_only=True)

    r.register("cochrane_search", "retrieval", {
        "name": "cochrane_search",
        "description": "搜索 Cochrane 系统评价数据库 (CDSR)。用于查找高质量系统评价/meta分析证据。将通过 Cochrane API 和 PubMed 双重检索。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "topic": {"type": "string", "description": "主题分类"},
                "year": {"type": "string", "description": "年份"},
                "max_results": {"type": "integer", "description": "最大结果数（默认 10）"},
            },
            "required": ["query"],
        },
    }, handle_cochrane_search, concurrency_safe=True, read_only=True)
