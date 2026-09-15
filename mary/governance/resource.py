"""Process-local resource accounting and paid-call guardrails for MaryV2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .limits import RuntimeLimits
from .model_scheduler import ModelIntelligenceScheduler
from mary.llm.provider_health import ProviderHealthBook
from mary.llm.provider_pressure import ProviderPressureBook
from mary.llm.quota_guard import ProviderQuotaBook, QuotaLimit
from mary.llm.quota_hysteresis import QuotaHysteresis


@dataclass
class ResourceGovernor:
    """Track model usage and enforce deterministic resource ceilings.

    Adaptive intelligence is intentionally applied only after the router has
    produced an eligible provider list. These operational books may filter or
    reorder that list, but can never add a provider excluded by privacy, cost,
    operation, permission, capability, or fallback policy.
    """

    limits: RuntimeLimits = field(default_factory=RuntimeLimits)
    provider_attempts: int = 0
    provider_successes: int = 0
    paid_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_prompt_tokens: int = 0
    model_scheduler: ModelIntelligenceScheduler = field(default_factory=ModelIntelligenceScheduler.from_environment)
    provider_health: ProviderHealthBook = field(default_factory=ProviderHealthBook)
    provider_pressure: ProviderPressureBook = field(default_factory=ProviderPressureBook)
    provider_quota: ProviderQuotaBook = field(default_factory=ProviderQuotaBook)
    _quota_hysteresis: dict[str, QuotaHysteresis] = field(default_factory=dict)
    _paid_by_task: dict[str, int] = field(default_factory=dict)
    _last_generation: dict[str, Any] = field(default_factory=dict)
    _last_successful_provider: str | None = None

    def configure_provider_quota(self, provider: str, limit: QuotaLimit | None) -> None:
        self.provider_quota.configure(provider, limit)

    def observe_quota_remaining(self, provider: str, remaining_fraction: float | None) -> None:
        name = str(provider).strip().lower()
        self.provider_pressure.quota(name, remaining_fraction)
        if remaining_fraction is not None:
            self._quota_hysteresis.setdefault(name, QuotaHysteresis()).update(remaining_fraction)

    def provider_order(self, order: list[str]) -> list[str]:
        """Rank only already-authorized providers, then apply attempt ceiling."""
        admitted = [name for name in order if self.provider_health.usable(name)]
        admitted = self.provider_quota.filter(admitted)
        # Hysteresis demotes scarce routes instead of flapping around thresholds.
        stable = [name for name in admitted if not self._quota_hysteresis.get(name, QuotaHysteresis()).pressured]
        pressured = [name for name in admitted if name not in stable]
        ranked = self.model_scheduler.rank(stable) + self.model_scheduler.rank(pressured)
        # Pressure scoring is a final stable tie-break among the same authorized set.
        ranked = self.provider_pressure.order(ranked)
        limit = max(1, int(self.limits.provider_attempts_per_generation))
        return list(ranked[:limit])

    def paid_remaining(self, task_id: str) -> int:
        used = int(self._paid_by_task.get(str(task_id), 0))
        return max(0, int(self.limits.paid_calls_per_task) - used)

    def reserve_paid_call(self, task_id: str) -> bool:
        key = str(task_id).strip()
        if not key or self.paid_remaining(key) <= 0:
            return False
        self._paid_by_task[key] = int(self._paid_by_task.get(key, 0)) + 1
        self.paid_calls += 1
        return True

    def record_generation_start(self, *, route: str, order: list[str]) -> None:
        self._last_generation = {"route": str(route or "configured"), "provider_order": list(order), "scheduler_mode": self.model_scheduler.mode, "attempts": [], "usage": {}}

    def record_attempt(self, provider: str, status: str, *, latency_ms: float | None = None, quality: float | None = None) -> None:
        self.provider_attempts += 1
        state = str(status).strip().lower()
        name = str(provider).strip().lower()
        if state == "success":
            self.provider_successes += 1
            self._last_successful_provider = name
            self.provider_health.update(name, "healthy")
            self.provider_pressure.success(name, latency_ms)
        elif state in {"cooldown", "rate_limit", "rate_limited"}:
            self.provider_health.update(name, "rate_limited")
            self.provider_pressure.failure(name, rate_limited=True)
        elif state in {"unavailable"}:
            self.provider_health.update(name, "unreachable")
            self.provider_pressure.failure(name)
        elif state not in {"not_configured", "skipped", "deadline_exceeded"}:
            self.provider_pressure.failure(name)
        attempts = self._last_generation.setdefault("attempts", [])
        attempts.append({"provider": name, "status": state})
        del attempts[:-max(1, int(self.limits.provider_attempts_per_generation))]
        self.model_scheduler.record_outcome(name, state, latency_ms=latency_ms, quality=quality)

    def record_usage(self, usage: dict[str, Any] | None) -> None:
        payload = dict(usage or {})
        prompt = self._safe_int(payload.get("prompt_tokens", 0))
        completion = self._safe_int(payload.get("completion_tokens", 0))
        reasoning = self._safe_int(payload.get("reasoning_tokens", 0))
        cached = self._safe_int(payload.get("cached_prompt_tokens", 0))
        total = self._safe_int(payload.get("total_tokens", prompt + completion))
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.reasoning_tokens += reasoning
        self.cached_prompt_tokens += cached
        self._last_generation["usage"] = {"prompt_tokens": prompt, "completion_tokens": completion, "reasoning_tokens": reasoning, "cached_prompt_tokens": cached, "total_tokens": total}
        self.model_scheduler.record_usage(payload)
        if self._last_successful_provider:
            self.provider_quota.record(self._last_successful_provider, tokens=total)

    def record_model_measurement(self, provider: str, *, latency_ms: float | None = None, quality: float | None = None, usage: dict[str, Any] | None = None) -> None:
        self.model_scheduler.record_measurement(provider, latency_ms=latency_ms, quality=quality, usage=usage)

    def forget_task(self, task_id: str) -> None:
        self._paid_by_task.pop(str(task_id).strip(), None)

    def status(self) -> dict[str, Any]:
        return {"policy": "bounded_resource_governance", "provider_attempts": self.provider_attempts, "provider_successes": self.provider_successes, "paid_calls": self.paid_calls, "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens, "reasoning_tokens": self.reasoning_tokens, "cached_prompt_tokens": self.cached_prompt_tokens, "total_tokens": self.prompt_tokens + self.completion_tokens, "paid_calls_per_task": int(self.limits.paid_calls_per_task), "provider_attempts_per_generation": int(self.limits.provider_attempts_per_generation), "model_scheduler": self.model_scheduler.status(), "provider_health": self.provider_health.snapshot(), "provider_pressure": self.provider_pressure.snapshot(), "provider_quota": self.provider_quota.snapshot(), "quota_hysteresis": {name: item.pressured for name, item in sorted(self._quota_hysteresis.items())}, "last_generation": dict(self._last_generation)}

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0
