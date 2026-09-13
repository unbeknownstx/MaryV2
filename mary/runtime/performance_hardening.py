"""Install MaryV2's bounded experience/presence composition helpers.

This remains thin composition wiring. It attaches projections and small bounded
runtime helpers to existing owners instead of introducing another Core, memory
store, attention bus, speaker floor, relationship database, or model router.
RelationalPresenceRuntime may ask the existing RelationshipManager to record
explicit relationship mode or completed shared-experience events; that manager
remains the only durable relationship authority.
"""
from __future__ import annotations

from mary.cognition.deliberation import DeliberationExecutor
from mary.distributed.stream_capabilities import StreamCapabilityCatalog
from mary.expression.social_delivery import SocialDeliveryPlanner
from mary.expression.standing_affect import StandingAffectStore
from mary.learning.strategy_advisor import StrategyAdvisor
from mary.learning.trajectory import TrajectoryRecorder
from mary.relationship.relational_presence import RelationalPresenceRuntime
from mary.runtime.experience_quality import ExperienceQualityMonitor


class PerformanceHardeningBundle:
    # This composition owner was introduced in 13.8. Newer attached capabilities
    # expose their own versions; do not repurpose the bundle's compatibility
    # version as a release number.
    VERSION = "13.8"

    def __init__(self, mary) -> None:
        self.mary = mary
        path = mary.config.paths.relationship / "standing_affect.json"
        self.standing_affect = StandingAffectStore(path)
        self.standing_affect.load()
        self.stream_capabilities = StreamCapabilityCatalog()
        self.experience_quality = ExperienceQualityMonitor()
        self.trajectory_telemetry = TrajectoryRecorder()
        self.deliberation_executor = DeliberationExecutor(
            recorder=self.trajectory_telemetry
        )
        self.strategy_advisor = StrategyAdvisor()

        # 13.8 relational presence is deliberately composed over the existing
        # canonical RelationshipManager. Durable mode/activity completions are
        # recorded by that owner; active activities and proposals stay ephemeral.
        self.relational_presence = RelationalPresenceRuntime(mary.relationship)
        self.social_delivery = SocialDeliveryPlanner()

    def observe_emotional_state(
        self,
        state,
        *,
        source: str = "conversation_emotion",
        cause: str = "",
    ):
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

    def strategy_proposal(self, *, task_class: str) -> dict:
        """Return proposal-only strategy evidence; never mutate runtime policy."""
        return self.strategy_advisor.propose(
            self.trajectory_telemetry.samples(),
            task_class=task_class,
        ).to_dict()

    def cognition_evidence_snapshot(self, *, limit: int = 8) -> dict:
        """Return bounded, content-free trajectory evidence + advisor proposals."""

        rows = list(self.trajectory_telemetry.samples())
        safe_rows = []
        allowed = {
            "trajectory_id",
            "task_class",
            "strategy",
            "passes",
            "branches",
            "verifier_score",
            "outcome",
            "reward",
            "provider_attempts",
            "tool_calls",
            "latency_ms",
            "total_tokens",
            "failure_kind",
            "tags",
        }
        for row in rows[-max(1, min(32, int(limit))):]:
            if not isinstance(row, dict):
                continue
            safe_rows.append({
                key: row.get(key)
                for key in allowed
                if key in row
            })

        proposals = {}
        for task_class in ("general", "conversation", "coding", "research"):
            proposals[task_class] = self.strategy_advisor.propose(
                rows,
                task_class=task_class,
            ).to_dict()

        return {
            "trajectory": self.trajectory_telemetry.snapshot(),
            "recent_samples": safe_rows,
            "strategy_proposals": proposals,
            "content_retained": False,
            "prompt_or_response_text_retained": False,
            "persistence": "process_local_evaluation_evidence",
            "authority": "evaluation_and_proposal_only",
        }

    def snapshot(self) -> dict:
        return {
            "version": self.VERSION,
            "standing_affect": self.standing_affect.snapshot(),
            "stream_capabilities": self.stream_capabilities.snapshot(),
            "runtime_profile": (
                self.mary.performance_profiles.status()
                if callable(
                    getattr(
                        getattr(self.mary, "performance_profiles", None),
                        "status",
                        None,
                    )
                )
                else {"enabled": False}
            ),
            "experience_quality": self.experience_quality.snapshot(),
            "trajectory_telemetry": self.trajectory_telemetry.snapshot(),
            "cognition_evidence": self.cognition_evidence_snapshot(),
            "deliberation_execution": {
                "version": self.deliberation_executor.VERSION,
                "private_reasoning_retained": False,
                "authority": "bounded_cognitive_execution",
            },
            "strategy_advisor": self.strategy_advisor.status(),
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
    mary.trajectory_telemetry = bundle.trajectory_telemetry
    mary.deliberation_executor = bundle.deliberation_executor
    mary.strategy_advisor = bundle.strategy_advisor
    mary.relational_presence = bundle.relational_presence
    mary.social_delivery = bundle.social_delivery
    return bundle
