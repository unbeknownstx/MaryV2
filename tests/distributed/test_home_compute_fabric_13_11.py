from __future__ import annotations

from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry
from mary.distributed.compute_fabric import BenchmarkBook, BenchmarkSample, HomeComputeScheduler, NodeLoad, WorkloadRequest


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
                metadata={"benchmark_latency_ms": latency_ms, "benchmark_success_rate": 1.0},
            )
        },
    )


def test_registry_prefers_faster_benchmarked_equivalent_node():
    registry = NodeRegistry()
    registry.register(_node("slow", 1800.0))
    registry.register(_node("fast", 650.0))
    assert registry.choose("llm.ollama").node_id == "fast"
    preview = registry.route_preview("llm.ollama")
    assert preview["selected_node_id"] == "fast"
    assert preview["candidate_benchmarks"]["fast"]["benchmark_latency_ms"] == 650.0


def test_unbenchmarked_node_remains_routable_for_backward_compatibility():
    registry = NodeRegistry()
    registry.register(NodeDescriptor(
        node_id="old-node",
        role="capability_node",
        host_type="capability_node",
        platform="test",
        capabilities={"llm.ollama": CapabilityDescriptor("llm.ollama", private=True, local=True, cost="local")},
    ))
    assert registry.choose("llm.ollama").node_id == "old-node"


def test_scheduler_protects_stream_critical_node_from_background_work():
    registry = NodeRegistry()
    registry.register(_node("windows-stream", 700.0))
    registry.register(_node("mac-worker", 900.0))
    book = BenchmarkBook()
    for node_id, latency in (("windows-stream", 700.0), ("mac-worker", 900.0)):
        book.record(BenchmarkSample(node_id=node_id, capability="llm.ollama", operation="summary", latency_ms=latency))
    scheduler = HomeComputeScheduler(registry, benchmarks=book)
    scheduler.update_load(NodeLoad(node_id="windows-stream", stream_critical=True, active_background=1))
    chosen = scheduler.choose(WorkloadRequest(capability="llm.ollama", operation="summary", realtime=False))
    assert chosen is not None
    assert chosen.node_id == "mac-worker"


def test_scheduler_prefers_low_latency_for_realtime_when_nodes_are_idle():
    registry = NodeRegistry()
    registry.register(_node("windows", 1200.0))
    registry.register(_node("mac", 500.0))
    book = BenchmarkBook()
    book.record(BenchmarkSample(node_id="windows", capability="llm.ollama", operation="conversation", latency_ms=1200.0))
    book.record(BenchmarkSample(node_id="mac", capability="llm.ollama", operation="conversation", latency_ms=500.0))
    scheduler = HomeComputeScheduler(registry, benchmarks=book)
    chosen = scheduler.choose(WorkloadRequest(capability="llm.ollama", operation="conversation", realtime=True))
    assert chosen is not None
    assert chosen.node_id == "mac"


def test_benchmark_book_is_operational_hint_only():
    book = BenchmarkBook()
    book.record(BenchmarkSample(node_id="mac", capability="llm.ollama", operation="conversation", latency_ms=100.0))
    snapshot = book.snapshot()
    assert snapshot["authority"] == "operational_hint_only"
    assert "prompt" not in str(snapshot).lower()
    assert "response" not in str(snapshot).lower()
