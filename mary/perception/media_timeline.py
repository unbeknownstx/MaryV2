"""Derived temporal media observations for long-form video/audio perception.

This module borrows the useful *timeline* pattern from local VTuber reaction
pipelines without creating a second memory or world-model owner. Observations
are bounded, source-attributed evidence. They are disposable and must be
explicitly promoted/reconciled by existing Mary Core owners.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

VERSION = "13.70"


@dataclass(frozen=True)
class MediaObservation:
    at_seconds: float
    kind: str
    text: str
    source: str
    confidence: float = 1.0
    previous_context: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "at_seconds", max(0.0, float(self.at_seconds)))
        object.__setattr__(self, "kind", str(self.kind or "unknown").strip().lower()[:40])
        object.__setattr__(self, "text", str(self.text or "").strip()[:4000])
        object.__setattr__(self, "source", str(self.source or "media").strip()[:240])
        object.__setattr__(self, "confidence", min(1.0, max(0.0, float(self.confidence))))
        object.__setattr__(self, "previous_context", str(self.previous_context or "").strip()[:1200])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MediaObservationTimeline:
    asset_id: str
    observations: tuple[MediaObservation, ...]
    version: str = VERSION
    authority: str = "derived_perception_evidence"
    persistence: str = "ephemeral_unless_explicitly_promoted"

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "observations": [item.to_dict() for item in self.observations],
            "version": self.version,
            "authority": self.authority,
            "persistence": self.persistence,
        }


def build_media_observation_timeline(
    asset_id: str,
    observations: Iterable[MediaObservation],
    *,
    max_observations: int = 600,
) -> MediaObservationTimeline:
    """Merge visual/audio observations into a deterministic timestamped view."""
    clean_id = str(asset_id or "").strip()[:240]
    if not clean_id:
        raise ValueError("asset_id is required")
    limit = max(1, min(5000, int(max_observations)))
    ordered = sorted(
        list(observations)[:limit],
        key=lambda item: (item.at_seconds, item.kind, item.source, item.text),
    )
    return MediaObservationTimeline(asset_id=clean_id, observations=tuple(ordered))


def context_window(
    timeline: MediaObservationTimeline,
    *,
    at_seconds: float,
    backward_seconds: float = 12.0,
    forward_seconds: float = 2.0,
    max_items: int = 12,
) -> list[dict[str, Any]]:
    """Return bounded local temporal context for a vision/reaction call."""
    center = max(0.0, float(at_seconds))
    low = max(0.0, center - max(0.0, float(backward_seconds)))
    high = center + max(0.0, float(forward_seconds))
    selected = [
        item.to_dict()
        for item in timeline.observations
        if low <= item.at_seconds <= high
    ]
    return selected[-max(1, min(64, int(max_items))):]
