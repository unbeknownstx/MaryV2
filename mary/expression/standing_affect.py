"""Persistent, decaying standing affect for MaryV2.

This component is derived expressive continuity, not a second emotion,
relationship, personality, or memory owner. It stores only bounded valence and
arousal residue plus provenance-safe cause metadata. Durable relationship change
must still flow through Mary's existing relationship-development authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp
from pathlib import Path
from time import time
from typing import Any
import json
import os


@dataclass
class StandingAffectState:
    valence: float = 0.0
    arousal: float = 0.0
    updated_at: float = 0.0
    source: str = ""
    cause: str = ""
    attributed_person: str | None = None
    attribution_confidence: float = 0.0


class StandingAffectStore:
    VERSION = "1"

    def __init__(self, path: str | Path | None = None, *, half_life_seconds: float = 2700.0) -> None:
        self.path = Path(path) if path is not None else None
        self.half_life_seconds = max(60.0, float(half_life_seconds))
        self.state = StandingAffectState(updated_at=time())

    @staticmethod
    def _clip(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, float(value)))

    def _decay_factor(self, now: float | None = None) -> float:
        now_value = time() if now is None else float(now)
        age = max(0.0, now_value - float(self.state.updated_at or now_value))
        return exp(-0.6931471805599453 * age / self.half_life_seconds)

    def decayed(self, now: float | None = None) -> StandingAffectState:
        factor = self._decay_factor(now)
        return StandingAffectState(
            valence=self.state.valence * factor,
            arousal=self.state.arousal * factor,
            updated_at=time() if now is None else float(now),
            source=self.state.source,
            cause=self.state.cause,
            attributed_person=self.state.attributed_person,
            attribution_confidence=self.state.attribution_confidence,
        )

    def observe(self, *, valence: float, arousal: float, intensity: float = 1.0, source: str, cause: str = "", attributed_person: str | None = None, attribution_confidence: float = 0.0) -> StandingAffectState:
        current = self.decayed()
        weight = self._clip(intensity, 0.0, 1.0) * 0.42
        current.valence = self._clip(current.valence * (1.0 - weight) + self._clip(valence, -1.0, 1.0) * weight, -1.0, 1.0)
        current.arousal = self._clip(current.arousal * (1.0 - weight) + self._clip(arousal, 0.0, 1.0) * weight, 0.0, 1.0)
        current.source = str(source or "unknown")[:80]
        current.cause = " ".join(str(cause or "").split())[:240]
        confidence = self._clip(attribution_confidence, 0.0, 1.0)
        current.attributed_person = str(attributed_person)[:120] if attributed_person and confidence >= 0.82 else None
        current.attribution_confidence = confidence if current.attributed_person else 0.0
        self.state = current
        self.save()
        return current

    def blend_into_emotional_state(self, emotional_state: Any, *, weight: float = 0.18) -> Any:
        standing = self.decayed()
        w = self._clip(weight, 0.0, 0.35)
        emotional_state.valence = self._clip(float(getattr(emotional_state, "valence", 0.0)) * (1.0 - w) + standing.valence * w, -1.0, 1.0)
        emotional_state.arousal = self._clip(float(getattr(emotional_state, "arousal", 0.0)) * (1.0 - w) + standing.arousal * w, 0.0, 1.0)
        metadata = dict(getattr(emotional_state, "metadata", {}) or {})
        metadata["standing_affect"] = self.snapshot()
        emotional_state.metadata = metadata
        return emotional_state

    def load(self) -> bool:
        if self.path is None or not self.path.exists():
            return False
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.state = StandingAffectState(**{k: raw.get(k, getattr(self.state, k)) for k in asdict(self.state)})
            return True
        except Exception:
            return False

    def save(self) -> bool:
        if self.path is None:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{self.path.name}.tmp")
        tmp.write_text(json.dumps(asdict(self.state), indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)
        return True

    def snapshot(self) -> dict[str, Any]:
        state = self.decayed()
        data = asdict(state)
        data.update({"version": self.VERSION, "half_life_seconds": self.half_life_seconds, "authority": "derived expressive continuity only"})
        return data
