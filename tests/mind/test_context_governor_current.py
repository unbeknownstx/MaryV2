from __future__ import annotations

from mary.mind.context_governor import ContextEvidenceGovernor


def test_context_governor_normalizes_lanes_and_preserves_whole_records() -> None:
    governor = ContextEvidenceGovernor(
        total_characters=2000,
        lane_budgets={
            "world": 500,
            "plans": 500,
            "skills": 500,
            "compute": 500,
            "knowledge": 1000,
        },
    )
    world = [{"id": "belief-1", "value": "main", "authority": "canonical"}]
    large = "x" * 700
    knowledge = [
        {"id": "doc-1", "snippet": large, "score": 1.0},
        {"id": "doc-2", "snippet": large, "score": 0.9},
    ]

    selected, report = governor.govern({
        "KNOWLEDGE": knowledge,
        "World": world,
    })

    assert selected["world"] == world
    assert len(selected["knowledge"]) == 1
    assert selected["knowledge"][0]["snippet"] == large
    assert report["used_characters"] <= report["total_budget_characters"]
    assert [item["lane"] for item in report["lanes"]] == ["world", "knowledge"]


def test_context_governor_reserves_operational_lanes_before_reference_text() -> None:
    governor = ContextEvidenceGovernor(
        total_characters=2000,
        lane_budgets={
            "world": 700,
            "plans": 700,
            "skills": 700,
            "compute": 700,
            "knowledge": 1800,
        },
    )
    selected, report = governor.govern({
        "knowledge": [{"id": "reference", "snippet": "k" * 1500}],
        "compute": [{"capability": "llm.ollama", "evidence_strength": 1.0}],
        "skills": [{"id": "skill", "steps": ["inspect", "verify"]}],
        "plans": [{"id": "plan", "objective": "repair Mary"}],
        "world": [{"id": "world", "value": "main"}],
    })

    assert selected["world"]
    assert selected["plans"]
    assert selected["skills"]
    assert selected["compute"]
    # Operational lanes are evaluated first. Reference text may still fit,
    # but only inside the remaining cumulative budget.
    assert len(selected["knowledge"]) <= 1
    assert report["used_characters"] <= report["total_budget_characters"]
    assert report["remaining_characters"] >= 0
    assert report["authority"].startswith("prompt-context budget only")
