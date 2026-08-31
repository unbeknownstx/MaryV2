"""Presentation-only experience contracts for MaryV2.

This module deliberately owns no identity, memory, relationship, or provider state.
It converts already-authoritative runtime projections into a stable shape that UI
surfaces can render without learning the internals of every Mary subsystem.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ExperienceCue:
    """A bounded presentation cue derived from authoritative state."""

    channel: str
    label: str
    intensity: float = 0.0
    source: str = "runtime"
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExperienceTheme:
    """UI palette tokens. These are presentation colors, not emotional truth."""

    name: str
    accent: str
    accent_2: str
    glow: str
    surface: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExperienceSnapshot:
    """Whitelisted, frontend-safe Mary experience projection."""

    version: str
    authority: str
    identity_owner: str
    interaction_state: str
    mood: str
    energy: str
    conversation_id: str
    conversation_label: str
    relationship_label: str
    relationship_strength: float
    memory_count: int
    active_task: str
    provider: str
    model: str
    lane: str
    latency_ms: float | None
    expression: str
    gesture: str
    gaze: str
    theme: ExperienceTheme
    cues: tuple[ExperienceCue, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["theme"] = self.theme.to_dict()
        payload["cues"] = [cue.to_dict() for cue in self.cues]
        payload["metadata"] = dict(self.metadata)
        return payload
