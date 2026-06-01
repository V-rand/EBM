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

_pubmed_session = _requests.Session()
_pubmed_session.trust_env = False  # bypass proxy — academic APIs faster direct from China

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
    r = _pubmed_session.get(url, params=p, timeout=20,
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


# PMID efetch helpers — detailed structured metadata lookup
_PUBMED_PUBTYPES_USABLE_FOR_GRADE = frozenset({
    "practice guideline", "guideline", "consensus development conference",
    "systematic review", "meta-analysis", "randomized controlled trial",
    "controlled clinical trial", "clinical trial, phase iii",
})

_PUBMED_PUBTYPES_PROXY_ONLY = frozenset({
    "case reports", "observational study", "cohort study", "case-control study",
    "narrative review", "review", "comment", "editorial", "letter",
    "historical article", "news", "newspaper article", "twin study",
})


async def _fetch_by_pmid(pmid: str) -> ToolResult:
    """Fetch detailed structured metadata for a single PMID via efetch XML."""
    global _last_pubmed_call
    try:
        async with _pubmed_lock:
            elapsed = time.time() - _last_pubmed_call
            rate = 0.34 if NCBI_KEY else 0.35
            if elapsed < rate:
                await asyncio.sleep(rate - elapsed)
            _last_pubmed_call = time.time()

        loop = asyncio.get_running_loop()
        r = await loop.run_in_executor(
            None,
            lambda: _pubmed_api(f"{NCBI_BASE}/efetch.fcgi", {
                "db": "pubmed", "id": pmid, "retmode": "xml",
            }),
        )
        root = ET.fromstring(r.text)
        ns = {"ns": "http://www.w3.org/2005/Atom"}

        # Try PubmedArticle direct (standard PubMed XML)
        article = root.find(".//PubmedArticle")
        if article is None:
            return ToolResult.fail(f"PMID {pmid}: not found in PubMed")

        return ToolResult.ok(data=_parse_pubmed_article(article, pmid))
    except Exception as e:
        return ToolResult.fail(f"PMID {pmid} lookup failed: {e}")


async def _fetch_by_pmid_list(pmids: list[str]) -> ToolResult:
    """Fetch summaries for multiple PMIDs and assign grade_readiness per article."""
    global _last_pubmed_call
    try:
        async with _pubmed_lock:
            elapsed = time.time() - _last_pubmed_call
            rate = 0.34 if NCBI_KEY else 0.35
            if elapsed < rate:
                await asyncio.sleep(rate - elapsed)
            _last_pubmed_call = time.time()

        ids = ",".join(pmids)
        loop = asyncio.get_running_loop()
        r = await loop.run_in_executor(
            None,
            lambda: _pubmed_api(f"{NCBI_BASE}/esummary.fcgi", {
                "db": "pubmed", "id": ids, "retmode": "json",
            }),
        )
        data = r.json()
        results = data.get("result", {})
        uid_list = data.get("result", {}).get("uids", [])

        items = []
        for uid in uid_list:
            info = results.get(uid, {})
            pubtypes_raw = [pt.strip().lower() for pt in info.get("pubtype", [])]
            grade_status = _classify_grade_readiness(pubtypes_raw)
            items.append({
                "pmid": uid,
                "title": info.get("title", ""),
                "authors": [a.get("name", "") for a in info.get("authors", []) if a.get("name")],
                "journal": info.get("source", ""),
                "pubdate": info.get("pubdate", ""),
                "doi": info.get("elocationid", "").replace("doi: ", "") if "doi:" in str(info.get("elocationid", "")) else "",
                "publication_types": pubtypes_raw,
                "grade_readiness": grade_status,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
            })

        return ToolResult.ok(data={
            "results": items,
            "count": len(items),
            "mode": "pmid_lookup",
        })
    except Exception as e:
        return ToolResult.fail(f"PMID batch lookup failed: {e}")


def _parse_pubmed_article(article: ET.Element, pmid: str) -> dict:
    """Parse a PubmedArticle XML element into structured dict."""
    medline = article.find(".//MedlineCitation")
    art = article.find(".//Article")
    pubmed_data = article.find(".//PubmedData")

    # Title
    title_el = art.find(".//ArticleTitle") if art is not None else None
    title = ""
    if title_el is not None:
        title = "".join(title_el.itertext()).strip()

    # Authors
    authors = []
    author_list = art.find(".//AuthorList") if art is not None else None
    if author_list is not None:
        for au in author_list.findall("Author"):
            last = au.find("LastName")
            fore = au.find("ForeName")
            if last is not None:
                name = f"{last.text or ''} {(fore.text or '') if fore is not None else ''}".strip()
                if name:
                    authors.append(name)

    # Journal
    journal_el = art.find(".//Journal/Title") if art is not None else None
    journal = journal_el.text.strip() if journal_el is not None and journal_el.text else ""

    # PubDate
    pubdate_el = art.find(".//Journal/JournalIssue/PubDate") if art is not None else None
    pubdate = ""
    if pubdate_el is not None:
        year_el = pubdate_el.find("Year")
        if year_el is not None:
            pubdate = year_el.text or ""
        else:
            medline_date = pubdate_el.find("MedlineDate")
            if medline_date is not None:
                pubdate = (medline_date.text or "")[:4]

    # DOI
    doi = ""
    for eid in (art.findall(".//ELocationID") if art is not None else []):
        if eid.get("EIdType") == "doi":
            doi = (eid.text or "").strip()
            break
    if not doi:
        # Check ArticleIdList
        for aid in (pubmed_data.findall(".//ArticleId") if pubmed_data is not None else []):
            if aid.get("IdType") == "doi":
                doi = (aid.text or "").strip()
                break

    # PMCID
    pmcid = ""
    for aid in (pubmed_data.findall(".//ArticleId") if pubmed_data is not None else []):
        if aid.get("IdType") == "pmc":
            pmcid = (aid.text or "").strip()

    # Publication Types
    pubtypes_raw = []
    for pt in (art.findall(".//PublicationTypeList/PublicationType") if art is not None else []):
        if pt.text:
            pubtypes_raw.append(pt.text.strip().lower())

    # Abstract
    abstract_parts = []
    abstract_el = art.find(".//Abstract") if art is not None else None
    if abstract_el is not None:
        for child in abstract_el:
            txt = "".join(child.itertext()).strip()
            label = child.get("Label", "")
            if label:
                abstract_parts.append(f"{label}: {txt}")
            else:
                abstract_parts.append(txt)
    abstract = "\n".join(abstract_parts)

    # MeSH Terms
    mesh_terms = []
    mesh_list = medline.find(".//MeshHeadingList") if medline is not None else None
    if mesh_list is not None:
        for mh in mesh_list.findall("MeshHeading"):
            desc = mh.find("DescriptorName")
            if desc is not None and desc.text:
                mesh_terms.append(desc.text.strip())

    # Full text availability
    has_pmcid = bool(pmcid)

    # Grade readiness
    grade_status = _classify_grade_readiness(pubtypes_raw)

    return {
        "pmid": pmid,
        "title": title,
        "authors": authors,
        "author_count": len(authors),
        "journal": journal,
        "pubdate": pubdate,
        "doi": doi,
        "pmcid": pmcid if has_pmcid else None,
        "full_text_available": has_pmcid,
        "publication_types": pubtypes_raw,
        "abstract": abstract,
        "mesh_terms": mesh_terms,
        "grade_readiness": grade_status,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def _classify_grade_readiness(pubtypes: list[str]) -> dict:
    """Classify a publication into grade_ready / proxy_only / not_applicable
    based on PubMed publication types.

    This is a conservative metadata-level heuristic — it does NOT substitute
    for formal GRADE assessment.
    """
    pubtypes_lower = [pt.strip().lower() for pt in pubtypes]

    # Check for grade_ready candidates
    for pt in pubtypes_lower:
        for usable in _PUBMED_PUBTYPES_USABLE_FOR_GRADE:
            if usable in pt:
                return {
                    "status": "grade_ready",
                    "label": "可作为 GRADE 评估素材",
                    "note": "PubMed publication_type 表明该文献类型可支持 GRADE 评估。需人工审核全文确认。",
                    "needs_human_review": True,
                }

    # Check for proxy_only
    for pt in pubtypes_lower:
        for proxy in _PUBMED_PUBTYPES_PROXY_ONLY:
            if proxy in pt:
                return {
                    "status": "proxy_only",
                    "label": "仅作为背景参考",
                    "note": "该文献类型不适合直接用于 GRADE 评估，但可作为背景或间接证据。",
                    "needs_human_review": False,
                }

    # Default
    return {
        "status": "not_applicable",
        "label": "不直接映射 GRADE",
        "note": "基于 PubMed 元数据无法确定该文献的证据分级适用性。",
        "needs_human_review": True,
    }


async def handle_pubmed_search(
    query: str = "",
    author: str = "",
    title: str = "",
    journal: str = "",
    year: str = "",
    mesh: str = "",
    pmid: str = "",
    pmids: str = "",
    article_type: str = "",
    clinical_query: str = "",
    clinical_query_sensitivity: str = "broad",
    max_results: int = 10,
    **kw,
) -> ToolResult:
    """Search PubMed for biomedical literature with EBM-specific filters.

    Supports:
    - pmid / pmids: direct PMID lookup for detailed structured metadata
    - article_type: rct, systematic_review, meta_analysis, guideline, etc.
    - clinical_query: therapy, diagnosis, prognosis, etiology (PubMed Clinical Queries)
    - clinical_query_sensitivity: broad (more results) or narrow (higher precision)
    """
    global _last_pubmed_call

    # ---- PMID quick lookup (direct efetch) ----
    if pmid:
        return await _fetch_by_pmid(pmid.strip())
    if pmids:
        pmid_list = [p.strip() for p in pmids.replace(",", " ").split() if p.strip()]
        if not pmid_list:
            return ToolResult.fail("No valid PMIDs provided.")
        return await _fetch_by_pmid_list(pmid_list)

    # ---- Normal search ----
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
                "query": {"type": "string", "description": "搜索词，如 "metformin diabetes cardiovascular""},
                "article_type": {
                    "type": "string",
                    "description": "文章类型: systematic_review, rct, meta_analysis, guideline, review, observational, case_report",
                },
                "clinical_query": {
                    "type": "string",
                    "description": "临床查询: therapy, diagnosis, prognosis, etiology。自动应用 PubMed 验证的检索策略",
                },
                "pmid": {"type": "string", "description": "PMID 精确查找，如 pmid="34101387""},
                "pmids": {"type": "string", "description": "批量 PMID，如 pmids="34101387 37937763""},
                "author": {"type": "string", "description": "作者，如 author="Fauci AS""},
                "title": {"type": "string", "description": "标题词"},
                "journal": {"type": "string", "description": "期刊，如 journal="Lancet""},
                "year": {"type": "string", "description": "年份，如 year="2023""},
                "mesh": {"type": "string", "description": "MeSH 词，如 mesh="Diabetes Mellitus""},
                "clinical_query_sensitivity": {"type": "string", "description": "broad 或 narrow，默认 broad"},
                "max_results": {"type": "integer", "description": "结果数，默认 10"},
            },
            "required": [],
        },
    }, handle_pubmed_search, concurrency_safe=True, read_only=True)
