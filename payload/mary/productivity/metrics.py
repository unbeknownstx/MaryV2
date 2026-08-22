"""Bounded in-process runtime performance metrics for MaryV2.

The metric store is deliberately ephemeral. Performance telemetry belongs to
this process/runtime surface; it is not Mary memory, relationship state, or a
source of identity truth.
"""
from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from time import monotonic
from typing import Any, Mapping


class RuntimeMetrics:
    """Small rolling metric store with one display-safe last-turn trace."""

    def __init__(self, limit: int = 100) -> None:
        self.limit = max(10, int(limit))
        self.values: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.limit)
        )
        self._last_turn: dict[str, Any] = {}

    def record(self, name: str, seconds: float) -> None:
        self.values[str(name)].append(max(0.0, float(seconds)))

    def record_ms(self, name: str, milliseconds: float) -> None:
        self.record(name, max(0.0, float(milliseconds)) / 1000.0)

    def record_many_ms(self, values: Mapping[str, Any]) -> None:
        for name, value in values.items():
            if isinstance(value, bool):
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            self.record_ms(str(name), number)

    def timer(self, name: str):
        metrics = self

        class _Timer:
            def __enter__(self):
                self.started = monotonic()
                return self

            def __exit__(self, *_):
                metrics.record(name, monotonic() - self.started)

        return _Timer()

    def record_turn_trace(self, trace: Mapping[str, Any] | None) -> None:
        """Record one sanitized desktop-turn timing trace.

        The trace contains provider/model identifiers and numeric timings only;
        prompts, response bodies, creator facts, and private memory are excluded.
        """

        if not trace:
            return
        safe = deepcopy(dict(trace))
        timings = safe.get("timings")
        if isinstance(timings, Mapping):
            self.record_many_ms(timings)
        self._last_turn = safe

    def last_turn(self) -> dict[str, Any]:
        return deepcopy(self._last_turn)

    def snapshot(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, values in self.values.items():
            seq = list(values)
            if not seq:
                continue
            result[name] = {
                "count": len(seq),
                "last_ms": round(seq[-1] * 1000, 1),
                "avg_ms": round(sum(seq) / len(seq) * 1000, 1),
                "max_ms": round(max(seq) * 1000, 1),
            }
        return result
