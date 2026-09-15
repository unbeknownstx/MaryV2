from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry
from mary.distributed.tasks import DeviceTaskBroker


def _node(node_id: str, latency_ms: float) -> NodeDescriptor:
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
                metadata={
                    "benchmark_latency_ms": latency_ms,
                    "benchmark_success_rate": 1.0,
                },
            )
        },
    )


def _args():
    return {
        "messages": [{"role": "user", "content": "hello"}],
        "role": "conversation",
        "temperature": 0.2,
        "max_tokens": 64,
    }


def _registry():
    registry = NodeRegistry()
    registry.register(_node("a-slow", 1500.0))
    registry.register(_node("z-fast", 300.0))
    return registry


def test_cold_start_preserves_registry_benchmark_selection():
    registry = _registry()
    broker = DeviceTaskBroker()

    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="reply",
        args=_args(),
        requester_device_id="creator",
    )

    assert task.selected_node_id == "z-fast"
    assert broker.compute_status()["sample_count"] == 0


def test_failed_claim_records_content_free_operational_evidence_and_can_shift_choice():
    registry = _registry()
    broker = DeviceTaskBroker()

    first = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="reply",
        args=_args(),
        requester_device_id="creator",
    )
    assert first.selected_node_id == "z-fast"
    assert broker.poll("z-fast") is first
    broker.complete(
        node_id="z-fast",
        task_id=first.task_id,
        status="failed",
        error="transport failed",
    )

    evidence = broker.compute_status()
    assert evidence["sample_count"] == 1
    sample = evidence["benchmarks"]["samples"][0]
    assert sample["node_id"] == "z-fast"
    assert sample["capability"] == "llm.ollama"
    assert sample["operation"] == "conversation"
    assert sample["success"] is False
    assert "messages" not in str(evidence).lower()
    assert "hello" not in str(evidence).lower()
    assert "transport failed" not in str(evidence).lower()

    second = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="reply again",
        args=_args(),
        requester_device_id="creator",
    )
    assert second.selected_node_id == "a-slow"


def test_permission_rejection_does_not_poison_runtime_reliability():
    registry = _registry()
    broker = DeviceTaskBroker()

    first = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="reply",
        args=_args(),
        requester_device_id="creator",
    )
    assert broker.poll("z-fast") is first
    broker.complete(
        node_id="z-fast",
        task_id=first.task_id,
        status="rejected",
        error="local permission denied",
    )

    assert broker.compute_status()["sample_count"] == 0
    second = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="reply again",
        args=_args(),
        requester_device_id="creator",
    )
    assert second.selected_node_id == "z-fast"


def test_successful_claim_records_latency_without_task_content():
    registry = _registry()
    broker = DeviceTaskBroker()
    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="private intent words",
        args=_args(),
        requester_device_id="creator",
    )
    broker.poll("z-fast")
    broker.complete(
        node_id="z-fast",
        task_id=task.task_id,
        status="completed",
        result={"content": "private generated answer", "model": "qwen"},
    )

    evidence = broker.compute_status()
    assert evidence["sample_count"] == 1
    assert evidence["benchmarks"]["samples"][0]["latency_ms"] >= 0.0
    serialized = str(evidence).lower()
    assert "private intent words" not in serialized
    assert "private generated answer" not in serialized
