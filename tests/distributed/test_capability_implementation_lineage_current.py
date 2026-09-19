from __future__ import annotations

from mary.continuity import CompetenceLedger
from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry
from mary.distributed.capabilities import capability_implementation_fingerprint
from mary.distributed.compute_fabric import (
    BenchmarkBook,
    BenchmarkSample,
    HomeComputeScheduler,
    WorkloadRequest,
)
from mary.distributed.node_intelligence import build_node_intelligence


def _cap(model: str, *, authorized: bool = True, benchmark_ms: float = 500.0):
    return CapabilityDescriptor(
        "llm.ollama",
        private=True,
        local=True,
        cost="local",
        metadata={
            "runtime": "ollama",
            "model": model,
            "execution_authorized": authorized,
            "benchmark_latency_ms": benchmark_ms,
        },
    )


def _node(model: str) -> NodeDescriptor:
    capability = _cap(model)
    return NodeDescriptor(
        node_id="pc",
        role="capability_node",
        host_type="desktop",
        platform="windows",
        capabilities={"llm.ollama": capability},
    )


def test_capability_implementation_fingerprint_ignores_permission_and_benchmark_noise():
    first = capability_implementation_fingerprint(
        _cap("qwen3:4b", authorized=True, benchmark_ms=500.0)
    )
    same_implementation = capability_implementation_fingerprint(
        _cap("qwen3:4b", authorized=False, benchmark_ms=2500.0)
    )
    changed_model = capability_implementation_fingerprint(
        _cap("qwen3:1.7b", authorized=True, benchmark_ms=500.0)
    )

    assert len(first) == 64
    assert first == same_implementation
    assert first != changed_model


def test_competence_ledger_separates_same_capability_by_implementation(tmp_path):
    ledger = CompetenceLedger(tmp_path / "competence.json")
    old_fp = capability_implementation_fingerprint(_cap("qwen3:1.7b"))
    current_fp = capability_implementation_fingerprint(_cap("qwen3:4b"))

    for index in range(8):
        ledger.record(
            capability="llm.ollama",
            operation="conversation",
            node_id="pc",
            success=True,
            verified=True,
            evidence_ids=(f"old-{index}",),
            implementation_fingerprint=old_fp,
        )
    ledger.record(
        capability="llm.ollama",
        operation="conversation",
        node_id="pc",
        success=False,
        evidence_ids=("current-1",),
        implementation_fingerprint=current_fp,
    )

    current = ledger.summary_for(
        "llm.ollama",
        operation="conversation",
        node_ids=("pc",),
        implementation_fingerprint=current_fp,
    )
    historical = ledger.summary_for(
        "llm.ollama",
        operation="conversation",
        node_ids=("pc",),
        implementation_fingerprint=old_fp,
    )

    assert len(current) == 1
    assert current[0]["attempts"] == 1
    assert current[0]["failures"] == 1
    assert current[0]["implementation_fingerprint"] == current_fp
    assert historical[0]["attempts"] == 8
    assert ledger.status()["implementation_bound_records"] == 2


def test_scheduler_excludes_stale_competence_and_benchmark_after_model_change(tmp_path):
    registry = NodeRegistry()
    registry.register(_node("qwen3:4b"))
    old_fp = capability_implementation_fingerprint(_cap("qwen3:1.7b"))
    current_fp = capability_implementation_fingerprint(_cap("qwen3:4b"))

    competence = CompetenceLedger(tmp_path / "competence.json")
    for index in range(12):
        competence.record(
            capability="llm.ollama",
            operation="conversation",
            node_id="pc",
            success=True,
            verified=True,
            evidence_ids=(f"old-{index}",),
            implementation_fingerprint=old_fp,
        )

    benchmarks = BenchmarkBook()
    benchmarks.record(BenchmarkSample(
        node_id="pc",
        capability="llm.ollama",
        operation="conversation",
        latency_ms=10.0,
        success=True,
        implementation_fingerprint=old_fp,
    ))

    [candidate] = HomeComputeScheduler(
        registry,
        benchmarks=benchmarks,
        competence=competence,
    ).rank(WorkloadRequest(
        capability="llm.ollama",
        operation="conversation",
        realtime=True,
    ))

    assert candidate["competence"]["implementation_fingerprint"] == current_fp
    assert candidate["competence"]["attempts"] == 0
    assert candidate["competence"]["stale_records"] == 1
    assert candidate["competence"]["score_delta"] == 0.0
    assert candidate["benchmark"]["implementation_fingerprint"] == current_fp
    assert candidate["benchmark"]["samples"] == 0


def test_node_intelligence_marks_only_stale_competence_as_implementation_changed(tmp_path):
    registry = NodeRegistry()
    registry.register(_node("qwen3:4b"))
    ledger = CompetenceLedger(tmp_path / "competence.json")
    old_fp = capability_implementation_fingerprint(_cap("qwen3:1.7b"))

    ledger.record(
        capability="llm.ollama",
        operation="conversation",
        node_id="pc",
        success=True,
        verified=True,
        evidence_ids=("old-run",),
        implementation_fingerprint=old_fp,
    )

    projection = build_node_intelligence(registry, ledger)
    node = projection["nodes"][0]
    capability = node["capabilities"][0]

    assert capability["evidence_state"] == "implementation_changed"
    assert capability["evidence"] == []
    assert capability["stale_competence_records"] == 1
    assert len(capability["implementation_fingerprint"]) == 64
    assert node["counts"]["demonstrated"] == 0
