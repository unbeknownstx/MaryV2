"""Bounded process-local provider quota headroom for MaryV2 13.62.

Operational routing evidence only. This module stores counters and configured
limits, never prompts, responses, keys, identity state, or durable memory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import time

VERSION = "13.62"


@dataclass(frozen=True)
class QuotaLimit:
    requests_per_minute: int | None = None
    requests_per_day: int | None = None
    tokens_per_day: int | None = None
    reserve_fraction: float = 0.05

    def __post_init__(self) -> None:
        for value in (self.requests_per_minute, self.requests_per_day, self.tokens_per_day):
            if value is not None and int(value) <= 0:
                raise ValueError("quota limits must be positive when configured")
        if not math.isfinite(float(self.reserve_fraction)) or not 0.0 <= float(self.reserve_fraction) < 1.0:
            raise ValueError("reserve_fraction must be in [0, 1)")


@dataclass
class _Usage:
    minute_requests: list[float] = field(default_factory=list)
    day_requests: list[float] = field(default_factory=list)
    day_tokens: list[tuple[float, int]] = field(default_factory=list)


class ProviderQuotaBook:
    """Small fail-open quota ledger with configurable safety headroom."""

    def __init__(self, max_providers: int = 64) -> None:
        self.max_providers = max(4, min(256, int(max_providers)))
        self._limits: dict[str, QuotaLimit] = {}
        self._usage: dict[str, _Usage] = {}

    @staticmethod
    def _name(provider: str) -> str:
        name = str(provider).strip().lower()
        if not name:
            raise ValueError("provider name required")
        return name

    def configure(self, provider: str, limit: QuotaLimit | None) -> None:
        name = self._name(provider)
        if limit is None:
            self._limits.pop(name, None)
            return
        if name not in self._usage and len(self._usage) >= self.max_providers:
            oldest = min(self._usage, key=lambda key: self._last_seen(self._usage[key]))
            self._usage.pop(oldest, None)
            self._limits.pop(oldest, None)
        self._limits[name] = limit
        self._usage.setdefault(name, _Usage())

    @staticmethod
    def _last_seen(usage: _Usage) -> float:
        values = usage.minute_requests + usage.day_requests + [stamp for stamp, _ in usage.day_tokens]
        return max(values, default=0.0)

    @staticmethod
    def _prune(usage: _Usage, now: float) -> None:
        usage.minute_requests[:] = [stamp for stamp in usage.minute_requests if now - stamp < 60.0]
        usage.day_requests[:] = [stamp for stamp in usage.day_requests if now - stamp < 86400.0]
        usage.day_tokens[:] = [(stamp, tokens) for stamp, tokens in usage.day_tokens if now - stamp < 86400.0]

    def record(self, provider: str, *, tokens: int = 0, now: float | None = None) -> None:
        name = self._name(provider)
        if name not in self._limits:
            return
        now = time.monotonic() if now is None else float(now)
        usage = self._usage.setdefault(name, _Usage())
        self._prune(usage, now)
        usage.minute_requests.append(now)
        usage.day_requests.append(now)
        if int(tokens) > 0:
            usage.day_tokens.append((now, int(tokens)))

    @staticmethod
    def _usable(used: int, limit: int | None, reserve: float, prospective: int = 1) -> bool:
        if limit is None:
            return True
        ceiling = max(1, int(math.floor(limit * (1.0 - reserve))))
        return used + max(0, prospective) <= ceiling

    def allows(self, provider: str, *, estimated_tokens: int = 0, now: float | None = None) -> bool:
        name = self._name(provider)
        limit = self._limits.get(name)
        if limit is None:
            return True
        now = time.monotonic() if now is None else float(now)
        usage = self._usage.setdefault(name, _Usage())
        self._prune(usage, now)
        reserve = limit.reserve_fraction
        return (
            self._usable(len(usage.minute_requests), limit.requests_per_minute, reserve)
            and self._usable(len(usage.day_requests), limit.requests_per_day, reserve)
            and self._usable(sum(tokens for _, tokens in usage.day_tokens), limit.tokens_per_day, reserve, max(0, int(estimated_tokens)))
        )

    def filter(self, providers: list[str], *, estimated_tokens: int = 0) -> list[str]:
        return [provider for provider in providers if self.allows(provider, estimated_tokens=estimated_tokens)]

    def snapshot(self) -> dict[str, object]:
        now = time.monotonic()
        providers: dict[str, object] = {}
        for name, limit in sorted(self._limits.items()):
            usage = self._usage.setdefault(name, _Usage())
            self._prune(usage, now)
            providers[name] = {
                "minute_requests": len(usage.minute_requests),
                "day_requests": len(usage.day_requests),
                "day_tokens": sum(tokens for _, tokens in usage.day_tokens),
                "reserve_fraction": limit.reserve_fraction,
                "allowed": self.allows(name, now=now),
            }
        return {"version": VERSION, "providers": providers, "authority": "operational_routing_evidence_only", "content_retained": False}
