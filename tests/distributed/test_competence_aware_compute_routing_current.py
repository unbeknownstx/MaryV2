from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mary.continuity import CompetenceLedger
from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry
from mary.distributed.compute_fabric import HomeComputeScheduler, WorkloadRequest
from mary.distributed.tasks import DeviceTaskBroker


def _node(
    node_id: str,
    *,
    authorized: bool | None = None,
    private: bool = True,
) -> NodeDescriptor:
    metadata = {
        "benchmark_latency_ms": 500.0,
        "benchmark_success_rate": 1.0,
    }
    if authorized is not None:
        metadata["execution_authorized"] = authorized
    return NodeDescriptor(
        node_id=node_id,
        role="capability_node",
        host_type="capability_node",
        platform="test",
        capabilities={
            "llm.ollama": CapabilityDescriptor(
                "llm.ollama",
                private=private,
                local=True,
                cost="local",
                metadata=metadata,
            )
        },
    )


def _args() -> dict:
    return {
        "messages": [{"role": "user", "content": "hello"}],
        "role": "conversation",
        "temperature": 0.2,
        "max_tokens": 64,
    }


def _record(ledger: CompetenceLedger, node_id: str, success: bool, count: int, *, observed_at: str | None = None) -> None:
    for index in range(count):
        ledger.record(
            capability="llm.ollama",
            operation="conversation",
            node_id=node_id,
            success=success,
            verified=success and index % 2 == 0,
            latency_ms=500.0,
            evidence_ids=(f"{node_id}-{index}",),
            observed_at=observed_at,
        )


def test_repeated_competence_can_break_an_equal_eligible_node_tie(tmp_path):
    registry = NodeRegistry()
    registry.register(_node("a-node"))
    registry.register(_node("b-node"))
    ledger = CompetenceLedger(tmp_path / "competence.json")
    _record(ledger, "a-node", False, 10)
    _record(ledger, "b-node", True, 10)

    broker = DeviceTaskBroker(competence=ledger)
    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="reply",
        args=_args(),
        requester_device_id="creator",
    )

    assert task.selected_node_id == "b-node"
    decision = broker.compute_status()["benchmarks"]["last_adaptive_decision"]
    rows = {row["node_id"]: row for row in decision["candidates"]}
    assert rows["b-node"]["competence"]["score_delta"] > 0
    assert rows["a-node"]["competence"]["score_delta"] < 0
    assert rows["b-node"]["competence"]["authority"] == "routing_hint_only"


def test_competence_cannot_restore_a_locally_denied_node(tmp_path):
    registry = NodeRegistry()
    registry.register(_node("a-allowed", authorized=True))
    registry.register(_node("b-denied", authorized=False))
    ledger = CompetenceLedger(tmp_path / "competence.json")
    _record(ledger, "a-allowed", False, 12)
    _record(ledger, "b-denied", True, 40)

    broker = DeviceTaskBroker(competence=ledger)
    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="reply",
        args=_args(),
        requester_device_id="creator",
    )

    assert task.selected_node_id == "a-allowed"
    decision = broker.compute_status()["benchmarks"]["last_adaptive_decision"]
    assert all(row["node_id"] != "b-denied" for row in decision.get("candidates", []))


def test_one_success_is_only_a_tiny_hint_and_old_evidence_decays(tmp_path):
    registry = NodeRegistry()
    registry.register(_node("node"))
    ledger = CompetenceLedger(tmp_path / "competence.json")
    _record(ledger, "node", True, 1)

    scheduler = HomeComputeScheduler(registry, competence=ledger)
    current = scheduler.rank(
        WorkloadRequest(
            capability="llm.ollama",
            operation="conversation",
            realtime=True,
        )
    )[0]["competence"]
    assert 0.0 < current["score_delta"] < 1.0

    old_ledger = CompetenceLedger(tmp_path / "old-competence.json")
    old = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
    _record(old_ledger, "node", True, 20, observed_at=old)
    old_hint = HomeComputeScheduler(
        registry,
        competence=old_ledger,
    ).rank(
        WorkloadRequest(
            capability="llm.ollama",
            operation="conversation",
            realtime=True,
        )
    )[0]["competence"]
    assert old_hint["freshness"] < 0.02
    assert old_hint["score_delta"] < 0.2


def test_allowed_node_ids_are_a_hard_scheduler_boundary(tmp_path):
    registry = NodeRegistry()
    registry.register(_node("a-allowed"))
    registry.register(_node("b-excluded"))
    ledger = CompetenceLedger(tmp_path / "competence.json")
    _record(ledger, "b-excluded", True, 40)

    scheduler = HomeComputeScheduler(registry, competence=ledger)
    ranked = scheduler.rank(
        WorkloadRequest(
            capability="llm.ollama",
            operation="conversation",
            realtime=True,
        ),
        allowed_node_ids={"a-allowed"},
    )

    assert [row["node_id"] for row in ranked] == ["a-allowed"]
