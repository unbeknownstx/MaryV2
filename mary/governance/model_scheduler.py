"""Adaptive model/provider intelligence for MaryV2.

The scheduler is deliberately downstream of Mary's hard routing policy. It may
reorder only providers that the router has already declared eligible for the
current request. It therefore cannot grant cloud access, authorize paid use,
bypass local-only privacy, add unsupported structured-output routes, or widen
fallback eligibility.

Only bounded structural measurements are retained: attempts, successes,
failures, latency summaries, quality signals, and token-efficiency counters.
Prompt text, response text, secrets, and provider exception prose are never
stored here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Iterable


_SUCCESS_STATUSES = frozenset({"success"})
_NEUTRAL_STATUSES = frozenset({"not_configured", "skipped", "deadline_exceeded"})
_SOFT_FAILURE_STATUSES = frozenset({"cooldown", "rate_limited", "rate_limit"})


def _bounded_float(value: Any, *, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _ewma(previous: float | None, value: float, alpha: float) -> float:
    if previous is None:
        return float(value)
    return (alpha * float(value)) + ((1.0 - alpha) * float(previous))


@dataclass
class ProviderEvidence:
    """Bounded, content-free evidence for one provider/model route."""

    attempts: int = 0
    successes: int = 0
    hard_failures: int = 0
    soft_failures: int = 0
    consecutive_failures: int = 0
    latency_ewma_ms: float | None = None
    quality_ewma: float | None = None
    token_efficiency_ewma: float | None = None
    cache_ratio_ewma: float | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_prompt_tokens: int = 0
    total_tokens: int = 0

    def reliability(self) -> float:
        observed = self.successes + self.hard_failures + self.soft_failures
        if observed <= 0:
            return 0.5
        # Beta(2, 2) prior prevents tiny samples from dominating route order.
        return (self.successes + 2.0) / (observed + 4.0)

    def snapshot(self) -> dict[str, Any]:
        return {
            "attempts": self.attempts,
            "successes": self.successes,
            "hard_failures": self.hard_failures,
            "soft_failures": self.soft_failures,
            "consecutive_failures": self.consecutive_failures,
            "reliability": round(self.reliability(), 4),
            "latency_ewma_ms": None if self.latency_ewma_ms is None else round(self.latency_ewma_ms, 2),
            "quality_ewma": None if self.quality_ewma is None else round(self.quality_ewma, 4),
            "token_efficiency_ewma": None if self.token_efficiency_ewma is None else round(self.token_efficiency_ewma, 4),
            "cache_ratio_ewma": None if self.cache_ratio_ewma is None else round(self.cache_ratio_ewma, 4),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cached_prompt_tokens": self.cached_prompt_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class ModelIntelligenceScheduler:
    """Evidence-driven reordering within an already-authorized provider set.

    ``adaptive`` is safe at cold start because providers with insufficient
    evidence keep their incoming deterministic order. Once enough structural
    observations exist, measured reliability, latency, quality and efficiency
    can influence the order. The incoming order always remains a meaningful
    prior, so local/free-first policy is not erased by noisy measurements.
    """

    mode: str = "adaptive"
    minimum_samples: int = 3
    ewma_alpha: float = 0.25
    _providers: dict[str, ProviderEvidence] = field(default_factory=dict)
    _last_successful_provider: str | None = None

    @classmethod
    def from_environment(cls) -> "ModelIntelligenceScheduler":
        mode = os.getenv("MARY_LLM_SCHEDULER", "adaptive").strip().lower()
        if mode not in {"ordered", "adaptive"}:
            mode = "adaptive"
        minimum_samples = _safe_int(os.getenv("MARY_LLM_SCHEDULER_MIN_SAMPLES", "3"))
        minimum_samples = max(1, min(50, minimum_samples or 3))
        alpha = _bounded_float(
            os.getenv("MARY_LLM_SCHEDULER_EWMA_ALPHA", "0.25"),
            low=0.05,
            high=1.0,
            default=0.25,
        )
        return cls(mode=mode, minimum_samples=minimum_samples, ewma_alpha=alpha)

    def evidence(self, provider: str) -> ProviderEvidence:
        name = str(provider).strip().lower()[:64]
        return self._providers.setdefault(name, ProviderEvidence())

    def rank(self, eligible_order: Iterable[str]) -> list[str]:
        """Rank only the providers already admitted by router/governance policy."""

        order: list[str] = []
        for item in eligible_order:
            name = str(item).strip().lower()
            if name and name not in order:
                order.append(name)
        if self.mode != "adaptive" or len(order) < 2:
            return order

        # Cold-start determinism: do not reshuffle a provider until it has enough
        # real observations. This keeps existing route tests and safe fallbacks
        # stable while allowing Mary to learn from actual use over time.
        eligible_with_evidence = {
            name
            for name in order
            if self.evidence(name).attempts >= self.minimum_samples
        }
        if not eligible_with_evidence:
            return order

        index = {name: position for position, name in enumerate(order)}

        def score(name: str) -> tuple[float, int]:
            stats = self.evidence(name)
            # Incoming policy order remains a strong prior. Evidence can move a
            # provider, but only after enough observations have accumulated.
            policy_prior = 1.0 - (index[name] / max(1, len(order) - 1))
            if stats.attempts < self.minimum_samples:
                adaptive = 0.0
            else:
                reliability = stats.reliability()
                quality = 0.5 if stats.quality_ewma is None else stats.quality_ewma
                efficiency = 0.5 if stats.token_efficiency_ewma is None else stats.token_efficiency_ewma
                if stats.latency_ewma_ms is None:
                    latency = 0.5
                else:
                    # 0 ms -> 1.0; 30 s or slower -> 0.0.
                    latency = 1.0 - min(stats.latency_ewma_ms, 30_000.0) / 30_000.0
                failure_penalty = min(stats.consecutive_failures, 5) * 0.08
                adaptive = (
                    reliability * 0.45
                    + quality * 0.25
                    + latency * 0.20
                    + efficiency * 0.10
                    - failure_penalty
                )
            combined = policy_prior * 0.55 + adaptive * 0.45
            return (combined, -index[name])

        return sorted(order, key=score, reverse=True)

    def record_outcome(
        self,
        provider: str,
        status: str,
        *,
        latency_ms: float | None = None,
        quality: float | None = None,
    ) -> None:
        name = str(provider).strip().lower()
        if not name:
            return
        state = str(status).strip().lower()
        stats = self.evidence(name)

        if state not in _NEUTRAL_STATUSES:
            stats.attempts += 1

        if state in _SUCCESS_STATUSES:
            stats.successes += 1
            stats.consecutive_failures = 0
            self._last_successful_provider = name
        elif state in _SOFT_FAILURE_STATUSES:
            stats.soft_failures += 1
            stats.consecutive_failures = min(stats.consecutive_failures + 1, 10_000)
        elif state not in _NEUTRAL_STATUSES:
            stats.hard_failures += 1
            stats.consecutive_failures = min(stats.consecutive_failures + 1, 10_000)

        if latency_ms is not None:
            latency = _bounded_float(latency_ms, low=0.0, high=86_400_000.0, default=0.0)
            stats.latency_ewma_ms = _ewma(stats.latency_ewma_ms, latency, self.ewma_alpha)
        if quality is not None:
            bounded_quality = _bounded_float(quality, low=0.0, high=1.0, default=0.5)
            stats.quality_ewma = _ewma(stats.quality_ewma, bounded_quality, self.ewma_alpha)

    def record_usage(self, usage: dict[str, Any] | None, *, provider: str | None = None) -> None:
        name = str(provider or self._last_successful_provider or "").strip().lower()
        if not name:
            return
        stats = self.evidence(name)
        payload = dict(usage or {})
        prompt = _safe_int(payload.get("prompt_tokens", 0))
        completion = _safe_int(payload.get("completion_tokens", 0))
        reasoning = _safe_int(payload.get("reasoning_tokens", 0))
        cached = _safe_int(payload.get("cached_prompt_tokens", 0))
        total = _safe_int(payload.get("total_tokens", prompt + completion))

        stats.prompt_tokens += prompt
        stats.completion_tokens += completion
        stats.reasoning_tokens += reasoning
        stats.cached_prompt_tokens += cached
        stats.total_tokens += total

        if total > 0:
            # Output yielded per total token. This is intentionally a structural
            # efficiency signal, not a claim about semantic answer quality.
            efficiency = completion / total
            stats.token_efficiency_ewma = _ewma(
                stats.token_efficiency_ewma,
                efficiency,
                self.ewma_alpha,
            )
        if prompt > 0:
            cache_ratio = min(1.0, cached / prompt)
            stats.cache_ratio_ewma = _ewma(
                stats.cache_ratio_ewma,
                cache_ratio,
                self.ewma_alpha,
            )

    def record_measurement(
        self,
        provider: str,
        *,
        latency_ms: float | None = None,
        quality: float | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        """Accept benchmark/runtime evidence without storing generated content."""

        if latency_ms is not None or quality is not None:
            stats = self.evidence(provider)
            if latency_ms is not None:
                latency = _bounded_float(latency_ms, low=0.0, high=86_400_000.0, default=0.0)
                stats.latency_ewma_ms = _ewma(stats.latency_ewma_ms, latency, self.ewma_alpha)
            if quality is not None:
                bounded_quality = _bounded_float(quality, low=0.0, high=1.0, default=0.5)
                stats.quality_ewma = _ewma(stats.quality_ewma, bounded_quality, self.ewma_alpha)
        if usage is not None:
            self.record_usage(usage, provider=provider)

    def status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "policy": "hard_constraints_then_adaptive_scoring",
            "minimum_samples": self.minimum_samples,
            "ewma_alpha": self.ewma_alpha,
            "content_retention": "none",
            "providers": {
                name: evidence.snapshot()
                for name, evidence in sorted(self._providers.items())
            },
        }
