"""
EBM (Evidence-Based Medicine) tools — clinical trials, Cochrane, GRADE, PICO.

This module provides EBM-specific tools for:
- ClinicalTrials.gov search — find interventional/observational trials
- Cochrane Library search — systematic reviews
- Evidence level evaluation (GRADE / Oxford CEBM)
- PICO framework formulation for clinical questions
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
        # Build search expression (advanced query syntax)
        parts: list[str] = []
        if query:
            parts.append(f"({query})")
        if condition:
            parts.append(f"AREA[ConditionDisease] {condition}")
        if intervention:
            parts.append(f"AREA[InterventionName] {intervention}")
        if sponsor:
            parts.append(f"AREA[Sponsor] {sponsor}")
        if location:
            parts.append(f"AREA[LocationCountry] {location}")
        if year:
            parts.append(f"AREA[StudyFirstPostDate] EXPAND[{year}]")

        query_expr = " AND ".join(parts) if parts else ""

        # Build filter params
        params: dict[str, Any] = {
            "pageSize": min(max_results, 20),
            "format": "json",
            "countTotal": "true",
        }
        if query_expr:
            params["query.term"] = query_expr
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
            "query": query_expr or query,
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
# Evidence Level Checker — GRADE / Oxford CEBM
# ============================================================================

_GRADE_TABLE = {
    "high": {
        "label": "高质量 (High)",
        "description": "进一步研究几乎不可能改变对效应估计的信度",
        "examples": ["设计良好的多中心RCT", "有足够把握度的RCT荟萃分析"],
    },
    "moderate": {
        "label": "中等质量 (Moderate)",
        "description": "进一步研究可能对效应估计的信度产生重要影响，且可能改变估计值",
        "examples": ["有局限性的RCT", "高质量观察性研究", "RCT的荟萃分析但存在异质性"],
    },
    "low": {
        "label": "低质量 (Low)",
        "description": "进一步研究很可能对效应估计的信度产生重要影响，且很可能改变估计值",
        "examples": ["观察性研究", "病例对照研究", "有重大局限性的RCT"],
    },
    "very_low": {
        "label": "极低质量 (Very Low)",
        "description": "对效应估计的任何信度都非常不确定",
        "examples": ["病例系列", "个案报道", "专家意见", "体外研究"],
    },
}

_OXFORD_CEBM_LEVELS = [
    {"level": "1a", "label": "同质性RCT的系统评价", "therapy": True, "prognosis": False},
    {"level": "1b", "label": "单个RCT（窄置信区间）", "therapy": True, "prognosis": False},
    {"level": "1c", "label": "全或无（治疗前全部死亡/治疗后部分存活）", "therapy": True, "prognosis": False},
    {"level": "2a", "label": "同质性队列研究的系统评价", "therapy": True, "prognosis": True},
    {"level": "2b", "label": "单个队列研究（包括低质量RCT）", "therapy": True, "prognosis": True},
    {"level": "2c", "label": "结局研究/生态学研究", "therapy": False, "prognosis": True},
    {"level": "3a", "label": "同质性病例对照研究的系统评价", "therapy": True, "prognosis": False},
    {"level": "3b", "label": "单个病例对照研究", "therapy": True, "prognosis": False},
    {"level": "4", "label": "病例系列/低质量队列或病例对照研究", "therapy": True, "prognosis": True},
    {"level": "5", "label": "专家意见（无严格评价或基于基础医学）", "therapy": True, "prognosis": True},
]


async def handle_evidence_level(
    study_type: str = "",
    design: str = "",
    limitations: str = "",
    **kw,
) -> ToolResult:
    """Evaluate the level of evidence for a clinical study using GRADE framework.

    Given study type and design features, returns GRADE quality rating
    and Oxford CEBM level with rationale.
    """
    study_type = str(study_type or "").strip().lower()
    design = str(design or "").strip().lower()
    limitations = str(limitations or "").strip().lower()

    # Determine GRADE starting level
    grade_start = "high"
    grade_reasons: list[str] = []
    downgrades = 0
    upgrades = 0

    # Type-based GRADE start
    if study_type in {"rct", "randomized controlled trial", "randomized"}:
        grade_start = "high"
        grade_reasons.append("起始为高质量（RCT）")
    elif study_type in {"observational", "cohort", "prospective cohort"}:
        grade_start = "low"
        grade_reasons.append("起始为低质量（观察性研究）")
    elif study_type in {"case-control", "retrospective"}:
        grade_start = "low"
        grade_reasons.append("起始为低质量（病例对照/回顾性研究）")
    elif study_type in {"case series", "case report", "expert opinion", "narrative review"}:
        grade_start = "very_low"
        grade_reasons.append("起始为极低质量（病例系列/专家意见）")
    elif study_type in {"systematic review", "meta-analysis"}:
        grade_start = "high"
        grade_reasons.append("系统评价/荟萃分析，基于纳入研究质量判定")
    elif study_type in {"guideline", "clinical practice guideline"}:
        grade_start = "moderate"
        grade_reasons.append("临床实践指南，依据证据基础判定")
    else:
        grade_start = "low"
        grade_reasons.append("未明确研究类型，默认起始为低质量")

    # Check for downgrade factors
    if "bias" in limitations or "risk of bias" in limitations:
        downgrades += 1
        grade_reasons.append("降级：偏倚风险高")
    if "inconsistency" in limitations or "heterogeneity" in limitations:
        downgrades += 1
        grade_reasons.append("降级：结果不一致/异质性大")
    if "indirectness" in limitations or "indirect" in limitations:
        downgrades += 1
        grade_reasons.append("降级：间接证据")
    if "imprecision" in limitations or "wide confidence interval" in limitations:
        downgrades += 1
        grade_reasons.append("降级：精度不足/置信区间宽")
    if "publication bias" in limitations or "reporting bias" in limitations:
        downgrades += 1
        grade_reasons.append("降级：发表偏倚")

    # Check for upgrade factors (for observational)
    if study_type in {"observational", "cohort", "case-control"}:
        if "large effect" in limitations or "large" in limitations:
            upgrades += 1
            grade_reasons.append("升级：效应量大（RR>2或<0.5）")
        if "dose response" in limitations or "dose-response" in limitations:
            upgrades += 1
            grade_reasons.append("升级：剂量-反应关系")
        if "confounding" in limitations and "negative" in limitations:
            upgrades += 1
            grade_reasons.append("升级：残余混杂偏倚减弱效应（实际效应可能更大）")

    # Calculate final grade
    grade_order = ["high", "moderate", "low", "very_low"]
    start_idx = grade_order.index(grade_start)
    final_idx = min(start_idx + downgrades - upgrades, len(grade_order) - 1)
    final_idx = max(final_idx, 0)
    final_grade = grade_order[final_idx]

    # Find matching Oxford CEBM level
    matching_levels = []
    for level in _OXFORD_CEBM_LEVELS:
        if level["label"].lower().startswith(design[:10]):
            matching_levels.append(level["level"])
    if not matching_levels:
        # Map study type to approximate level
        type_level_map = {
            "rct": "1b", "randomized": "1b",
            "cohort": "2b", "prospective cohort": "2b",
            "case-control": "3b", "retrospective": "3b",
            "case series": "4", "case report": "4",
            "systematic review": "1a", "meta-analysis": "1a",
            "expert opinion": "5",
        }
        matching_levels = [type_level_map.get(study_type, "—")]

    return ToolResult.ok(data={
        "grade_quality": _GRADE_TABLE[final_grade]["label"],
        "grade_description": _GRADE_TABLE[final_grade]["description"],
        "grade_reasons": grade_reasons,
        "downgrades": downgrades,
        "upgrades": upgrades,
        "oxford_cebm_level": matching_levels[0] if matching_levels else "—",
        "grade_table": _GRADE_TABLE,
        "oxford_table": _OXFORD_CEBM_LEVELS,
        "study_type": study_type,
        "design": design,
    })


# ============================================================================
# PICO Analysis Tool
# ============================================================================

async def handle_pico_analysis(
    clinical_question: str = "",
    **kw,
) -> ToolResult:
    """Parse a clinical question into PICO components.

    PICO:
    - P: Patient/Population/Problem
    - I: Intervention/Exposure
    - C: Comparison/Control
    - O: Outcome

    If question is provided, guides the user on how to structure it.
    Returns a PICO template for the model to fill via research_state.
    """
    if not clinical_question.strip():
        return ToolResult.ok(data={
            "pico": {
                "P": "Patient/Population/Problem — 患者群体、疾病或状况",
                "I": "Intervention/Exposure — 干预措施、诊断方法或暴露因素",
                "C": "Comparison/Control — 对照措施（安慰剂、标准治疗、无干预）",
                "O": "Outcome — 临床结局指标（有效性、安全性、生活质量等）",
            },
            "template": "PICO 框架构建完成。请将分解后的 PICO 元素写入 research_state 供后续检索使用。",
            "question_types": [
                "therapy/treatment — 治疗疗效",
                "diagnosis — 诊断准确性",
                "prognosis — 预后评估",
                "etiology/harm — 病因/危害",
                "prevention — 预防措施",
                "economic — 卫生经济学",
            ],
            "example": {
                "question": "在2型糖尿病患者中，SGLT-2抑制剂相比二甲双胍是否能更有效降低心血管事件风险？",
                "p": "2型糖尿病患者",
                "i": "SGLT-2抑制剂",
                "c": "二甲双胍",
                "o": "主要不良心血管事件（MACE）发生率",
            },
        })

    # Parse user's clinical question into PICO
    q = clinical_question.strip()
    pico = {"P": "", "I": "", "C": "", "O": ""}
    question_type = "therapy/treatment"

    # Extract P: look for "in patients with", "in adults with", etc.
    p_match = re.search(
        r'in\s+(patients?\s+with|adults?\s+with|children?\s+with|subjects?\s+with|participants?\s+with|population\s+|people\s+with)\s+(.+?)(?:,|\.|;|who\s+are|that\s+are|where|and\s+the|$|\s+treated|\s+compared|\s+receiving|\s+received)',
        q, re.IGNORECASE
    )
    if p_match:
        pico["P"] = p_match.group(2).strip()

    # Try Chinese P
    if not pico["P"]:
        p_match = re.search(r'(患有|诊断[为]?|合并|伴有)\s*(.+?)(?:的患者|的病人|人群|,|，|\.|。|$)', q)
        if p_match:
            pico["P"] = p_match.group(2).strip()

    # Extract I: look for treatment/intervention
    i_patterns = [
        r'(?:treated with|receiving|receives|given|assigned to|intervention\s*:?\s*|exposed to)\s+(.+?)(?:,|\.|;|compared|\s+vs|\s+versus|\s+or\s+no\s+treatment|\s+or\s+placebo|\s+and\s+compared|$)',
        r'(?:用|给予|接受|采用|使用)\s*(.+?)(?:治疗|干预|处理|,|，|。|$|与|对比|比较)',
    ]
    for pat in i_patterns:
        i_match = re.search(pat, q, re.IGNORECASE)
        if i_match:
            pico["I"] = i_match.group(1).strip()
            break

    # Extract C: look for comparison
    c_patterns = [
        r'(?:compared with|versus|vs\.?\s*|compared to)\s+(.+?)(?:,|\.|;|in\s+terms\s+of|on\s+|for\s+|with\s+respect\s+to|$)',
        r'(?:与|对比|比较|vs)\s*(.+?)(?:相比|对比|比较|,|，|。|$|在|对)',
    ]
    for pat in c_patterns:
        c_match = re.search(pat, q, re.IGNORECASE)
        if c_match:
            pico["C"] = c_match.group(1).strip()
            break

    # If no explicit comparison, default to placebo/standard
    if not pico["C"]:
        if "placebo" in q.lower():
            pico["C"] = "安慰剂 (placebo)"
        elif "standard" in q.lower() or "usual" in q.lower() or "conventional" in q.lower():
            pico["C"] = "标准治疗 (standard care)"
        else:
            pico["C"] = "对照措施（待明确）"

    # Extract O: outcome
    o_patterns = [
        r'(?:in\s+terms\s+of|to\s+(?:reduce|improve|prevent|decrease|increase|assess|evaluate|determine)|outcomes?\s*(?:include|:)?|with\s+respect\s+to|measured\s+by)\s+(.+?)$',
        r'(?:能否|是否|可以|能否有效|能不能)\s*(.+?)(?:\?|？|$)',
        r'(?:降低|减少|提高|改善|预防|评估|评价)\s*(.+?)(?:\?|？|$)',
    ]
    for pat in o_patterns:
        o_match = re.search(pat, q, re.IGNORECASE)
        if o_match:
            pico["O"] = o_match.group(1).strip()
            break

    # Determine question type
    for keyword, qtype in [
        ("diagnos", "diagnosis"),
        ("prognos", "prognosis"),
        ("etiolog", "etiology/harm"),
        ("caus", "etiology/harm"),
        ("risk factor", "etiology/harm"),
        ("prevent", "prevention"),
        ("screen", "prevention"),
        ("economic", "economic"),
        ("cost", "economic"),
    ]:
        if keyword in q.lower():
            question_type = qtype
            break

    return ToolResult.ok(data={
        "pico": pico,
        "question_type": question_type,
        "question": q,
        "original_parsed": bool(pico["P"] or pico["I"] or pico["O"]),
        "template": "PICO 已初步解析。请 review 各个元素是否准确，必要时用 research_state 修正后开始检索。",
    })


# ============================================================================
# Registration
# ============================================================================

def register_ebm_tools(r) -> None:
    """Register all EBM-specific tools."""
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

    r.register("evidence_level", "reasoning", {
        "name": "evidence_level",
        "description": "评估临床研究证据等级（GRADE 框架 + Oxford CEBM 分级）。输入研究类型和局限性信息，返回证据质量评级和理由。",
        "parameters": {
            "type": "object",
            "properties": {
                "study_type": {
                    "type": "string",
                    "description": "研究类型：rct, cohort, case-control, case series, systematic review, meta-analysis, guideline, expert opinion",
                },
                "design": {
                    "type": "string",
                    "description": "设计描述（如 'randomized double-blind', 'prospective cohort'）",
                },
                "limitations": {
                    "type": "string",
                    "description": "局限性描述，包含关键词如 'risk of bias', 'inconsistency', 'heterogeneity', 'indirectness', 'imprecision', 'publication bias', 'large effect', 'dose response'",
                },
            },
            "required": ["study_type"],
        },
    }, handle_evidence_level, concurrency_safe=True, read_only=True)

    r.register("pico_analysis", "reasoning", {
        "name": "pico_analysis",
        "description": "PICO 临床问题框架构建。输入临床问题，自动解析为 P（患者/问题）、I（干预）、C（对照）、O（结局）四个要素。帮助规划循证医学检索策略。",
        "parameters": {
            "type": "object",
            "properties": {
                "clinical_question": {"type": "string", "description": "临床问题描述。留空则返回 PICO 框架说明和示例。"},
            },
            "required": [],
        },
    }, handle_pico_analysis, concurrency_safe=True, read_only=True)
