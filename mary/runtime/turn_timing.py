"""Local deterministic turn-latency profiling for MaryV2.

Timing evidence is diagnostic only. It contains no prompt text, provider keys,
private memory content, or authority-bearing state.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from threading import RLock
from time import perf_counter
from typing import Iterator


@dataclass
class TurnTiming:
    turn_id: str
    stages_ms: dict[str, float] = field(default_factory=dict)
    total_ms: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class TurnLatencyProfiler:
    """Measure named turn stages without depending on any provider/runtime UI."""

    ALLOWED_STAGES = frozenset({
        "input", "context", "cognition", "provider", "reflection",
        "retrieval", "tts", "playback_startup", "playback", "tools",
    })

    def __init__(self, turn_id: str) -> None:
        self.turn_id = str(turn_id or "turn")[:120]
        self._started = perf_counter()
        self._stages: dict[str, float] = {}
        self._lock = RLock()

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        key = str(name or "").strip()
        if key not in self.ALLOWED_STAGES:
            raise ValueError(f"Unsupported timing stage: {key}")
        started = perf_counter()
        try:
            yield
        finally:
            elapsed = max(0.0, (perf_counter() - started) * 1000.0)
            with self._lock:
                self._stages[key] = self._stages.get(key, 0.0) + elapsed

    def record_ms(self, name: str, milliseconds: float) -> None:
        key = str(name or "").strip()
        if key not in self.ALLOWED_STAGES:
            raise ValueError(f"Unsupported timing stage: {key}")
        value = max(0.0, min(float(milliseconds), 3_600_000.0))
        with self._lock:
            self._stages[key] = self._stages.get(key, 0.0) + value

    def snapshot(self) -> TurnTiming:
        with self._lock:
            stages = {key: round(value, 3) for key, value in self._stages.items()}
        total = max(0.0, (perf_counter() - self._started) * 1000.0)
        return TurnTiming(turn_id=self.turn_id, stages_ms=stages, total_ms=round(total, 3))

    def breakdown(self) -> dict[str, object]:
        timing = self.snapshot()
        accounted = sum(timing.stages_ms.values())
        return {
            "turn_id": timing.turn_id,
            "stages_ms": timing.stages_ms,
            "total_ms": timing.total_ms,
            "unaccounted_ms": round(max(0.0, timing.total_ms - accounted), 3),
            "semantics": "diagnostic timing only; no prompt, secret, memory, or identity data",
        }
