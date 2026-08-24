"""Deterministic response-risk classification for local dialogue.

This production-capable module projects decisions already made by Mary's
intent, dialogue, authority, and conversation-lane systems.  It does not call a
model, retrieve state, own authority, or select a provider.  Production uses
the fail-closed response class before procedural realization.  The separate
``qwen_shadow_eligible`` helper remains benchmark-only and grants no production
route permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from mary.cognition.intent import Intent, IntentType
from mary.conversation.lanes import ConversationLane, LaneDecision

from .dialogue_acts import DialogueAct, DialoguePlan


class ResponseRiskClass(str, Enum):
    """Bounded response classes shared by production and hybrid benchmarks."""

    PRECISION_LOCAL = "precision_local"
    SOCIAL_LOW_RISK = "social_low_risk"
    OPEN_CONVERSATION = "open_conversation"
    THINKING_REQUIRED = "thinking_required"


@dataclass(frozen=True, slots=True)
class ResponseAuthorityContext:
    """Small authority projection supplied by Mary's existing local systems.

    ``authority_domains`` is intentionally declarative.  Any non-empty domain
    makes the turn precision-sensitive, including a domain unknown to this
    experiment.  That fail-closed behavior prevents new authority types from
    being treated as harmless social wording by accident.
    """

    authority_domains: tuple[str, ...] = ()
    structurally_represented: bool = False
    reference_sensitive: bool = False
    represented_stance: bool = False
    represented_uncertainty: bool = False
    represented_personal_state: bool = False
    requires_tool: bool = False
    requires_deep_reasoning: bool = False
    mutates_authoritative_state: bool = False
    open_ended: bool = False
    fact_free_social_follow_up: bool = False

    def __post_init__(self) -> None:
        domains = tuple(
            " ".join(str(item).split()).strip().lower()
            for item in self.authority_domains
        )
        if any(not item for item in domains):
            raise ValueError("authority domains must be non-empty strings")
        if len(set(domains)) != len(domains):
            raise ValueError("authority domains must be unique")
        object.__setattr__(self, "authority_domains", domains)

    @property
    def carries_precision_semantics(self) -> bool:
        return bool(
            self.authority_domains
            or self.structurally_represented
            or self.reference_sensitive
            or self.represented_stance
            or self.represented_uncertainty
            or self.represented_personal_state
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "authority_domains": list(self.authority_domains),
            "structurally_represented": self.structurally_represented,
            "reference_sensitive": self.reference_sensitive,
            "represented_stance": self.represented_stance,
            "represented_uncertainty": self.represented_uncertainty,
            "represented_personal_state": self.represented_personal_state,
            "requires_tool": self.requires_tool,
            "requires_deep_reasoning": self.requires_deep_reasoning,
            "mutates_authoritative_state": self.mutates_authoritative_state,
            "open_ended": self.open_ended,
            "fact_free_social_follow_up": self.fact_free_social_follow_up,
        }


@dataclass(frozen=True, slots=True)
class ResponseRiskDecision:
    response_class: ResponseRiskClass
    rationale: tuple[str, ...]
    deterministic: bool = True
    model_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "response_class": self.response_class.value,
            "rationale": list(self.rationale),
            "deterministic": self.deterministic,
            "model_used": self.model_used,
        }


_HARD_THINKING_INTENTS = {
    IntentType.TOOL_USE,
    IntentType.WEB_SEARCH,
    IntentType.COMMAND,
    IntentType.CREATOR_DIRECTIVE,
    IntentType.MEMORY_STORE,
}

_PRECISION_INTENTS = {
    IntentType.MEMORY_RECALL,
    IntentType.CONVERSATION_RECALL,
    IntentType.SELF_QUERY,
    IntentType.RELATIONSHIP_SHARE,
    IntentType.RELATIONSHIP_QUERY,
}

_PRECISION_ACTS = {
    DialogueAct.STATUS,
    DialogueAct.KNOWN_FACT,
    DialogueAct.KNOWN_PREFERENCE,
    DialogueAct.ANSWER,
}

_SOCIAL_ACTS = {
    DialogueAct.GREET,
    DialogueAct.ACKNOWLEDGE,
    DialogueAct.THANKS_RESPONSE,
    DialogueAct.GOODBYE,
    DialogueAct.LAUGH,
    DialogueAct.REACT,
}


def _intent_type(value: Intent | IntentType | str | None) -> IntentType | None:
    if isinstance(value, Intent):
        return value.intent_type
    if isinstance(value, IntentType):
        return value
    if value is None or not str(value).strip():
        return None
    try:
        return IntentType(str(value).strip().lower())
    except ValueError:
        return None


def _dialogue_act(value: DialoguePlan | DialogueAct | str | None) -> DialogueAct | None:
    if isinstance(value, DialoguePlan):
        return value.act
    if isinstance(value, DialogueAct):
        return value
    if value is None or not str(value).strip():
        return None
    try:
        return DialogueAct(str(value).strip().lower())
    except ValueError:
        return None


def _lane(value: LaneDecision | ConversationLane | str | None) -> ConversationLane | None:
    if isinstance(value, LaneDecision):
        return value.lane
    if isinstance(value, ConversationLane):
        return value
    if value is None or not str(value).strip():
        return None
    try:
        return ConversationLane(str(value).strip().lower())
    except ValueError:
        return None


def classify_response_risk(
    *,
    dialogue: DialoguePlan | DialogueAct | str | None,
    intent: Intent | IntentType | str | None,
    lane: LaneDecision | ConversationLane | str | None,
    authority: ResponseAuthorityContext | None = None,
) -> ResponseRiskDecision:
    """Classify without generation, retrieval, or production route changes.

    Explicit hard-work requirements win first.  Already represented semantics
    then win over style or lane hints.  The social class is a strict allowlist;
    everything else falls back to the existing open conversation path.
    """

    context = authority or ResponseAuthorityContext()
    act = _dialogue_act(dialogue)
    intent_type = _intent_type(intent)
    conversation_lane = _lane(lane)

    hard_reasons: list[str] = []
    if context.requires_tool:
        hard_reasons.append("authority context requires a tool")
    if context.requires_deep_reasoning:
        hard_reasons.append("authority context requires deep reasoning")
    if context.mutates_authoritative_state:
        hard_reasons.append("turn may mutate authoritative state")
    if intent_type in _HARD_THINKING_INTENTS:
        hard_reasons.append(f"existing intent is {intent_type.value}")
    if conversation_lane == ConversationLane.EXPERT:
        hard_reasons.append("existing lane is expert")
    if conversation_lane == ConversationLane.THINKING:
        hard_reasons.append("existing conversation lane requires thinking")
    if context.open_ended and context.carries_precision_semantics:
        hard_reasons.append(
            "mixed represented precision semantics and unrepresented open work"
        )
    if hard_reasons:
        return ResponseRiskDecision(
            ResponseRiskClass.THINKING_REQUIRED,
            tuple(hard_reasons),
        )

    precision_reasons: list[str] = []
    if context.authority_domains:
        precision_reasons.append(
            "authority-bearing semantics: " + ", ".join(context.authority_domains)
        )
    if context.structurally_represented:
        precision_reasons.append("answer is already structurally represented")
    if context.reference_sensitive:
        precision_reasons.append("agent/patient or pronoun ownership is reference-sensitive")
    if context.represented_stance:
        precision_reasons.append("represented Mary stance must be preserved")
    if context.represented_uncertainty:
        precision_reasons.append("represented uncertainty must be preserved")
    if context.represented_personal_state:
        precision_reasons.append("represented personal state must be preserved")
    if act in _PRECISION_ACTS:
        precision_reasons.append(f"dialogue act {act.value} is precision-sensitive")
    if intent_type in _PRECISION_INTENTS:
        precision_reasons.append(f"existing intent {intent_type.value} is authoritative")
    if precision_reasons:
        return ResponseRiskDecision(
            ResponseRiskClass.PRECISION_LOCAL,
            tuple(precision_reasons),
        )

    if context.open_ended:
        return ResponseRiskDecision(
            ResponseRiskClass.OPEN_CONVERSATION,
            ("authority context marks the turn open-ended",),
        )

    social_allowed = conversation_lane == ConversationLane.SOCIAL_INSTANT and (
        act in _SOCIAL_ACTS
        or (act == DialogueAct.FOLLOW_UP and context.fact_free_social_follow_up)
    )
    if social_allowed:
        return ResponseRiskDecision(
            ResponseRiskClass.SOCIAL_LOW_RISK,
            (
                f"dialogue act {act.value} is on the bounded social allowlist",
                "no authority-bearing or reference-sensitive semantics are present",
            ),
        )

    precision_fallback_reasons: list[str] = [
        "insufficient bounded evidence for the low-risk social or open class"
    ]
    if act is not None:
        precision_fallback_reasons.append(
            f"dialogue act {act.value} is not safely classifiable as social"
        )
    if conversation_lane is not None:
        precision_fallback_reasons.append(
            f"existing lane is {conversation_lane.value}"
        )
    return ResponseRiskDecision(
        ResponseRiskClass.PRECISION_LOCAL,
        tuple(precision_fallback_reasons),
    )


def qwen_shadow_eligible(
    decision: ResponseRiskDecision,
    *,
    explicit_precision_probe: bool = False,
) -> bool:
    """Return benchmark eligibility; this is not a production route choice."""

    if decision.response_class == ResponseRiskClass.SOCIAL_LOW_RISK:
        return True
    return bool(
        explicit_precision_probe
        and decision.response_class == ResponseRiskClass.PRECISION_LOCAL
    )
