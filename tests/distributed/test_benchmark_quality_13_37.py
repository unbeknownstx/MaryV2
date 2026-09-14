from mary.distributed import CapabilityDescriptor
from mary.distributed.benchmarking import apply_benchmark_profile, useful_throughput


def test_useful_throughput_penalizes_fast_wrong_model():
    assert useful_throughput(80.0, 0.5) == 40.0
    assert useful_throughput(50.0, 1.0) == 50.0


def test_quality_metrics_flow_into_capability_metadata_without_raw_output():
    capability = CapabilityDescriptor("llm.ollama", metadata={"configured_model": "qwen", "num_ctx": 8192})
    profile = {
        "version": "13.11",
        "reliability_revision": "13.37",
        "capabilities": {
            "llm.ollama": {
                "model": "qwen",
                "num_ctx": 8192,
                "median_latency_ms": 500,
                "success_rate": 1.0,
                "correctness_rate": 0.9,
                "throughput_tokens_per_second": 40,
                "useful_throughput": 36,
                "median_output_tokens": 24,
                "truncated_runs": 0,
            }
        },
    }
    [result] = apply_benchmark_profile([capability], profile)
    assert result.metadata["benchmark_accuracy"] == 0.9
    assert result.metadata["benchmark_useful_throughput"] == 36.0
    assert result.metadata["benchmark_reliability_revision"] == "13.37"
    assert "content" not in result.metadata

from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry


def test_node_registry_exposes_and_prefers_accuracy_without_granting_authority():
    registry = NodeRegistry()
    for node_id, accuracy, latency in (("fast-wrong", 0.4, 100.0), ("slower-right", 0.98, 350.0)):
        registry.register(NodeDescriptor(
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
                        "benchmark_success_rate": 1.0,
                        "benchmark_accuracy": accuracy,
                        "benchmark_latency_ms": latency,
                        "benchmark_useful_throughput": 20.0 * accuracy,
                    },
                )
            },
        ))

    chosen = registry.choose("llm.ollama")
    assert chosen is not None
    assert chosen.node_id == "slower-right"
    preview = registry.route_preview("llm.ollama")
    assert preview["candidate_benchmarks"]["slower-right"]["benchmark_accuracy"] == 0.98
    assert preview["execution"] == "not_authorized"
