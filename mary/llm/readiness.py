"""Bounded readiness aggregation for MaryV2 13.64."""
from __future__ import annotations
from dataclasses import dataclass
import time

VERSION = "13.64"

@dataclass(frozen=True)
class ReadinessSignal:
    source: str
    ready: bool | None
    observed_at: float
    ttl_seconds: float = 90.0

    def fresh(self, now: float) -> bool:
        return now - self.observed_at <= max(1.0, min(3600.0, self.ttl_seconds))

class ReadinessAggregator:
    """Aggregates operational signals without turning unknown into failure."""
    def __init__(self, max_signals: int = 128) -> None:
        self.max_signals = max(8, min(512, int(max_signals)))
        self._signals: dict[tuple[str, str], ReadinessSignal] = {}

    def observe(self, provider: str, signal: ReadinessSignal) -> None:
        key = (str(provider).strip().lower(), str(signal.source).strip().lower())
        if not all(key):
            raise ValueError("provider and readiness source required")
        if key not in self._signals and len(self._signals) >= self.max_signals:
            oldest = min(self._signals, key=lambda item: self._signals[item].observed_at)
            self._signals.pop(oldest, None)
        self._signals[key] = signal

    def status(self, provider: str, *, now: float | None = None) -> str:
        now = time.monotonic() if now is None else float(now)
        name = str(provider).strip().lower()
        values = [s.ready for (p, _), s in self._signals.items() if p == name and s.fresh(now) and s.ready is not None]
        if not values:
            return "unknown"
        if any(value is False for value in values):
            return "not_ready"
        return "ready"

    def snapshot(self) -> dict[str, object]:
        providers = sorted({p for p, _ in self._signals})
        return {"version": VERSION, "providers": {p: self.status(p) for p in providers}, "authority": "operational_readiness_only", "content_retained": False}
