"""Install the MaryV2 performance/experience hardening bundle.

This is intentionally thin wiring. It attaches derived/ephemeral systems to the
existing owners instead of introducing another Core, memory store, attention bus,
speaker floor, relationship database, or model router.
"""
from __future__ import annotations

from mary.expression.standing_affect import StandingAffectStore
from mary.distributed.stream_capabilities import StreamCapabilityCatalog
from mary.runtime.experience_quality import ExperienceQualityMonitor


class PerformanceHardeningBundle:
    VERSION = "13.7"

    def __init__(self, mary) -> None:
        self.mary = mary
        path = mary.config.paths.relationship / "standing_affect.json"
        self.standing_affect = StandingAffectStore(path)
        self.standing_affect.load()
        self.stream_capabilities = StreamCapabilityCatalog()
        self.experience_quality = ExperienceQualityMonitor()

    def observe_emotional_state(self, state, *, source: str = "conversation_emotion", cause: str = ""):
        self.standing_affect.observe(
            valence=float(getattr(state, "valence", 0.0)),
            arousal=float(getattr(state, "arousal", 0.0)),
            intensity=float(getattr(state, "intensity", 0.0)),
            source=source,
            cause=cause,
        )
        return self.standing_affect.blend_into_emotional_state(state)

    def snapshot(self) -> dict:
        return {
            "version": self.VERSION,
            "standing_affect": self.standing_affect.snapshot(),
            "stream_capabilities": self.stream_capabilities.snapshot(),
            "runtime_profile": (
                self.mary.performance_profiles.status()
                if callable(getattr(getattr(self.mary, "performance_profiles", None), "status", None))
                else {"enabled": False}
            ),
            "experience_quality": self.experience_quality.snapshot(),
            "authority": "wiring/telemetry only; canonical owners remain Mary Core subsystems",
        }


def install_performance_hardening(mary) -> PerformanceHardeningBundle:
    bundle = PerformanceHardeningBundle(mary)
    mary.performance_hardening = bundle
    mary.standing_affect = bundle.standing_affect
    mary.stream_capability_catalog = bundle.stream_capabilities
    mary.experience_quality = bundle.experience_quality
    return bundle
