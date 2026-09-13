from __future__ import annotations

from mary.distributed.inference_acceleration import (
    AccelerationBenchmark,
    LocalInferenceAccelerationPolicy,
)


def test_non_vllm_runtime_does_not_claim_mtp_support() -> None:
    policy = LocalInferenceAccelerationPolicy(mode="auto", speculative_tokens=1)
    result = policy.candidate(model="Qwen3.5-9B", runtime="ollama")
    assert result.method == "mtp"
    assert result.state == "unsupported_runtime"


def test_model_name_is_candidate_not_proof(monkeypatch) -> None:
    monkeypatch.setenv("MARY_VLLM_REMOTE_READY", "1")
    policy = LocalInferenceAccelerationPolicy(mode="auto", speculative_tokens=1)
    result = policy.candidate(model="Qwen3.5-9B", runtime="vllm")
    assert result.state == "benchmark_required"
    assert "not_promoted" in result.reason


def test_unverified_model_is_not_promoted(monkeypatch) -> None:
    monkeypatch.setenv("MARY_VLLM_REMOTE_READY", "1")
    policy = LocalInferenceAccelerationPolicy(mode="auto")
    result = policy.candidate(model="ordinary-model", runtime="vllm")
    assert result.state == "unverified_model"


def test_explicit_checkpoint_capability_allows_benchmark_candidate(monkeypatch) -> None:
    monkeypatch.setenv("MARY_VLLM_REMOTE_READY", "1")
    policy = LocalInferenceAccelerationPolicy(mode="auto")
    result = policy.candidate(
        model="custom-local-checkpoint",
        runtime="vllm",
        checkpoint_declares_mtp=True,
    )
    assert result.state == "benchmark_required"


def test_benchmark_must_beat_baseline_before_promotion() -> None:
    baseline = AccelerationBenchmark(
        method="normal",
        median_latency_ms=1000.0,
        throughput_tokens_per_second=20.0,
        success_rate=1.0,
        samples=3,
    )
    slower = AccelerationBenchmark(
        method="mtp",
        median_latency_ms=900.0,
        throughput_tokens_per_second=20.5,
        success_rate=1.0,
        samples=3,
    )
    selected = LocalInferenceAccelerationPolicy.select(baseline, [slower])
    assert selected["selected_method"] == "normal"
    assert selected["promoted"] is False


def test_measured_mtp_speedup_can_be_promoted() -> None:
    baseline = AccelerationBenchmark(
        method="normal",
        median_latency_ms=1000.0,
        throughput_tokens_per_second=20.0,
        success_rate=1.0,
        samples=3,
    )
    faster = AccelerationBenchmark(
        method="mtp",
        median_latency_ms=650.0,
        throughput_tokens_per_second=31.0,
        acceptance_rate=0.78,
        success_rate=1.0,
        samples=3,
    )
    selected = LocalInferenceAccelerationPolicy.select(baseline, [faster])
    assert selected["selected_method"] == "mtp"
    assert selected["promoted"] is True
    assert selected["speedup"] > 1.5
