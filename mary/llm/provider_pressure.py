"""Ephemeral provider pressure evidence for MaryV2 13.60.

Inspired by multi-provider gateways, but deliberately Mary-owned: this ledger
contains no prompts, responses, keys, identity state, or durable memory. It
records content-free operational evidence while keeping ordinary configured
routing stable unless an explicit pressure signal (for example quota headroom
or an external cooldown) is present.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import time


VERSION = "13.60"


@dataclass
class ProviderPressure:
    successes: int = 0
    failures: int = 0
    rate_limits: int = 0
    latency_ema_ms: float | None = None
    quota_remaining_fraction: float | None = None
    cooldown_until: float = 0.0
    last_update: float = 0.0

    def observe_success(self, latency_ms: float | None = None) -> None:
        self.successes += 1
        self.last_update = time.monotonic()
        if latency_ms is not None and math.isfinite(float(latency_ms)) and float(latency_ms) >= 0:
            value = float(latency_ms)
            self.latency_ema_ms = value if self.latency_ema_ms is None else (0.8 * self.latency_ema_ms + 0.2 * value)

    def observe_failure(self, *, rate_limited: bool = False, cooldown_seconds: float = 0.0) -> None:
        self.failures += 1
        if rate_limited:
            self.rate_limits += 1
        self.last_update = time.monotonic()
        if cooldown_seconds > 0:
            self.cooldown_until = max(self.cooldown_until, self.last_update + float(cooldown_seconds))

    def set_quota_remaining(self, fraction: float | None) -> None:
        if fraction is None:
            self.quota_remaining_fraction = None
            return
        value = float(fraction)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("quota remaining fraction must be between 0 and 1")
        self.quota_remaining_fraction = value
        self.last_update = time.monotonic()

    def has_explicit_routing_signal(self, now: float | None = None) -> bool:
        """Return whether pressure is authorized to influence route order.

        Ordinary success/failure observations remain useful diagnostics and
        scoring evidence, but do not by themselves override the creator's
        configured provider order. Explicit quota headroom or an externally
        supplied cooldown is required before this pressure book reorders.
        """
        now = time.monotonic() if now is None else float(now)
        return self.quota_remaining_fraction is not None or self.cooldown_until > now

    def score(self, now: float | None = None) -> float:
        now = time.monotonic() if now is None else float(now)
        if self.cooldown_until > now:
            return -1000.0
        total = self.successes + self.failures
        reliability = (self.successes + 1.0) / (total + 2.0)
        quota = 0.5 if self.quota_remaining_fraction is None else self.quota_remaining_fraction
        latency_penalty = 0.0 if self.latency_ema_ms is None else min(1.0, self.latency_ema_ms / 10000.0)
        rate_penalty = min(1.0, self.rate_limits / max(1.0, total))
        return (2.0 * reliability) + quota - latency_penalty - rate_penalty

    def public_dict(self, now: float | None = None) -> dict[str, object]:
        now = time.monotonic() if now is None else float(now)
        return {
            "successes": self.successes,
            "failures": self.failures,
            "rate_limits": self.rate_limits,
            "latency_ema_ms": None if self.latency_ema_ms is None else round(self.latency_ema_ms, 2),
            "quota_remaining_fraction": self.quota_remaining_fraction,
            "cooldown_remaining_seconds": round(max(0.0, self.cooldown_until - now), 2),
            "score": round(self.score(now), 4),
            "content_retained": False,
        }


class ProviderPressureBook:
    """Bounded process-local health/quota ledger used only as routing evidence."""

    def __init__(self, max_providers: int = 64) -> None:
        self.max_providers = max(4, min(256, int(max_providers)))
        self._items: dict[str, ProviderPressure] = {}

    def _entry(self, provider: str) -> ProviderPressure:
        name = str(provider).strip().lower()
        if not name:
            raise ValueError("provider name required")
        if name not in self._items and len(self._items) >= self.max_providers:
            oldest = min(self._items, key=lambda key: self._items[key].last_update)
            self._items.pop(oldest, None)
        return self._items.setdefault(name, ProviderPressure())

    def success(self, provider: str, latency_ms: float | None = None) -> None:
        self._entry(provider).observe_success(latency_ms)

    def failure(self, provider: str, *, rate_limited: bool = False, cooldown_seconds: float = 0.0) -> None:
        self._entry(provider).observe_failure(rate_limited=rate_limited, cooldown_seconds=cooldown_seconds)

    def quota(self, provider: str, remaining_fraction: float | None) -> None:
        self._entry(provider).set_quota_remaining(remaining_fraction)

    def has_routing_signal(self, providers: list[str], now: float | None = None) -> bool:
        now = time.monotonic() if now is None else float(now)
        for provider in providers:
            item = self._items.get(str(provider).strip().lower())
            if item is not None and item.has_explicit_routing_signal(now):
                return True
        return False

    def order(self, providers: list[str]) -> list[str]:
        # Stable sort preserves creator/configured order when evidence is absent/equal.
        indexed = list(enumerate(providers))
        return [name for _, name in sorted(indexed, key=lambda item: (-self._items.get(item[1], ProviderPressure()).score(), item[0]))]

    def snapshot(self) -> dict[str, object]:
        return {
            "version": VERSION,
            "providers": {name: pressure.public_dict() for name, pressure in sorted(self._items.items())},
            "authority": "operational_routing_evidence_only",
            "content_retained": False,
        }
