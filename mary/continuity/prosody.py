"""Prosody-aware turn-taking signals without psychological inference."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProsodyObservation:
    speech_rate_wpm: float | None = None
    pause_ms: float = 0.0
    rms_ratio: float = 1.0
    pitch_range_hz: float | None = None
    terminal_pitch_slope: float | None = None
    voiced: bool = True


class TurnTakingAdvisor:
    """Use acoustic observables to advise floor timing, never infer hidden emotion."""

    VERSION = 1

    def assess(self, observation: ProsodyObservation) -> dict[str, Any]:
        pause = max(0.0, float(observation.pause_ms))
        slope = observation.terminal_pitch_slope
        likely_finished = pause >= 650.0
        if slope is not None and slope < -0.20 and pause >= 350.0:
            likely_finished = True
        likely_continuing = bool(slope is not None and slope > 0.25 and pause < 500.0)
        energetic_delivery = float(observation.rms_ratio) >= 1.8
        fast_delivery = bool(observation.speech_rate_wpm is not None and observation.speech_rate_wpm >= 190.0)
        return {
            "version": self.VERSION,
            "likely_finished": bool(likely_finished and not likely_continuing),
            "likely_continuing": likely_continuing,
            "backchannel_ok": bool(observation.voiced and pause >= 180.0 and not likely_finished),
            "energetic_delivery": energetic_delivery,
            "fast_delivery": fast_delivery,
            "observables": asdict(observation),
            "policy": "acoustic expression only; no hidden-emotion or mental-state claim",
        }
