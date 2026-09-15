"""Content-free provider liveness/readiness aggregation for MaryV2 13.62."""
from __future__ import annotations

from dataclasses import dataclass
import time

VERSION = "13.62"
_ALLOWED = frozenset({"healthy", "rate_limited", "invalid", "unreachable", "unknown"})


@dataclass
class ProviderHealth:
    status: str = "unknown"
    resume_at: float = 0.0
    updated_at: float = 0.0


class ProviderHealthBook:
    def __init__(self, max_providers: int = 64, ttl_seconds: float = 300.0) -> None:
        self.max_providers = max(4, min(256, int(max_providers)))
        self.ttl_seconds = max(10.0, min(3600.0, float(ttl_seconds)))
        self._items: dict[str, ProviderHealth] = {}

    def update(self, provider: str, status: str, *, resume_after_seconds: float = 0.0) -> None:
        name = str(provider).strip().lower()
        state = str(status).strip().lower()
        if not name or state not in _ALLOWED:
            raise ValueError("invalid provider health observation")
        now = time.monotonic()
        if name not in self._items and len(self._items) >= self.max_providers:
            oldest = min(self._items, key=lambda key: self._items[key].updated_at)
            self._items.pop(oldest, None)
        self._items[name] = ProviderHealth(state, now + max(0.0, float(resume_after_seconds)), now)

    def status(self, provider: str, now: float | None = None) -> str:
        now = time.monotonic() if now is None else float(now)
        item = self._items.get(str(provider).strip().lower())
        if item is None or now - item.updated_at > self.ttl_seconds:
            return "unknown"
        if item.status == "rate_limited" and item.resume_at and now >= item.resume_at:
            return "unknown"
        return item.status

    def usable(self, provider: str) -> bool:
        return self.status(provider) in {"healthy", "unknown"}

    def ready(self, providers: list[str]) -> bool:
        return any(self.usable(provider) for provider in providers)

    def snapshot(self) -> dict[str, object]:
        return {
            "version": VERSION,
            "providers": {name: self.status(name) for name in sorted(self._items)},
            "authority": "operational_routing_evidence_only",
            "content_retained": False,
        }
