from pathlib import Path


def test_dp_xunyi_skill_is_discoverable():
    from agent_os.skills.loader import SkillLoader

    skills_dir = Path(__file__).resolve().parents[1] / "skills"
    loader = SkillLoader(skills_dir=str(skills_dir))
    skills = loader.discover_all()

    assert "dp_xunyi_compat" in skills
    assert loader.resolve_skill("dp-xunyi-compat") is not None

    body = loader.get_skill_body("dp-xunyi-compat") or ""
    clinical_bottom = "".join(chr(value) for value in [20020, 24202, 24213, 32447])
    reliability_overview = "".join(chr(value) for value in [21487, 38752, 24615, 24635, 35272])
    evidence_chain = "".join(chr(value) for value in [35777, 25454, 38142])

    assert clinical_bottom in body
    assert reliability_overview in body
    assert evidence_chain in body


def test_pubmed_reliability_screen_returns_dp_fields():
    from agent_os.tools.pubmed import _score_pubmed_reliability

    result = _score_pubmed_reliability(
        pmid="34101387",
        title="ACR guideline",
        journal="Arthritis Rheumatol",
        date="2021",
        doi="10.1002/art.41752",
        publication_types=["Practice Guideline", "Systematic Review"],
        abstract="GRADE methodology was used.",
        full_text_available=True,
    )

    assert result["level"] == "high"
    assert result["score"] >= 78
    assert result["human_review_required"] is True
    assert result["scope"].endswith("not official GRADE")
    assert "source_score" in result["indicators"]
    assert "design_score" in result["indicators"]
    assert "weakest_links" in result
