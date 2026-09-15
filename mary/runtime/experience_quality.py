"""Bounded operational experience-quality telemetry for MaryV2.

This module measures the *delivery experience* of Mary without becoming a
character, memory, routing, or lifecycle authority.  It is intentionally
process-local and content-free: only timing/outcome labels are retained.

The monitor gives every surface the same vocabulary for responsive/degraded
states while providers, voice engines, renderers and nodes remain replaceable.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from statistics import median
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class ExperienceSample:
    latency_ms: float
    channel: str
    outcome: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperienceQualityMonitor:
    """Content-free rolling latency/readiness projection.

    Thresholds are UX classifications, not provider SLAs.  They describe how a
    completed interaction felt at the surface and are deliberately conservative
    enough to work across cloud and local routes.
    """

    VERSION = "13.7"
    CAPACITY = 96

    def __init__(self, *, capacity: int = CAPACITY) -> None:
        self._lock = RLock()
        self._samples: deque[ExperienceSample] = deque(
            maxlen=max(16, min(512, int(capacity)))
        )
        self._degraded_reasons: deque[str] = deque(maxlen=12)

    @staticmethod
    def classify(latency_ms: float, *, channel: str = "text") -> str:
        latency = max(0.0, float(latency_ms))
        voice = str(channel).strip().lower() in {"voice", "speech"}
        # Voice includes recognition/synthesis/playback startup, so its
        # classification window is intentionally wider than text.
        if latency < (1800.0 if voice else 1200.0):
            return "instant"
        if latency < (4000.0 if voice else 3000.0):
            return "responsive"
        if latency < (9000.0 if voice else 8000.0):
            return "delayed"
        return "degraded"

    def observe_turn(
        self,
        latency_ms: float,
        *,
        voice_input: bool = False,
        outcome: str = "success",
    ) -> ExperienceSample:
        channel = "voice" if voice_input else "text"
        sample = ExperienceSample(
            latency_ms=round(max(0.0, float(latency_ms)), 3),
            channel=channel,
            outcome=str(outcome or "unknown")[:40],
        )
        with self._lock:
            self._samples.append(sample)
            if sample.outcome != "success":
                self._degraded_reasons.append(f"turn:{sample.outcome}")
            elif self.classify(sample.latency_ms, channel=channel) == "degraded":
                self._degraded_reasons.append(f"{channel}:latency")
        return sample

    def note_degraded(self, reason: str) -> None:
        value = " ".join(str(reason or "").split())[:120]
        if value:
            with self._lock:
                self._degraded_reasons.append(value)

    @staticmethod
    def _percentile(values: list[float], q: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * q)))
        return float(ordered[index])

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            samples = list(self._samples)
            reasons = list(self._degraded_reasons)
        values = [item.latency_ms for item in samples]
        outcomes: dict[str, int] = {}
        for item in samples:
            outcomes[item.outcome] = outcomes.get(item.outcome, 0) + 1
        latest = samples[-1] if samples else None
        latest_class = (
            self.classify(latest.latency_ms, channel=latest.channel)
            if latest is not None
            else "unknown"
        )
        success_count = outcomes.get("success", 0)
        return {
            "version": self.VERSION,
            "sample_count": len(samples),
            "latest": latest.to_dict() if latest else None,
            "latest_class": latest_class,
            "median_ms": round(float(median(values)), 3) if values else 0.0,
            "p95_ms": round(self._percentile(values, 0.95), 3),
            "success_rate": (
                round(success_count / len(samples), 4) if samples else None
            ),
            "outcomes": outcomes,
            "recent_degraded_reasons": reasons[-6:],
            "semantics": (
                "content-free process-local UX telemetry only; no identity, memory, "
                "provider-routing, lifecycle, or permission authority"
            ),
        }
