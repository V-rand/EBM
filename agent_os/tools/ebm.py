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

_ebm_session = _requests.Session()
_ebm_session.trust_env = False  # bypass proxy — academic APIs faster direct from China

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
            lambda: _ebm_session.get(
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
                lambda: _ebm_session.get(
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


# ============================================================================
# medRxiv search — health sciences preprint server
# ============================================================================

MEDRXIV_API = "https://api.medrxiv.org/details/medrxiv"
_medrxiv_lock = asyncio.Lock()

# medRxiv subject categories relevant to EBM
_MEDRXIV_CATEGORIES = {
    "cardiovascular": "cardiovascular medicine",
    "oncology": "oncology",
    "neurology": "neurology",
    "psychiatry": "psychiatry and clinical psychology",
    "epidemiology": "epidemiology",
    "infectious": "infectious diseases",
    "public_health": "public and global health",
    "endocrine": "endocrinology",
    "respiratory": "respiratory medicine",
    "surgery": "surgery",
    "anesthesia": "anesthesia",
    "dermatology": "dermatology",
    "gastroenterology": "gastroenterology",
    "rheumatology": "rheumatology",
    "nephrology": "nephrology",
    "urology": "urology",
    "ophthalmology": "ophthalmology",
    "pediatrics": "pediatrics",
    "geriatrics": "geriatric medicine",
    "emergency": "emergency medicine",
    "radiology": "radiology and imaging",
    "nutrition": "nutrition",
    "pharmacology": "pharmacology and therapeutics",
    "genetics": "genetic and genomic medicine",
    "immunology": "allergy and immunology",
    "pain": "pain management",
    "rehabilitation": "rehabilitation medicine and physical therapy",
    "sports": "sports medicine",
    "nursing": "nursing",
    "health_economics": "health economics",
    "health_informatics": "health informatics",
    "health_policy": "health systems and quality improvement",
    "medical_education": "medical education",
    "palliative": "palliative and end-of-life care",
    "addiction": "addiction medicine",
}


async def handle_medrxiv_search(
    date_from: str = "",
    date_to: str = "",
    query: str = "",
    category: str = "",
    max_results: int = 15,
    **kw,
) -> ToolResult:
    """Search medRxiv for health sciences preprints.

    medRxiv is the primary preprint server for clinical/health research.
    Uses the official medRxiv content API (no API key needed).
    """
    try:
        # Default date range: last 30 days
        if not date_to:
            date_to = time.strftime("%Y-%m-%d")
        if not date_from:
            # ~30 days ago
            date_from = time.strftime("%Y-%m-%d", time.localtime(time.time() - 30 * 86400))

        all_results: list[dict[str, Any]] = []
        cursor = 0
        seen_dois: set[str] = set()

        async with _medrxiv_lock:
            while len(all_results) < max_results:
                loop = asyncio.get_running_loop()
                api_url = f"{MEDRXIV_API}/{date_from}/{date_to}/{cursor}"
                r = await loop.run_in_executor(
                    None,
                    lambda: _ebm_session.get(api_url, timeout=20, headers={"User-Agent": "EBMAgentOS/1.0"}),
                )
                r.raise_for_status()
                data = r.json()

                collection = data.get("collection", [])
                msg = (data.get("messages") or [{}])[0]
                total = msg.get("total", 0)
                if not collection:
                    break

                query_lower = query.strip().lower() if query else ""
                category_key = category.strip().lower() if category else ""
                cat_full = _MEDRXIV_CATEGORIES.get(category_key, category_key)

                for paper in collection:
                    doi = paper.get("doi", "")
                    if doi in seen_dois:
                        continue
                    seen_dois.add(doi)

                    # Client-side text/category filter
                    if cat_full:
                        paper_cat = (paper.get("category") or "").lower()
                        if cat_full not in paper_cat:
                            continue
                    if query_lower:
                        title = (paper.get("title") or "").lower()
                        abstract = (paper.get("abstract") or "").lower()
                        if query_lower not in title and query_lower not in abstract:
                            continue

                    published = paper.get("published", "")
                    all_results.append({
                        "title": paper.get("title", ""),
                        "doi": paper.get("doi", ""),
                        "authors": paper.get("authors", ""),
                        "category": paper.get("category", ""),
                        "date": paper.get("date", ""),
                        "abstract": (paper.get("abstract") or "")[:1000],
                        "published_in": f"https://doi.org/{published}" if published else "",
                        "pub_status": "published" if published else "preprint",
                        "version": paper.get("version", ""),
                        "url": f"https://medrxiv.org/content/{doi}v{paper.get('version', '1')}" if doi else "",
                    })

                    if len(all_results) >= max_results:
                        break

                # Next page
                if cursor + len(collection) >= total:
                    break
                cursor += len(collection)

        return ToolResult.ok(data={
            "date_range": f"{date_from} to {date_to}",
            "total_in_range": total,
            "results": all_results,
            "count": len(all_results),
        })
    except Exception as e:
        return ToolResult.fail(f"medRxiv API error: {e}")


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
        "description": "Search ClinicalTrials.gov for interventional and observational studies. Filter by condition, intervention, status (recruiting|completed|terminated), and phase. Use with PICO framework to find trial evidence.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "condition": {"type": "string", "description": "疾病名称，如 'type 2 diabetes'"},
                "intervention": {"type": "string", "description": "干预名称，如 'metformin'"},
                "status": {"type": "string", "description": "可选：recruiting, completed, terminated"},
                "phase": {"type": "string", "description": "可选：1, 2, 3, 4"},
                "sponsor": {"type": "string", "description": "可选，赞助方"},
                "location": {"type": "string", "description": "可选，国家"},
                "year": {"type": "string", "description": "可选，年份"},
                "max_results": {"type": "integer", "description": "可选，默认 10"},
            },
            "required": [],
        },
    }, handle_clinical_trials_search, concurrency_safe=True, read_only=True)

    r.register("cochrane_search", "retrieval", {
        "name": "cochrane_search",
        "description": "Search Cochrane Database of Systematic Reviews (CDSR) — the gold standard for systematic reviews. Falls back to PubMed when Cochrane API is unavailable.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "topic": {"type": "string", "description": "Topic"},
                "year": {"type": "string", "description": "Year"},
                "max_results": {"type": "integer", "description": "Default 10"},
            },
            "required": ["query"],
        },
    }, handle_cochrane_search, concurrency_safe=True, read_only=True)

    r.register("medrxiv_search", "retrieval", {
        "name": "medrxiv_search",
        "description": "Search medRxiv preprints for the latest clinical/epidemiological research not yet indexed in PubMed. NOT peer-reviewed — check for subsequent journal publication before citing as strong evidence.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": '搜索词，如 COVID vaccine efficacy'},
                "category": {"type": "string", "description": "学科: cardiovascular, oncology, epidemiology, infectious, public_health"},
                "date_from": {"type": "string", "description": '起始日期，如 2026-01-01'},
                "date_to": {"type": "string", "description": '截止日期，如 2026-06-01'},
                "max_results": {"type": "integer", "description": "结果数，默认 15"},
            },
            "required": [],
        },
    }, handle_medrxiv_search, concurrency_safe=True, read_only=True)
