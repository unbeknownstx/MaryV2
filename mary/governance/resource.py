"""Process-local resource accounting and paid-call guardrails for MaryV2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .limits import RuntimeLimits


@dataclass
class ResourceGovernor:
    """Track model usage and enforce deterministic resource ceilings.

    This object never persists secrets or prompt text. It stores only counters
    and compact metadata so the terminal/UI can expose how Mary is using
    resources without becoming another unbounded history.
    """

    limits: RuntimeLimits = field(default_factory=RuntimeLimits)
    provider_attempts: int = 0
    provider_successes: int = 0
    paid_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    _paid_by_task: dict[str, int] = field(default_factory=dict)
    _last_generation: dict[str, Any] = field(default_factory=dict)

    def provider_order(self, order: list[str]) -> list[str]:
        """Apply the hard maximum attempts for a single generation."""

        limit = max(1, int(self.limits.provider_attempts_per_generation))
        return list(order[:limit])

    def paid_remaining(self, task_id: str) -> int:
        used = int(self._paid_by_task.get(str(task_id), 0))
        return max(0, int(self.limits.paid_calls_per_task) - used)

    def reserve_paid_call(self, task_id: str) -> bool:
        """Reserve one paid call before execution so duplicate calls are blocked."""

        key = str(task_id).strip()
        if not key or self.paid_remaining(key) <= 0:
            return False
        self._paid_by_task[key] = int(self._paid_by_task.get(key, 0)) + 1
        self.paid_calls += 1
        return True

    def record_generation_start(self, *, route: str, order: list[str]) -> None:
        self._last_generation = {
            "route": str(route or "configured"),
            "provider_order": list(order),
            "attempts": [],
            "usage": {},
        }

    def record_attempt(self, provider: str, status: str) -> None:
        self.provider_attempts += 1
        if str(status) == "success":
            self.provider_successes += 1
        attempts = self._last_generation.setdefault("attempts", [])
        attempts.append({"provider": str(provider), "status": str(status)})
        # The provider-order ceiling bounds this list, but retain a defensive cap.
        del attempts[:-max(1, int(self.limits.provider_attempts_per_generation))]

    def record_usage(self, usage: dict[str, Any] | None) -> None:
        payload = dict(usage or {})
        prompt = self._safe_int(payload.get("prompt_tokens", 0))
        completion = self._safe_int(payload.get("completion_tokens", 0))
        reasoning = self._safe_int(payload.get("reasoning_tokens", 0))
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.reasoning_tokens += reasoning
        self._last_generation["usage"] = {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "reasoning_tokens": reasoning,
            "total_tokens": self._safe_int(payload.get("total_tokens", prompt + completion)),
        }

    def forget_task(self, task_id: str) -> None:
        """Release process-local per-task counters after an ephemeral task is evicted."""

        self._paid_by_task.pop(str(task_id).strip(), None)

    def status(self) -> dict[str, Any]:
        return {
            "policy": "bounded_resource_governance",
            "provider_attempts": self.provider_attempts,
            "provider_successes": self.provider_successes,
            "paid_calls": self.paid_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "paid_calls_per_task": int(self.limits.paid_calls_per_task),
            "provider_attempts_per_generation": int(self.limits.provider_attempts_per_generation),
            "last_generation": dict(self._last_generation),
        }

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0
