"""Bounded local-inference acceleration policy for MaryV2.

This module treats MTP/speculative decoding as a replaceable execution
optimization under Mary's existing compute fabric. It never changes identity,
provider eligibility, privacy, model authorization, or durable state.

The policy is deliberately evidence-first:

    detect capability -> verify runtime/checkpoint metadata -> benchmark -> promote

A model name may make MTP a candidate, but never proves runtime compatibility.
For GGUF/llama.cpp paths, explicit ``nextn_predict_layers`` metadata is stronger
proof than a family-name hint. Actual use still requires a successful benchmark
on the target node.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.util import find_spec
import os
import re
from typing import Any, Iterable


_MTP_MODEL_HINTS = (
    re.compile(r"\bqwen3[-_. ]?next\b", re.IGNORECASE),
    re.compile(r"\bqwen3\.5\b", re.IGNORECASE),
    re.compile(r"\bqwen3[-_. ]?5\b", re.IGNORECASE),
    re.compile(r"\bmimo[-_. ]?7b\b", re.IGNORECASE),
    re.compile(r"\bglm[-_. ]?4[.-]?(?:5|6)\b", re.IGNORECASE),
)

_VLLM_RUNTIMES = frozenset({"vllm", "vllm_openai", "vllm-openai"})
_LLAMA_CPP_RUNTIMES = frozenset({"llama.cpp", "llama_cpp", "llamacpp", "llama-cpp"})
_JAN_RUNTIMES = frozenset({"jan", "jan_llama_cpp", "jan-llama-cpp"})


def _module(name: str) -> bool:
    try:
        return find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "enabled"}


def _bounded_int(value: Any, *, low: int, high: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _runtime_ready(runtime_name: str) -> tuple[bool, str]:
    if runtime_name in _VLLM_RUNTIMES:
        ready = _module("vllm") or _flag("MARY_VLLM_REMOTE_READY", False)
        return ready, "vllm_not_detected_or_declared_ready"
    if runtime_name in _LLAMA_CPP_RUNTIMES:
        ready = _module("llama_cpp") or _flag("MARY_LLAMA_CPP_READY", False)
        return ready, "llama_cpp_not_detected_or_declared_ready"
    if runtime_name in _JAN_RUNTIMES:
        ready = bool(os.getenv("MARY_JAN_BASE_URL", "").strip()) or _flag("MARY_JAN_READY", False)
        return ready, "jan_not_configured_or_declared_ready"
    return False, "runtime_has_no_verified_native_mtp_contract"


@dataclass(frozen=True)
class AccelerationCandidate:
    method: str
    state: str
    reason: str
    speculative_tokens: int = 0
    runtime: str | None = None
    model: str | None = None
    checkpoint_evidence: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AccelerationBenchmark:
    method: str
    median_latency_ms: float | None = None
    throughput_tokens_per_second: float | None = None
    time_to_first_token_ms: float | None = None
    acceptance_rate: float | None = None
    success_rate: float = 0.0
    samples: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalInferenceAccelerationPolicy:
    """Detect and rank local decoding optimizations from structural evidence."""

    VERSION = "13.25"

    def __init__(self, *, mode: str | None = None, speculative_tokens: int | None = None) -> None:
        requested = str(mode or os.getenv("MARY_LOCAL_ACCELERATION", "auto")).strip().lower()
        self.mode = requested if requested in {"auto", "off", "mtp"} else "auto"
        self.speculative_tokens = _bounded_int(
            speculative_tokens if speculative_tokens is not None else os.getenv("MARY_MTP_SPECULATIVE_TOKENS", "1"),
            low=1,
            high=8,
            default=1,
        )

    @staticmethod
    def model_has_mtp_hint(model: str | None) -> bool:
        name = str(model or "").strip()
        return bool(name and any(pattern.search(name) for pattern in _MTP_MODEL_HINTS))

    def candidate(
        self,
        *,
        model: str | None,
        runtime: str | None,
        checkpoint_declares_mtp: bool | None = None,
        gguf_nextn_predict_layers: int | None = None,
    ) -> AccelerationCandidate:
        runtime_name = str(runtime or "").strip().lower()
        model_name = str(model or "").strip()

        if self.mode == "off":
            return AccelerationCandidate(
                "none", "disabled", "acceleration_disabled",
                runtime=runtime_name or None, model=model_name or None,
            )

        supported_runtime = (
            runtime_name in _VLLM_RUNTIMES
            or runtime_name in _LLAMA_CPP_RUNTIMES
            or runtime_name in _JAN_RUNTIMES
        )
        if not supported_runtime:
            return AccelerationCandidate(
                "mtp",
                "unsupported_runtime",
                "runtime_has_no_verified_native_mtp_contract",
                speculative_tokens=self.speculative_tokens,
                runtime=runtime_name or None,
                model=model_name or None,
            )

        runtime_ready, unavailable_reason = _runtime_ready(runtime_name)
        if not runtime_ready:
            return AccelerationCandidate(
                "mtp",
                "runtime_unavailable",
                unavailable_reason,
                speculative_tokens=self.speculative_tokens,
                runtime=runtime_name,
                model=model_name or None,
            )

        metadata_layers = _bounded_int(
            gguf_nextn_predict_layers,
            low=0,
            high=64,
            default=0,
        ) if gguf_nextn_predict_layers is not None else 0
        explicit = checkpoint_declares_mtp is True or _flag("MARY_MTP_CHECKPOINT_CAPABLE", False)
        hinted = self.model_has_mtp_hint(model_name)

        if metadata_layers > 0:
            evidence = "gguf_nextn_predict_layers"
        elif explicit:
            evidence = "explicit_checkpoint_declaration"
        elif hinted:
            evidence = "model_family_hint"
        else:
            evidence = "none"

        # llama.cpp and Jan GGUF paths deliberately require explicit checkpoint
        # evidence. A family name alone cannot prove that a downloaded GGUF kept
        # the auxiliary MTP tensors/metadata.
        if runtime_name in (_LLAMA_CPP_RUNTIMES | _JAN_RUNTIMES):
            verified = metadata_layers > 0 or explicit
        else:
            verified = metadata_layers > 0 or explicit or hinted

        if not verified:
            return AccelerationCandidate(
                "mtp",
                "unverified_model",
                "checkpoint_has_not_declared_native_mtp_support",
                speculative_tokens=self.speculative_tokens,
                runtime=runtime_name,
                model=model_name or None,
                checkpoint_evidence=evidence,
            )

        return AccelerationCandidate(
            "mtp",
            "benchmark_required",
            "candidate_detected_but_not_promoted_without_local_measurement",
            speculative_tokens=self.speculative_tokens,
            runtime=runtime_name,
            model=model_name or None,
            checkpoint_evidence=evidence,
        )

    @staticmethod
    def select(
        baseline: AccelerationBenchmark,
        candidates: Iterable[AccelerationBenchmark],
        *,
        minimum_speedup: float = 1.05,
        minimum_success_rate: float = 0.95,
    ) -> dict[str, Any]:
        """Choose an acceleration method only when it measurably beats baseline."""

        minimum_speedup = max(1.0, min(3.0, float(minimum_speedup)))
        minimum_success_rate = max(0.0, min(1.0, float(minimum_success_rate)))
        baseline_tp = baseline.throughput_tokens_per_second
        baseline_latency = baseline.median_latency_ms
        winner: AccelerationBenchmark | None = None
        winner_speedup = 1.0

        for item in candidates:
            if item.samples <= 0 or item.success_rate < minimum_success_rate:
                continue
            speedup: float | None = None
            if (
                baseline_tp is not None
                and baseline_tp > 0
                and item.throughput_tokens_per_second is not None
                and item.throughput_tokens_per_second > 0
            ):
                speedup = float(item.throughput_tokens_per_second) / float(baseline_tp)
            elif (
                baseline_latency is not None
                and baseline_latency > 0
                and item.median_latency_ms is not None
                and item.median_latency_ms > 0
            ):
                speedup = float(baseline_latency) / float(item.median_latency_ms)

            if speedup is not None and speedup >= minimum_speedup and speedup > winner_speedup:
                winner = item
                winner_speedup = speedup

        return {
            "version": LocalInferenceAccelerationPolicy.VERSION,
            "selected_method": winner.method if winner is not None else baseline.method,
            "speedup": round(winner_speedup, 4),
            "promoted": winner is not None,
            "authority": "operational_hint_only",
            "policy": "benchmark_before_promotion",
        }


def local_acceleration_status(
    *,
    model: str | None = None,
    runtime: str | None = None,
    gguf_nextn_predict_layers: int | None = None,
) -> dict[str, Any]:
    policy = LocalInferenceAccelerationPolicy()
    candidate = policy.candidate(
        model=model,
        runtime=runtime,
        gguf_nextn_predict_layers=gguf_nextn_predict_layers,
    )
    return {
        "version": policy.VERSION,
        "mode": policy.mode,
        "vllm_installed": _module("vllm"),
        "llama_cpp_python_installed": _module("llama_cpp"),
        "jan_configured": bool(os.getenv("MARY_JAN_BASE_URL", "").strip()) or _flag("MARY_JAN_READY", False),
        "speculators_installed": _module("speculators"),
        "speculative_tokens": policy.speculative_tokens,
        "candidate": candidate.to_dict(),
        "startup_dependency": False,
        "authority": "diagnostics_only",
    }
