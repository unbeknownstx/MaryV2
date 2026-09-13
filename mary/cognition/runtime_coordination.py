"""Unify per-turn cognition, compute, knowledge, deliberation and presentation hints.

This coordinator is a projection only. Existing Mary systems remain the owners
of identity, memory, relationship, permissions, provider eligibility and tool
execution. The output gives runtime surfaces one coherent plan to consume.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from mary.cognition.cognitive_character import CognitiveCharacterRuntime
from mary.cognition.deliberation import DeliberationGovernor
from mary.distributed.cognitive_workload import workload_from_cognitive_plan
from mary.expression.cognitive_embodiment import delivery_overrides_from_cognitive_plan
from mary.realtime.duplex_policy import DuplexInteractionPolicy


@dataclass(frozen=True)
class CharacterRuntimePlan:
    cognition: dict[str, Any]
    compute: dict[str, Any]
    knowledge: dict[str, Any]
    deliberation: dict[str, Any]
    realtime: dict[str, Any]
    presentation: dict[str, Any]
    authority: str = "coordination_projection_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CharacterRuntimeCoordinator:
    VERSION = "13.32"

    def __init__(
        self,
        *,
        cognition: CognitiveCharacterRuntime | None = None,
        deliberation: DeliberationGovernor | None = None,
        duplex: DuplexInteractionPolicy | None = None,
    ) -> None:
        self.cognition = cognition or CognitiveCharacterRuntime()
        self.deliberation = deliberation or DeliberationGovernor()
        self.duplex = duplex or DuplexInteractionPolicy()

    @staticmethod
    def _knowledge_policy(input_text: str, cognition: dict[str, Any]) -> dict[str, Any]:
        text = " ".join(str(input_text or "").lower().split())
        mode = str(cognition.get("cognitive_mode") or "balanced")
        academic = any(word in text for word in (
            "paper", "research", "study", "citation", "scientific", "academic", "journal"
        ))
        current = any(word in text for word in (
            "latest", "today", "current", "news", "recent", "right now", "new release"
        ))
        broad = mode == "deliberate" and any(word in text for word in (
            "research", "compare", "investigate", "find sources", "deep dive"
        ))
        if academic:
            categories = ["academic", "encyclopedic"]
        elif current:
            categories = ["web", "encyclopedic"]
        elif broad:
            categories = ["encyclopedic", "academic", "web"]
        else:
            categories = []
        return {
            "recommended": bool(categories),
            "categories": categories,
            "freshness_required": current,
            "authority": "external_evidence_only",
        }

    def plan_from_turn_state(
        self,
        turn_state: Any,
        *,
        compute_capability: str = "llm.local",
        privacy_required: bool = False,
        verifier_available: bool = True,
        external_verifier_authorized: bool = False,
    ) -> CharacterRuntimePlan:
        payload = (
            turn_state.to_dict()
            if callable(getattr(turn_state, "to_dict", None))
            else dict(turn_state or {})
        )
        cognition_plan = self.cognition.plan_from_turn_state(payload).to_dict()
        workload = workload_from_cognitive_plan(
            compute_capability,
            cognition_plan,
            privacy_required=privacy_required,
        )
        compute = {
            "capability": workload.capability,
            "operation": workload.operation,
            "realtime": workload.realtime,
            "privacy_required": workload.privacy_required,
            "local_preferred": workload.local_preferred,
            "cost_sensitive": workload.cost_sensitive,
            "estimated_seconds": workload.estimated_seconds,
            "authority": "scheduling_hint_only",
        }
        knowledge = self._knowledge_policy(
            str(payload.get("input_text") or ""),
            cognition_plan,
        )
        deliberation = self.deliberation.plan(
            cognition_plan,
            verifier_available=verifier_available,
            external_verifier_authorized=external_verifier_authorized,
            realtime=bool(workload.realtime),
        ).to_dict()
        realtime = self.duplex.plan(
            cognitive_mode=str(cognition_plan.get("cognitive_mode") or "balanced"),
            knowledge_recommended=bool(knowledge.get("recommended")),
        ).to_dict()
        presentation = delivery_overrides_from_cognitive_plan(cognition_plan)
        return CharacterRuntimePlan(
            cognition=cognition_plan,
            compute=compute,
            knowledge=knowledge,
            deliberation=deliberation,
            realtime=realtime,
            presentation=presentation,
        )
