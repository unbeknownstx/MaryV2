from __future__ import annotations

from mary.distributed import CapabilityDescriptor
from mary.distributed.benchmarking import PROFILE_VERSION, apply_benchmark_profile, cpu_reference_benchmark, host_fingerprint
from mary.distributed.resource_profile import RuntimeResourceProfile


def test_cpu_reference_benchmark_is_small_and_sanitized():
    result = cpu_reference_benchmark(repeats=1, rounds=5_000)
    assert result["operation"] == "cpu_reference"
    assert result["success_rate"] == 1.0
    assert result["median_latency_ms"] is not None
    text = str(result).lower()
    assert "prompt" not in text
    assert "token" not in text
    assert "secret" not in text


def test_apply_benchmark_profile_only_adds_operational_metadata():
    capability = CapabilityDescriptor("llm.ollama", private=True, local=True, metadata={"model": "test"})
    profile = {
        "version": PROFILE_VERSION,
        "authority": "operational_hint_only",
        "capabilities": {
            "llm.ollama": {
                "median_latency_ms": 456.7,
                "success_rate": 1.0,
                "throughput_tokens_per_second": 22.5,
            }
        },
    }
    updated = apply_benchmark_profile([capability], profile)[0]
    assert updated.metadata["model"] == "test"
    assert updated.metadata["benchmark_latency_ms"] == 456.7
    assert updated.metadata["benchmark_success_rate"] == 1.0
    assert updated.metadata["benchmark_throughput"] == 22.5
    assert updated.metadata["benchmark_profile_version"] == PROFILE_VERSION


def test_resource_profile_exposes_acceleration_as_hints_only():
    profile = RuntimeResourceProfile.detect().to_dict()
    assert profile["authority"] == "capability_hint_only"
    assert "vulkan_available" in profile
    assert "metal_available" in profile
    assert "gpu_label" in profile
    assert "recommended_policy" in profile


def test_host_fingerprint_contains_no_hostname_or_identity():
    fingerprint = host_fingerprint()
    assert len(fingerprint) == 16
    assert fingerprint.isalnum()
