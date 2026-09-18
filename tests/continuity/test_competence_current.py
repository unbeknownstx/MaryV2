from __future__ import annotations

from pathlib import Path

from mary.continuity import CompetenceLedger


def test_competence_reliability_is_conservative_with_sparse_evidence(tmp_path: Path):
    ledger = CompetenceLedger(tmp_path / "competence.json")

    first = ledger.record(
        capability="llm.ollama",
        operation="conversation",
        node_id="desktop",
        success=True,
        verified=True,
        evidence_ids=("task-1",),
        result="ok",
    )

    assert first.attempts == 1
    assert first.successes == 1
    assert first.failures == 0
    assert first.verified_successes == 1
    assert first.reliability == 0.6667
    assert 0.0 < first.evidence_strength < 0.2

    second = ledger.record(
        capability="llm.ollama",
        operation="conversation",
        node_id="desktop",
        success=False,
        verified=False,
        evidence_ids=("task-2",),
        result="timeout",
    )
    assert second.attempts == 2
    assert second.successes == 1
    assert second.failures == 1
    assert second.reliability == 0.5
    assert second.evidence_strength > first.evidence_strength


def test_competence_accumulates_durable_evidence_without_granting_authority(tmp_path: Path):
    ledger = CompetenceLedger(tmp_path / "competence.json")

    for index in range(10):
        ledger.record(
            capability="knowledge.search",
            operation="search",
            node_id="mac",
            success=index != 7,
            verified=index != 7,
            evidence_ids=(f"task-{index}",),
        )

    row = ledger.find(
        capability="knowledge.search",
        operation="search",
        node_id="mac",
    )[0]
    assert row.attempts == 10
    assert row.successes == 9
    assert row.failures == 1
    assert row.reliability == 0.8333
    assert row.evidence_strength > 0.7
    assert len(row.evidence_ids) == 10

    summary = ledger.summary_for(
        "knowledge.search",
        node_ids=("mac",),
    )
    assert summary[0]["node_id"] == "mac"
    assert summary[0]["attempts"] == 10
    assert "does not grant permission" in ledger.status()["authority"]
