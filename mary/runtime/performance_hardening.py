"""Install MaryV2's bounded experience/presence composition helpers.

This remains thin composition wiring. It attaches projections and small bounded
runtime helpers to existing owners instead of introducing another Core, memory
store, attention bus, speaker floor, relationship database, or model router.
RelationalPresenceRuntime may ask the existing RelationshipManager to record
explicit relationship mode or completed shared-experience events; that manager
remains the only durable relationship authority.
"""
from __future__ import annotations

from mary.expression.social_delivery import SocialDeliveryPlanner
from mary.expression.standing_affect import StandingAffectStore
from mary.distributed.stream_capabilities import StreamCapabilityCatalog
from mary.relationship.relational_presence import RelationalPresenceRuntime
from mary.runtime.experience_quality import ExperienceQualityMonitor


class PerformanceHardeningBundle:
    VERSION = "13.8"

    def __init__(self, mary) -> None:
        self.mary = mary
        path = mary.config.paths.relationship / "standing_affect.json"
        self.standing_affect = StandingAffectStore(path)
        self.standing_affect.load()
        self.stream_capabilities = StreamCapabilityCatalog()
        self.experience_quality = ExperienceQualityMonitor()

        # 13.8 relational presence is deliberately composed over the existing
        # canonical RelationshipManager. Durable mode/activity completions are
        # recorded by that owner; active activities and proposals stay ephemeral.
        self.relational_presence = RelationalPresenceRuntime(mary.relationship)
        self.social_delivery = SocialDeliveryPlanner()

    def observe_emotional_state(self, state, *, source: str = "conversation_emotion", cause: str = ""):
        self.standing_affect.observe(
            valence=float(getattr(state, "valence", 0.0)),
            arousal=float(getattr(state, "arousal", 0.0)),
            intensity=float(getattr(state, "intensity", 0.0)),
            source=source,
            cause=cause,
        )
        return self.standing_affect.blend_into_emotional_state(state)

    def delivery_envelope(self, state=None, *, privacy_scope: str = "private") -> dict:
        return self.social_delivery.build(
            relationship_mode=self.relational_presence.relationship_mode(),
            emotional_state=state,
            privacy_scope=privacy_scope,
        ).to_dict()

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
            "relational_presence": self.relational_presence.snapshot(),
            "social_delivery": self.delivery_envelope(),
            "authority": (
                "composition/projection layer only; durable relationship writes "
                "delegate to the canonical RelationshipManager"
            ),
        }


def install_performance_hardening(mary) -> PerformanceHardeningBundle:
    bundle = PerformanceHardeningBundle(mary)
    mary.performance_hardening = bundle
    mary.standing_affect = bundle.standing_affect
    mary.stream_capability_catalog = bundle.stream_capabilities
    mary.experience_quality = bundle.experience_quality
    mary.relational_presence = bundle.relational_presence
    mary.social_delivery = bundle.social_delivery
    return bundle
