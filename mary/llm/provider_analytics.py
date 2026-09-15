"""Content-free bounded provider analytics for MaryV2 13.63."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math

VERSION = "13.63"


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * fraction))
    return round(ordered[index], 2)


@dataclass
class _Samples:
    max_samples: int
    latency: deque[float] = field(default_factory=deque)
    ttft: deque[float] = field(default_factory=deque)
    success: int = 0
    failure: int = 0

    def add(self, *, latency_ms: float | None, ttft_ms: float | None, success: bool) -> None:
        self.success += int(bool(success))
        self.failure += int(not success)
        for target, value in ((self.latency, latency_ms), (self.ttft, ttft_ms)):
            if value is not None and math.isfinite(float(value)) and float(value) >= 0:
                target.append(float(value))
                while len(target) > self.max_samples:
                    target.popleft()


class ProviderAnalytics:
    def __init__(self, max_providers: int = 64, max_samples: int = 128) -> None:
        self.max_providers = max(4, min(256, int(max_providers)))
        self.max_samples = max(8, min(1024, int(max_samples)))
        self._items: dict[str, _Samples] = {}

    def observe(self, provider: str, *, latency_ms: float | None = None, ttft_ms: float | None = None, success: bool = True) -> None:
        name = str(provider).strip().lower()
        if not name:
            raise ValueError("provider required")
        if name not in self._items and len(self._items) >= self.max_providers:
            # Deterministic bounded eviction; this is diagnostics, not authority.
            self._items.pop(sorted(self._items)[0], None)
        self._items.setdefault(name, _Samples(self.max_samples)).add(latency_ms=latency_ms, ttft_ms=ttft_ms, success=success)

    def snapshot(self) -> dict[str, object]:
        providers: dict[str, object] = {}
        for name, item in sorted(self._items.items()):
            lat = list(item.latency); ttft = list(item.ttft); total = item.success + item.failure
            providers[name] = {
                "samples": total,
                "success_rate": None if not total else round(item.success / total, 4),
                "latency_p50_ms": _percentile(lat, 0.50),
                "latency_p95_ms": _percentile(lat, 0.95),
                "ttft_p50_ms": _percentile(ttft, 0.50),
                "ttft_p95_ms": _percentile(ttft, 0.95),
            }
        return {"version": VERSION, "providers": providers, "content_retained": False, "authority": "operational_diagnostics_only"}
