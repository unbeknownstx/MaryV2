"""Small rolling latency/resource metric store."""
from __future__ import annotations
from collections import defaultdict, deque
from time import monotonic
from typing import Any


class RuntimeMetrics:
    def __init__(self, limit: int = 100) -> None:
        self.limit = max(10, int(limit)); self.values: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=self.limit))

    def record(self, name: str, seconds: float) -> None:
        self.values[str(name)].append(max(0.0, float(seconds)))

    def timer(self, name: str):
        metrics = self
        class _Timer:
            def __enter__(self): self.started = monotonic(); return self
            def __exit__(self, *_): metrics.record(name, monotonic() - self.started)
        return _Timer()

    def snapshot(self) -> dict[str, Any]:
        result = {}
        for name, values in self.values.items():
            seq = list(values)
            if not seq: continue
            result[name] = {"count": len(seq), "last_ms": round(seq[-1]*1000, 1), "avg_ms": round(sum(seq)/len(seq)*1000, 1), "max_ms": round(max(seq)*1000, 1)}
        return result
