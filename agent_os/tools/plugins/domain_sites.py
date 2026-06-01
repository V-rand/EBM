"""
domain_sites tool — authoritative site directory for domain-locked web_search.

Reads skills/domain_sites/sites.yaml and returns site: patterns
for the requested domain, so the model can lock searches to authoritative sources.
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any

from agent_os.tools.registry import ToolResult

_SITES_PATH = Path(__file__).resolve().parent.parent.parent.parent / "skills" / "domain_sites" / "sites.yaml"
_sites_cache: dict[str, list[str]] | None = None


def _load_sites() -> dict[str, list[str]]:
    global _sites_cache
    if _sites_cache is not None:
        return _sites_cache
    if _SITES_PATH.exists():
        with open(_SITES_PATH, encoding="utf-8") as f:
            _sites_cache = yaml.safe_load(f) or {}
    else:
        _sites_cache = {}
    return _sites_cache


async def handle_domain_sites(domain: str = "", **kw: Any) -> ToolResult:
    sites = _load_sites()
    domain = domain.strip()

    if not domain:
        return ToolResult.ok(data={
            "available_domains": sorted(sites.keys()),
            "hint": "Call with a specific domain, e.g. domain_sites(domain=\"legal_cn\")",
        })

    if domain not in sites:
        return ToolResult.ok(data={
            "error": f"Unknown domain: {domain}",
            "available_domains": sorted(sites.keys()),
            "hint": "Choose from the available domains above.",
        })

    domain_list = sites[domain]
    site_ops = [f"site:{s}" for s in domain_list]
    hint = f'拼入 web_search query: "{" OR ".join(site_ops)}"'
    return ToolResult.ok(data={
        "domain": domain,
        "sites": domain_list,
        "site_operators": site_ops,
        "hint": hint,
    })


def register(r) -> None:
    r.register(
        "domain_sites",
        "reasoning",
        {
            "name": "domain_sites",
            "description": (
                "Look up authoritative website domains for a given research domain. "
                "Returns site: operators for hard domain-locked web_search.\n\n"
                "法律: legal_cn_judicial, legal_cn_legislative, legal_cn_business, "
                "legal_cn_labor, legal_cn_professional, legal_cn_admin, legal_cn_regulatory, "
                "legal_en, legal_historical\n"
                "政府: gov_cn_economic, gov_cn_health, gov_cn_science, gov_cn_infra, "
                "gov_cn_rural, gov_cn_culture, government_en\n"
                "医疗: medical, medical_cn, biomedical\n"
                "计算机: cs_conferences\n"
                "金融: finance, finance_cn\n"
                "自然科学: biology, materials, chemistry, environment, mathematics, physics\n"
                "通用: elite_multidisciplinary, academic, patents, standards, "
                "film_media, geography, historical, encyclopedia, common_knowledge"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": (
                            "Research domain key. Choose from: legal_cn_judicial, "
                            "legal_cn_legislative, legal_cn_business, legal_cn_labor, "
                            "legal_cn_professional, legal_cn_admin, legal_cn_regulatory, "
                            "legal_en, legal_historical, medical, medical_cn, biomedical, "
                            "cs_conferences, finance, finance_cn, gov_cn_economic, "
                            "gov_cn_health, gov_cn_science, gov_cn_infra, gov_cn_rural, "
                            "gov_cn_culture, government_en, biology, materials, chemistry, "
                            "environment, mathematics, physics, elite_multidisciplinary, "
                            "academic, patents, standards, film_media, geography, "
                            "historical, encyclopedia, common_knowledge. "
                            "Leave empty to list all available domains."
                        ),
                    },
                },
                "required": [],
            },
        },
        handle_domain_sites,
        concurrency_safe=True,
        read_only=True,
    )
