from __future__ import annotations

from mary.distributed.inference_acceleration import (
    AccelerationBenchmark,
    LocalInferenceAccelerationPolicy,
)


def test_ollama_does_not_claim_native_mtp_support() -> None:
    policy = LocalInferenceAccelerationPolicy(mode="auto", speculative_tokens=1)
    result = policy.candidate(model="Qwen3.5-9B", runtime="ollama")
    assert result.method == "mtp"
    assert result.state == "unsupported_runtime"


def test_model_name_is_candidate_for_vllm(monkeypatch) -> None:
    monkeypatch.setenv("MARY_VLLM_REMOTE_READY", "1")
    policy = LocalInferenceAccelerationPolicy(mode="auto", speculative_tokens=1)
    result = policy.candidate(model="Qwen3.5-9B", runtime="vllm")
    assert result.state == "benchmark_required"
    assert result.checkpoint_evidence == "model_family_hint"
    assert "not_promoted" in result.reason


def test_unverified_vllm_model_is_not_promoted(monkeypatch) -> None:
    monkeypatch.setenv("MARY_VLLM_REMOTE_READY", "1")
    policy = LocalInferenceAccelerationPolicy(mode="auto")
    result = policy.candidate(model="ordinary-model", runtime="vllm")
    assert result.state == "unverified_model"


def test_explicit_checkpoint_capability_allows_vllm_benchmark(monkeypatch) -> None:
    monkeypatch.setenv("MARY_VLLM_REMOTE_READY", "1")
    policy = LocalInferenceAccelerationPolicy(mode="auto")
    result = policy.candidate(
        model="custom-local-checkpoint",
        runtime="vllm",
        checkpoint_declares_mtp=True,
    )
    assert result.state == "benchmark_required"
    assert result.checkpoint_evidence == "explicit_checkpoint_declaration"


def test_llama_cpp_requires_runtime_readiness(monkeypatch) -> None:
    monkeypatch.delenv("MARY_LLAMA_CPP_READY", raising=False)
    policy = LocalInferenceAccelerationPolicy(mode="auto")
    result = policy.candidate(
        model="Qwen3.5-9B-GGUF",
        runtime="llama.cpp",
        gguf_nextn_predict_layers=2,
    )
    if result.state != "runtime_unavailable":
        # A development machine may actually have llama_cpp installed.
        assert result.state == "benchmark_required"


def test_llama_cpp_uses_explicit_gguf_mtp_metadata(monkeypatch) -> None:
    monkeypatch.setenv("MARY_LLAMA_CPP_READY", "1")
    policy = LocalInferenceAccelerationPolicy(mode="auto")
    result = policy.candidate(
        model="Qwen3.5-9B-GGUF",
        runtime="llama.cpp",
        gguf_nextn_predict_layers=2,
    )
    assert result.state == "benchmark_required"
    assert result.checkpoint_evidence == "gguf_nextn_predict_layers"


def test_llama_cpp_family_name_alone_is_not_checkpoint_proof(monkeypatch) -> None:
    monkeypatch.setenv("MARY_LLAMA_CPP_READY", "1")
    policy = LocalInferenceAccelerationPolicy(mode="auto")
    result = policy.candidate(model="Qwen3.5-9B-GGUF", runtime="llama.cpp")
    assert result.state == "unverified_model"
    assert result.checkpoint_evidence == "model_family_hint"


def test_jan_can_advertise_gguf_mtp_candidate(monkeypatch) -> None:
    monkeypatch.setenv("MARY_JAN_BASE_URL", "http://127.0.0.1:1337/v1")
    policy = LocalInferenceAccelerationPolicy(mode="auto")
    result = policy.candidate(
        model="GLM-4.6-GGUF",
        runtime="jan",
        gguf_nextn_predict_layers=1,
    )
    assert result.state == "benchmark_required"
    assert result.runtime == "jan"
    assert result.checkpoint_evidence == "gguf_nextn_predict_layers"


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
