from __future__ import annotations

from mary.learning.evidence import (
    EvidenceBundle,
    EvidenceItem,
    EvidenceValidator,
)


def _bundle(*, dynamic: bool = False) -> EvidenceBundle:
    return EvidenceBundle(
        query=(
            "What is the latest grounded status?"
            if dynamic
            else "What does the evidence support?"
        ),
        dynamic_query=dynamic,
        items=[
            EvidenceItem(
                title="Official source",
                url="https://example.com/official",
                content="The official source supports the bounded claim.",
                source_type="web",
                grounding={
                    "overall": 0.95,
                    "primary_source": True,
                    "observed_date": "2026-09-17",
                    "stale_for_dynamic_query": False,
                },
                evaluation={
                    "recommendation": "accept",
                    "confidence": 0.95,
                },
            )
        ],
    )


def test_research_synthesis_prompt_is_evidence_only_and_conflict_aware():
    prompt = EvidenceValidator()._build_synthesis_prompt(
        _bundle()
    )

    assert "using ONLY the approved research evidence" in prompt
    assert "Every factual claim must be supported" in prompt
    assert "Prefer primary/official evidence when sources disagree" in prompt
    assert "If evidence is insufficient or conflicting, say so plainly" in prompt
    assert "Do not use outside model knowledge" in prompt


def test_dynamic_research_prompt_requires_newest_strong_evidence():
    prompt = EvidenceValidator()._build_synthesis_prompt(
        _bundle(dynamic=True)
    )

    assert "This is a current/dynamic query" in prompt
    assert "Use the newest strong evidence" in prompt
    assert "Older sources are historical context only" in prompt


def test_evidence_audit_requires_correction_or_qualification():
    validator = EvidenceValidator()
    prompt = validator._build_prompt(
        bundle=_bundle(),
        draft="An unsupported draft claim.",
    )

    assert "Check every factual claim" in prompt
    assert "Remove, correct, or explicitly qualify" in prompt
    assert "If evidence is insufficient, say what is uncertain instead of guessing" in prompt
    assert "Do not add outside facts from your own model knowledge" in prompt
