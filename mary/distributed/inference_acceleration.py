"""Bounded local-inference acceleration policy for MaryV2.

This module treats MTP/speculative decoding as a replaceable execution
optimization under Mary's existing compute fabric. It never changes identity,
provider eligibility, privacy, model authorization, or durable state.

The policy is deliberately evidence-first:

    detect capability -> benchmark baseline/accelerated variants -> promote winner

A model name may make MTP a *candidate*, but never proves runtime compatibility.
Actual use still requires a compatible runtime/checkpoint and a successful
benchmark on the target node.
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
    re.compile(r"\bgemma[-_. ]?4\b", re.IGNORECASE),
)


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


@dataclass(frozen=True)
class AccelerationCandidate:
    method: str
    state: str
    reason: str
    speculative_tokens: int = 0
    runtime: str | None = None
    model: str | None = None

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

    VERSION = "13.24"

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
    ) -> AccelerationCandidate:
        runtime_name = str(runtime or "").strip().lower()
        model_name = str(model or "").strip()

        if self.mode == "off":
            return AccelerationCandidate("none", "disabled", "acceleration_disabled", runtime=runtime_name or None, model=model_name or None)

        if runtime_name not in {"vllm", "vllm_openai", "vllm-openai"}:
            return AccelerationCandidate(
                "mtp",
                "unsupported_runtime",
                "native_mtp_requires_a_runtime_with_verified_mtp_support",
                speculative_tokens=self.speculative_tokens,
                runtime=runtime_name or None,
                model=model_name or None,
            )

        runtime_installed = _module("vllm") or _flag("MARY_VLLM_REMOTE_READY", False)
        if not runtime_installed:
            return AccelerationCandidate(
                "mtp",
                "runtime_unavailable",
                "vllm_not_detected_or_declared_ready",
                speculative_tokens=self.speculative_tokens,
                runtime=runtime_name,
                model=model_name or None,
            )

        explicit = checkpoint_declares_mtp is True or _flag("MARY_MTP_CHECKPOINT_CAPABLE", False)
        hinted = self.model_has_mtp_hint(model_name)
        if not explicit and not hinted:
            return AccelerationCandidate(
                "mtp",
                "unverified_model",
                "checkpoint_has_not_declared_native_mtp_support",
                speculative_tokens=self.speculative_tokens,
                runtime=runtime_name,
                model=model_name or None,
            )

        # A known family/name is still only a candidate. Runtime initialization
        # and a successful benchmark are required before scheduler promotion.
        return AccelerationCandidate(
            "mtp",
            "benchmark_required",
            "candidate_detected_but_not_promoted_without_local_measurement",
            speculative_tokens=self.speculative_tokens,
            runtime=runtime_name,
            model=model_name or None,
        )

    @staticmethod
    def select(
        baseline: AccelerationBenchmark,
        candidates: Iterable[AccelerationBenchmark],
        *,
        minimum_speedup: float = 1.05,
        minimum_success_rate: float = 0.95,
    ) -> dict[str, Any]:
        """Choose an acceleration method only when it measurably beats baseline.

        Throughput is preferred when available; otherwise median latency is
        compared. Acceptance rate is recorded for diagnostics but is not used as
        a semantic-quality proxy because speculative decoding should remain
        distribution-preserving at the serving layer.
        """

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


def local_acceleration_status(*, model: str | None = None, runtime: str | None = None) -> dict[str, Any]:
    policy = LocalInferenceAccelerationPolicy()
    candidate = policy.candidate(model=model, runtime=runtime)
    return {
        "version": policy.VERSION,
        "mode": policy.mode,
        "vllm_installed": _module("vllm"),
        "speculators_installed": _module("speculators"),
        "speculative_tokens": policy.speculative_tokens,
        "candidate": candidate.to_dict(),
        "startup_dependency": False,
        "authority": "diagnostics_only",
    }
