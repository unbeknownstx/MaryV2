import json

import pytest

from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry
from mary.distributed.compute_fabric import BenchmarkBook
from mary.distributed.tasks import DeviceTaskBroker


def _node(node_id: str, latency_ms: float, *, required_gib: float | None = None) -> NodeDescriptor:
    metadata = {
        "benchmark_latency_ms": latency_ms,
        "benchmark_success_rate": 1.0,
    }
    if required_gib is not None:
        metadata["resource_accelerator_gib_utility"] = required_gib
    return NodeDescriptor(
        node_id=node_id,
        role="capability_node",
        host_type="capability_node",
        platform="test",
        capabilities={
            "llm.ollama": CapabilityDescriptor(
                "llm.ollama",
                private=True,
                local=True,
                cost="local",
                metadata=metadata,
            )
        },
    )


def _registry(*, required: bool = False) -> NodeRegistry:
    registry = NodeRegistry()
    registry.register(_node("a-slow", 900.0, required_gib=2.0 if required else None))
    registry.register(_node("z-fast", 300.0, required_gib=8.0 if required else None))
    return registry


def _args(secret: str = "PRIVATE-PROMPT-MUST-NOT-APPEAR") -> dict:
    return {
        "messages": [{"role": "user", "content": secret}],
        "role": "utility",
        "temperature": 0.2,
        "max_tokens": 64,
    }


def _report(total: float, free: float) -> dict:
    return {
        "ram_total_gib": 32.0,
        "ram_free_gib": 24.0,
        "vram_total_gib": total,
        "vram_free_gib": free,
        "apple_unified_memory": False,
        "source": "nvidia_smi",
    }


def test_adaptive_route_decision_is_visible_but_content_free():
    registry = _registry()
    broker = DeviceTaskBroker()
    broker.update_resource_telemetry("z-fast", _report(4.0, 4.0))
    broker.update_resource_telemetry("a-slow", _report(16.0, 16.0))

    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="PRIVATE-INTENT-MUST-NOT-APPEAR",
        args=_args(),
        requester_device_id="creator",
    )

    status = broker.compute_status()
    decision = status["benchmarks"]["last_adaptive_decision"]
    assert task.selected_node_id == "z-fast"
    assert decision["revision"] == "13.55"
    assert decision["capability"] == "llm.ollama"
    assert decision["operation"] == "utility"
    assert decision["selected_node_id"] == "z-fast"
    assert decision["outcome"] == "selected"
    assert decision["content_retained"] is False
    assert {item["node_id"] for item in decision["candidates"]} == {"a-slow", "z-fast"}

    serialized = json.dumps(status, sort_keys=True)
    assert "PRIVATE-INTENT-MUST-NOT-APPEAR" not in serialized
    assert "PRIVATE-PROMPT-MUST-NOT-APPEAR" not in serialized


def test_cold_registry_fallback_is_not_misattributed_to_adaptive_scheduler():
    registry = _registry()
    broker = DeviceTaskBroker()

    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="ordinary work",
        args=_args("ordinary content"),
        requester_device_id="creator",
    )

    assert task.selected_node_id == "z-fast"
    assert broker.compute_status()["benchmarks"]["last_adaptive_decision"] == {}


def test_measured_no_fit_failure_records_content_free_explanation():
    registry = _registry(required=True)
    broker = DeviceTaskBroker()
    broker.update_resource_telemetry("z-fast", _report(4.0, 4.0))
    broker.update_resource_telemetry("a-slow", _report(1.0, 1.0))

    with pytest.raises(LookupError, match="measured accelerator capacity"):
        broker.enqueue(
            registry,
            capability="llm.ollama",
            intent="PRIVATE-NOFIT-INTENT",
            args=_args("PRIVATE-NOFIT-PROMPT"),
            requester_device_id="creator",
        )

    decision = broker.compute_status()["benchmarks"]["last_adaptive_decision"]
    assert decision["selected_node_id"] is None
    assert decision["outcome"] == "measured_no_fit"
    assert len(decision["candidates"]) == 2
    assert all("resource_infeasible" in item["reason"] for item in decision["candidates"])
    serialized = json.dumps(decision, sort_keys=True)
    assert "PRIVATE-NOFIT-INTENT" not in serialized
    assert "PRIVATE-NOFIT-PROMPT" not in serialized


def test_decision_candidate_retention_is_bounded_and_sanitized():
    book = BenchmarkBook()
    candidates = [
        {
            "node_id": f"node-{index}",
            "score": index,
            "reason": "x" * 500,
            "load_pressure": 3.0,
            "benchmark": {
                "samples": index,
                "success_rate": 1.0,
                "median_latency_ms": 100.0,
                "median_throughput": 20.0,
                "raw_output": "must-not-survive",
            },
            "prompt": "must-not-survive",
        }
        for index in range(20)
    ]

    book.record_adaptive_decision(
        capability="llm.ollama",
        operation="utility",
        selected_node_id="node-0",
        outcome="selected",
        candidates=candidates,
    )
    decision = book.snapshot()["last_adaptive_decision"]

    assert len(decision["candidates"]) == 8
    assert all(len(item["reason"]) <= 240 for item in decision["candidates"])
    assert all(item["load_pressure"] == 1.0 for item in decision["candidates"])
    serialized = json.dumps(decision, sort_keys=True)
    assert "raw_output" not in serialized
    assert "must-not-survive" not in serialized
    assert '"prompt"' not in serialized
