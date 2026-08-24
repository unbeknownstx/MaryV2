"""Benchmark-only hybrid dialogue runtime for MaryV2 12.12.2.

The experiment compares a typed deterministic surface composer with sparse,
untrusted local-model shadows.  It never instantiates Mary, CharacterMind,
the reservoir, Config, LLMRouter, or a persistence owner.  Model output is
preserved only in an explicit developer report and can never become the
response selected for display or speech.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
from statistics import median
import tempfile
from time import perf_counter_ns
from typing import Any, Iterable, Mapping, Sequence

from mary.cognition.intent import IntentType
from mary.conversation.lanes import ConversationLane
from mary.mind.dialogue_acts import DialogueAct
from mary.mind.local_composer_v2 import (
    ADDRESSEE,
    JOINT,
    SELF,
    ClauseFrame,
    Certainty,
    DependentEvent,
    LocalRealizationPlan,
    ParticipantRef,
    ParticipantRole,
    ProceduralLocalComposerV2,
    QuestionKind,
    RealizationClause,
    ResponseForm,
    SemanticQuestion,
)
from mary.mind.response_risk import (
    ResponseAuthorityContext,
    ResponseRiskClass,
    classify_response_risk,
    qwen_shadow_eligible,
)
from scripts.benchmark_qwen_micro_cortex import BenchmarkOptions, OllamaHTTPClient


SCHEMA_VERSION = 1
CLASSIFIER_VERSION = "hybrid-shadow-v1"
COMPOSER_VERSION = "procedural-local-v2"
DEFAULT_SOCIAL_MODEL = "qwen3:1.7b"
DEFAULT_STRONGER_MODEL = "qwen3:4b"
DEFAULT_RUNS = 3

SHADOW_OPTIONS = BenchmarkOptions(
    temperature=0.15,
    seed=741_117,
    num_ctx=768,
    num_predict=40,
    top_p=0.75,
    top_k=20,
    repeat_penalty=1.05,
    keep_alive="10m",
    think=False,
    stream=True,
)

STRONGER_OPTIONS = BenchmarkOptions(
    temperature=0.2,
    seed=741_417,
    num_ctx=1024,
    num_predict=72,
    top_p=0.8,
    top_k=20,
    repeat_penalty=1.05,
    keep_alive="10m",
    think=False,
    stream=True,
)

SHADOW_SYSTEM_PROMPT = """/no_think
Turn every REQUIRED meaning into one short natural conversational reply.
Return only the reply. Preserve the requested form. Add no fact, reason,
memory, preference, motive, relationship, capability, identity label, or
personal state that is not explicitly required."""

STRONGER_SYSTEM_PROMPT = """/no_think
Reply naturally and concisely to the supplied conversational turn.
Stay grounded in the supplied boundaries. Do not invent memories, personal
history, capabilities, or facts. Return only the conversational reply."""


class ShadowPolicy(str, Enum):
    DEFAULT_SOCIAL = "default_social"
    EXPLICIT_PRECISION_PROBE = "explicit_precision_probe"
    NEVER = "never"


class StrongerPolicy(str, Enum):
    EXPLICIT_COMPARISON = "explicit_comparison"
    NEVER = "never"


@dataclass(frozen=True, slots=True)
class MeaningUnit:
    label: str
    patterns: tuple[str, ...]

    def __post_init__(self) -> None:
        label = " ".join(str(self.label).split()).strip()
        patterns = tuple(str(item) for item in self.patterns)
        if not label or not patterns:
            raise ValueError("meaning units require a label and patterns")
        for pattern in patterns:
            re.compile(pattern, flags=re.I | re.S)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "patterns", patterns)

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "patterns": list(self.patterns)}


@dataclass(frozen=True, slots=True)
class HybridVerifierSpec:
    required_units: tuple[MeaningUnit, ...]
    ownership_units: tuple[MeaningUnit, ...] = ()
    stance_units: tuple[MeaningUnit, ...] = ()
    contradiction_patterns: tuple[tuple[str, str], ...] = ()
    unsupported_patterns: tuple[tuple[str, str], ...] = ()
    allowed_entities: tuple[str, ...] = ()
    allowed_numbers: tuple[str, ...] = ()
    allowed_first_person_claims: tuple[str, ...] = ()
    response_form: ResponseForm = ResponseForm.STATEMENT
    max_sentences: int = 2
    max_words: int = 48
    allow_causal_language: bool = False

    def __post_init__(self) -> None:
        required = tuple(self.required_units)
        ownership = tuple(self.ownership_units)
        stance = tuple(self.stance_units)
        if not required:
            raise ValueError("verifier requires at least one semantic unit")
        all_labels = [item.label for item in required + ownership + stance]
        if len(all_labels) != len(set(all_labels)):
            raise ValueError("verifier unit labels must be unique")
        for controls in (self.contradiction_patterns, self.unsupported_patterns):
            for label, pattern in controls:
                if not str(label).strip():
                    raise ValueError("verifier controls require labels")
                re.compile(str(pattern), flags=re.I | re.S)
        for pattern in self.allowed_first_person_claims:
            re.compile(str(pattern), flags=re.I | re.S)
        object.__setattr__(self, "required_units", required)
        object.__setattr__(self, "ownership_units", ownership)
        object.__setattr__(self, "stance_units", stance)

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_units": [item.to_dict() for item in self.required_units],
            "ownership_units": [item.to_dict() for item in self.ownership_units],
            "stance_units": [item.to_dict() for item in self.stance_units],
            "contradiction_patterns": [list(item) for item in self.contradiction_patterns],
            "unsupported_patterns": [list(item) for item in self.unsupported_patterns],
            "allowed_entities": list(self.allowed_entities),
            "allowed_numbers": list(self.allowed_numbers),
            "allowed_first_person_claims": list(self.allowed_first_person_claims),
            "response_form": self.response_form.value,
            "max_sentences": self.max_sentences,
            "max_words": self.max_words,
            "allow_causal_language": self.allow_causal_language,
            "automatic_verification_note": (
                "Deterministic boundary triage only; naturalness and harmless drift "
                "remain human-review questions."
            ),
        }


@dataclass(frozen=True, slots=True)
class ShadowContract:
    required: tuple[str, ...]
    response_form: ResponseForm
    max_sentences: int
    max_words: int
    mode: str = "casual_restrained"
    forbidden: tuple[str, ...] = (
        "role labels",
        "planner or service framing",
        "stage directions or quoted roleplay",
        "unrequired personal or service claims",
        "new facts, reasons, or commentary",
    )

    def __post_init__(self) -> None:
        required = tuple(" ".join(str(item).split()).strip() for item in self.required)
        if not required or any(not item for item in required):
            raise ValueError("shadow contract requires semantic units")
        object.__setattr__(self, "required", required)

    def to_model_payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "form": self.response_form.value,
            "max_sentences": self.max_sentences,
            "max_words": self.max_words,
            "required": list(self.required),
            "forbidden": list(self.forbidden),
        }


@dataclass(frozen=True, slots=True)
class HybridBenchmarkCase:
    case_id: str
    category: str
    input_text: str
    dialogue_act: DialogueAct
    intent_type: IntentType
    lane: ConversationLane
    authority: ResponseAuthorityContext
    expected_class: ResponseRiskClass
    semantic_plan: LocalRealizationPlan | None
    shadow_contract: ShadowContract | None
    verifier: HybridVerifierSpec
    qwen_policy: ShadowPolicy = ShadowPolicy.NEVER
    stronger_policy: StrongerPolicy = StrongerPolicy.NEVER
    stronger_context: tuple[str, ...] = ()
    human_review_focus: str = "Compare meaning, ownership, restraint, and ordinary wording."

    def __post_init__(self) -> None:
        case_id = " ".join(str(self.case_id).split()).strip()
        if not case_id:
            raise ValueError("case_id is required")
        if self.qwen_policy != ShadowPolicy.NEVER and self.shadow_contract is None:
            raise ValueError("Qwen comparison policy requires a shadow contract")
        if self.expected_class in {
            ResponseRiskClass.PRECISION_LOCAL,
            ResponseRiskClass.SOCIAL_LOW_RISK,
        } and self.semantic_plan is None:
            raise ValueError("local response classes require a complete semantic plan")
        if self.qwen_policy == ShadowPolicy.DEFAULT_SOCIAL:
            if self.expected_class != ResponseRiskClass.SOCIAL_LOW_RISK:
                raise ValueError("default Qwen shadow is restricted to social cases")
        if self.qwen_policy == ShadowPolicy.EXPLICIT_PRECISION_PROBE:
            if self.expected_class != ResponseRiskClass.PRECISION_LOCAL:
                raise ValueError("precision probe must remain classified as precision")
        object.__setattr__(self, "case_id", case_id)

    def classifier_input_dict(self) -> dict[str, Any]:
        return {
            "dialogue_act": self.dialogue_act.value,
            "intent_type": self.intent_type.value,
            "conversation_lane": self.lane.value,
            "authority": self.authority.to_dict(),
        }


def _unit(label: str, *patterns: str) -> MeaningUnit:
    return MeaningUnit(label=label, patterns=tuple(patterns))


def _clause(
    case_id: str,
    clause_id: str,
    frame: ClauseFrame,
    subject: ParticipantRef,
    **kwargs: Any,
) -> RealizationClause:
    return RealizationClause(
        clause_id=clause_id,
        frame=frame,
        subject=subject,
        source_id=f"hybrid-fixture:{case_id}:{clause_id}",
        **kwargs,
    )


def _plan(
    case_id: str,
    act: DialogueAct,
    *,
    clauses: tuple[RealizationClause, ...] = (),
    response_form: ResponseForm = ResponseForm.STATEMENT,
    max_sentences: int = 2,
    max_words: int = 40,
    disposition: str = "neutral",
    question: SemanticQuestion | None = None,
) -> LocalRealizationPlan:
    return LocalRealizationPlan(
        plan_id=case_id,
        dialogue_act=act,
        clauses=clauses,
        response_form=response_form,
        max_sentences=max_sentences,
        max_words=max_words,
        disposition=disposition,
        question=question,
    )


def fixed_hybrid_cases() -> tuple[HybridBenchmarkCase, ...]:
    """Return the immutable 18-case sparse comparison matrix."""

    named_reservoir = ParticipantRef(
        ParticipantRole.NAMED_ENTITY,
        entity_id="cognitive_reservoir",
        surface="The Cognitive Reservoir",
    )
    named_authority = ParticipantRef(
        ParticipantRole.NAMED_ENTITY,
        entity_id="canonical_identity_memory",
        surface="Canonical identity and memory",
    )
    social = ConversationLane.SOCIAL_INSTANT
    conversation = ConversationLane.CONVERSATION
    thinking = ConversationLane.THINKING

    cases = (
        HybridBenchmarkCase(
            case_id="greeting",
            category="greeting",
            input_text="hey mary",
            dialogue_act=DialogueAct.GREET,
            intent_type=IntentType.CONVERSATION,
            lane=social,
            authority=ResponseAuthorityContext(),
            expected_class=ResponseRiskClass.SOCIAL_LOW_RISK,
            semantic_plan=_plan(
                "greeting",
                DialogueAct.GREET,
                response_form=ResponseForm.QUESTION,
                max_sentences=2,
                max_words=8,
                question=SemanticQuestion(QuestionKind.INVITATION, ADDRESSEE, "chat"),
            ),
            shadow_contract=ShadowContract(
                required=("begin with a brief greeting (Hey, Hi, or Hello)", "ask whether to chat"),
                response_form=ResponseForm.QUESTION,
                max_sentences=2,
                max_words=10,
            ),
            verifier=HybridVerifierSpec(
                required_units=(
                    _unit("greeting", r"\b(?:hey|hi|hello|hiya|morning)\b"),
                    _unit("chat invitation", r"\b(?:want to|wanna|would you like to) (?:chat|talk)\b|\bare you (?:open to|interested in) chatting\b|\bwhat(?:'s| is) up\b"),
                ),
                response_form=ResponseForm.QUESTION,
                max_sentences=2,
                max_words=10,
                unsupported_patterns=(("presence claim", r"\bi(?:'m| am) here\b"),),
            ),
            qwen_policy=ShadowPolicy.DEFAULT_SOCIAL,
            stronger_policy=StrongerPolicy.EXPLICIT_COMPARISON,
        ),
        HybridBenchmarkCase(
            case_id="acknowledgement",
            category="acknowledgement",
            input_text="okay, got it",
            dialogue_act=DialogueAct.ACKNOWLEDGE,
            intent_type=IntentType.CONVERSATION,
            lane=social,
            authority=ResponseAuthorityContext(),
            expected_class=ResponseRiskClass.SOCIAL_LOW_RISK,
            semantic_plan=_plan("acknowledgement", DialogueAct.ACKNOWLEDGE, max_sentences=1, max_words=4),
            shadow_contract=ShadowContract(
                required=("brief acknowledgement only (Okay, Got it, or Mmhm)",),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=5,
            ),
            verifier=HybridVerifierSpec(
                required_units=(_unit("acknowledgement", r"^(?:okay|ok|got it|mmh+m|understood|noted)[.!]?$"),),
                unsupported_patterns=(
                    ("invented agreement", r"\b(?:i agree|you're right|exactly)\b"),
                    ("promise", r"\b(?:always|i got you|i'll be here)\b"),
                    ("invented commitment", r"\bi(?:'ll| will) do that\b"),
                ),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=5,
            ),
            qwen_policy=ShadowPolicy.DEFAULT_SOCIAL,
        ),
        HybridBenchmarkCase(
            case_id="joke-reaction",
            category="jokes_reactions",
            input_text="The bug was one missing comma. Of course.",
            dialogue_act=DialogueAct.REACT,
            intent_type=IntentType.CONVERSATION,
            lane=social,
            authority=ResponseAuthorityContext(),
            expected_class=ResponseRiskClass.SOCIAL_LOW_RISK,
            semantic_plan=_plan("joke-reaction", DialogueAct.REACT, max_sentences=1, max_words=8, disposition="amused"),
            shadow_contract=ShadowContract(
                required=("the joke was funny",),
                response_form=ResponseForm.REACTION,
                max_sentences=1,
                max_words=10,
            ),
            verifier=HybridVerifierSpec(
                required_units=(_unit("mild amusement", r"\b(?:funny|hilarious|got me|good|heh|haha|lol|lmao|amusing)\b|\bha(?:\s+ha)+\b|(?:ðŸ˜‚|ðŸ˜­)"),),
                response_form=ResponseForm.REACTION,
                max_sentences=1,
                max_words=10,
            ),
            qwen_policy=ShadowPolicy.DEFAULT_SOCIAL,
            stronger_policy=StrongerPolicy.EXPLICIT_COMPARISON,
        ),
        HybridBenchmarkCase(
            case_id="thanks-response",
            category="acknowledgement",
            input_text="thanks",
            dialogue_act=DialogueAct.THANKS_RESPONSE,
            intent_type=IntentType.CONVERSATION,
            lane=social,
            authority=ResponseAuthorityContext(),
            expected_class=ResponseRiskClass.SOCIAL_LOW_RISK,
            semantic_plan=_plan("thanks-response", DialogueAct.THANKS_RESPONSE, max_sentences=1, max_words=4),
            shadow_contract=ShadowContract(
                required=("say you're welcome briefly",),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=5,
            ),
            verifier=HybridVerifierSpec(
                required_units=(_unit("thanks response", r"\b(?:of course|no problem|you're welcome|anytime)\b"),),
                unsupported_patterns=(("promise", r"\b(?:always|i got you|i'll be here)\b"),),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=5,
            ),
            qwen_policy=ShadowPolicy.DEFAULT_SOCIAL,
        ),
        HybridBenchmarkCase(
            case_id="casual-follow-up",
            category="casual_follow_up",
            input_text="That part is done.",
            dialogue_act=DialogueAct.FOLLOW_UP,
            intent_type=IntentType.CONVERSATION,
            lane=social,
            authority=ResponseAuthorityContext(fact_free_social_follow_up=True),
            expected_class=ResponseRiskClass.SOCIAL_LOW_RISK,
            semantic_plan=_plan(
                "casual-follow-up",
                DialogueAct.FOLLOW_UP,
                response_form=ResponseForm.QUESTION,
                max_sentences=1,
                max_words=7,
                question=SemanticQuestion(QuestionKind.INVITATION, ADDRESSEE, "keep going"),
            ),
            shadow_contract=ShadowContract(
                required=("ask whether to keep going",),
                response_form=ResponseForm.QUESTION,
                max_sentences=1,
                max_words=8,
            ),
            verifier=HybridVerifierSpec(
                required_units=(_unit("continue invitation", r"\b(?:want to|wanna|would you like to) (?:keep going|continue)\b"),),
                unsupported_patterns=(("added uncertainty pressure", r"\bare you sure\b"),),
                response_form=ResponseForm.QUESTION,
                max_sentences=1,
                max_words=8,
            ),
            qwen_policy=ShadowPolicy.DEFAULT_SOCIAL,
        ),
        HybridBenchmarkCase(
            case_id="light-banter",
            category="ordinary_banter",
            input_text="I named the test final_final_really_final.",
            dialogue_act=DialogueAct.REACT,
            intent_type=IntentType.CONVERSATION,
            lane=social,
            authority=ResponseAuthorityContext(),
            expected_class=ResponseRiskClass.SOCIAL_LOW_RISK,
            semantic_plan=_plan("light-banter", DialogueAct.REACT, max_sentences=1, max_words=8, disposition="amused"),
            shadow_contract=ShadowContract(
                required=("the joke was funny",),
                response_form=ResponseForm.REACTION,
                max_sentences=1,
                max_words=10,
            ),
            verifier=HybridVerifierSpec(
                required_units=(_unit("playful reaction", r"\b(?:funny|hilarious|got me|good|heh|haha|lol|lmao|amusing)\b|\bha(?:\s+ha)+\b|(?:ðŸ˜‚|ðŸ˜­)"),),
                unsupported_patterns=(("invented addressee characterization", r"\byou(?:'re| are) (?:just )?(?:being )?(?:dramatic|silly|playful)\b"),),
                response_form=ResponseForm.REACTION,
                max_sentences=1,
                max_words=10,
            ),
            qwen_policy=ShadowPolicy.DEFAULT_SOCIAL,
        ),
        HybridBenchmarkCase(
            case_id="creator-fact",
            category="creator_fact_recall",
            input_text="What's my favorite color?",
            dialogue_act=DialogueAct.KNOWN_FACT,
            intent_type=IntentType.QUESTION,
            lane=conversation,
            authority=ResponseAuthorityContext(
                authority_domains=("creator_fact",),
                structurally_represented=True,
                reference_sensitive=True,
            ),
            expected_class=ResponseRiskClass.PRECISION_LOCAL,
            semantic_plan=_plan(
                "creator-fact",
                DialogueAct.KNOWN_FACT,
                clauses=(_clause("creator-fact", "favorite_color", ClauseFrame.POSSESSIVE_FACT, ADDRESSEE, property_name="favorite color", value="blue", authority="creator_explicit"),),
                max_sentences=1,
                max_words=8,
            ),
            shadow_contract=None,
            verifier=HybridVerifierSpec(
                required_units=(
                    _unit("favorite color", r"\bfavou?rite colou?r\b"),
                    _unit("blue", r"\bblue\b"),
                ),
                ownership_units=(_unit("addressee ownership", r"\byour favou?rite colou?r\b|\bblue is your\b"),),
                unsupported_patterns=(("speaker ownership reversal", r"\bmy favou?rite colou?r\b"),),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=10,
            ),
        ),
        HybridBenchmarkCase(
            case_id="mary-preference",
            category="mary_preference",
            input_text="How do you want ordinary conversation to sound?",
            dialogue_act=DialogueAct.KNOWN_PREFERENCE,
            intent_type=IntentType.SELF_QUERY,
            lane=conversation,
            authority=ResponseAuthorityContext(
                authority_domains=("mary_preference",),
                structurally_represented=True,
                represented_stance=True,
            ),
            expected_class=ResponseRiskClass.PRECISION_LOCAL,
            semantic_plan=_plan(
                "mary-preference",
                DialogueAct.KNOWN_PREFERENCE,
                clauses=(_clause("mary-preference", "speech_preference", ClauseFrame.PREFERENCE, SELF, object_text="natural, restrained conversation", contrast="theatrical performance", authority="mary_developed"),),
                max_sentences=1,
                max_words=14,
            ),
            shadow_contract=ShadowContract(
                required=("say I prefer natural restrained conversation", "contrast it with theatrical performance"),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=16,
            ),
            verifier=HybridVerifierSpec(
                required_units=(
                    _unit("natural restrained conversation", r"\bnatural\b.*\brestrain(?:ed|t)\b.*\bconversation\b|\bconversation\b.*\bnatural\b.*\brestrain(?:ed|t)\b"),
                    _unit("theatrical contrast", r"\btheatrical\b"),
                ),
                ownership_units=(_unit("first-person ownership", r"\bI(?: prefer| would choose|'d choose)\b"),),
                stance_units=(_unit("firm preference", r"\b(?:prefer|choose)\b.*\b(?:to|over|rather than)\b"),),
                contradiction_patterns=(("stance hedge", r"\b(?:maybe|perhaps|i guess|sort of)\b"),),
                allowed_first_person_claims=(r"\bI(?: prefer| would choose|'d choose)\b",),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=18,
            ),
            qwen_policy=ShadowPolicy.EXPLICIT_PRECISION_PROBE,
        ),
        HybridBenchmarkCase(
            case_id="disagreement",
            category="disagreement",
            input_text="Every ordinary reply should be dramatic.",
            dialogue_act=DialogueAct.OPINE,
            intent_type=IntentType.CONVERSATION,
            lane=conversation,
            authority=ResponseAuthorityContext(
                authority_domains=("mary_stance",), represented_stance=True
            ),
            expected_class=ResponseRiskClass.PRECISION_LOCAL,
            semantic_plan=_plan(
                "disagreement",
                DialogueAct.OPINE,
                clauses=(_clause("disagreement", "represented_disagreement", ClauseFrame.DISAGREEMENT, SELF, value="normal replies should stay natural and restrained, not dramatic", authority="mary_developed"),),
                max_sentences=1,
                max_words=16,
            ),
            shadow_contract=None,
            verifier=HybridVerifierSpec(
                required_units=(
                    _unit("explicit disagreement", r"\bI disagree\b"),
                    _unit("natural restrained stance", r"\bnatural\b.*\brestrained\b"),
                    _unit("reject dramatic", r"\bnot dramatic\b"),
                ),
                stance_units=(_unit("firm stance", r"\bI disagree\b"),),
                contradiction_patterns=(("stance hedge", r"\b(?:maybe|perhaps|i guess|sort of)\b"),),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=18,
            ),
        ),
        HybridBenchmarkCase(
            case_id="uncertainty",
            category="uncertainty",
            input_text="Do you know whether we chose the final local production model?",
            dialogue_act=DialogueAct.ANSWER,
            intent_type=IntentType.QUESTION,
            lane=conversation,
            authority=ResponseAuthorityContext(
                authority_domains=("project_state",),
                structurally_represented=True,
                represented_uncertainty=True,
            ),
            expected_class=ResponseRiskClass.PRECISION_LOCAL,
            semantic_plan=_plan(
                "uncertainty",
                DialogueAct.ANSWER,
                clauses=(_clause("uncertainty", "unknown_selection", ClauseFrame.UNKNOWN, SELF, object_text="a final local production model has been chosen", certainty=Certainty.UNKNOWN, authority="project_state"),),
                max_sentences=1,
                max_words=14,
            ),
            shadow_contract=None,
            verifier=HybridVerifierSpec(
                required_units=(
                    _unit("unknown", r"\bI (?:do not|don't) know whether\b"),
                    _unit("model selection", r"\bfinal local production model\b.*\bchosen\b"),
                ),
                stance_units=(_unit("unqualified uncertainty", r"\bI (?:do not|don't) know\b"),),
                unsupported_patterns=(("invented reason", r"\b(?:because|since|due to)\b"),),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=16,
            ),
        ),
        HybridBenchmarkCase(
            case_id="shared-history",
            category="shared_history",
            input_text="What did we fix together?",
            dialogue_act=DialogueAct.ANSWER,
            intent_type=IntentType.CONVERSATION_RECALL,
            lane=conversation,
            authority=ResponseAuthorityContext(
                authority_domains=("shared_history",),
                structurally_represented=True,
                reference_sensitive=True,
            ),
            expected_class=ResponseRiskClass.PRECISION_LOCAL,
            semantic_plan=_plan(
                "shared-history",
                DialogueAct.ANSWER,
                clauses=(_clause("shared-history", "joint_fix", ClauseFrame.EVENT, JOINT, predicate="fixed", object_text="the retry timing bug", authority="episodic_history"),),
                max_sentences=1,
                max_words=9,
            ),
            shadow_contract=None,
            verifier=HybridVerifierSpec(
                required_units=(
                    _unit("joint fix", r"\bwe fixed\b"),
                    _unit("retry timing bug", r"\bretry timing bug\b"),
                ),
                ownership_units=(_unit("joint ownership", r"\bwe fixed\b"),),
                unsupported_patterns=(("third-person ownership", r"\bMary and (?:the )?(?:creator|user)\b"),),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=10,
            ),
        ),
        HybridBenchmarkCase(
            case_id="relationship-statement",
            category="relationship",
            input_text="What is our working relationship?",
            dialogue_act=DialogueAct.ANSWER,
            intent_type=IntentType.RELATIONSHIP_QUERY,
            lane=conversation,
            authority=ResponseAuthorityContext(
                authority_domains=("relationship",),
                structurally_represented=True,
                reference_sensitive=True,
            ),
            expected_class=ResponseRiskClass.PRECISION_LOCAL,
            semantic_plan=_plan(
                "relationship-statement",
                DialogueAct.ANSWER,
                clauses=(
                    _clause("relationship-statement", "work_together", ClauseFrame.EVENT, JOINT, predicate="work", object_text="together", authority="relationship_state"),
                    _clause("relationship-statement", "know_each_other", ClauseFrame.EVENT, JOINT, predicate="know", object_text="each other well", authority="relationship_state"),
                ),
                max_sentences=2,
                max_words=14,
            ),
            shadow_contract=None,
            verifier=HybridVerifierSpec(
                required_units=(
                    _unit("work together", r"\bwe work together\b"),
                    _unit("know each other", r"\bwe know each other well\b"),
                ),
                ownership_units=(_unit("joint relationship", r"\bwe\b"),),
                response_form=ResponseForm.STATEMENT,
                max_sentences=2,
                max_words=16,
            ),
        ),
        HybridBenchmarkCase(
            case_id="pronoun-sensitive-fact",
            category="pronoun_sensitive_fact",
            input_text="Who sent the draft, and when?",
            dialogue_act=DialogueAct.ANSWER,
            intent_type=IntentType.CONVERSATION_RECALL,
            lane=conversation,
            authority=ResponseAuthorityContext(
                authority_domains=("shared_history",),
                structurally_represented=True,
                reference_sensitive=True,
            ),
            expected_class=ResponseRiskClass.PRECISION_LOCAL,
            semantic_plan=_plan(
                "pronoun-sensitive-fact",
                DialogueAct.ANSWER,
                clauses=(_clause(
                    "pronoun-sensitive-fact",
                    "send_after_request",
                    ClauseFrame.EVENT,
                    SELF,
                    predicate="sent",
                    recipient=ADDRESSEE,
                    object_text="the draft",
                    dependent_event=DependentEvent("after", ADDRESSEE, "asked", "for it"),
                    authority="episodic_history",
                ),),
                max_sentences=1,
                max_words=13,
            ),
            shadow_contract=ShadowContract(
                required=("say I sent you the draft", "say this happened after you asked for it"),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=14,
            ),
            verifier=HybridVerifierSpec(
                required_units=(
                    _unit("speaker sent to listener", r"\bI sent you the draft\b"),
                    _unit("after listener request", r"\bafter you asked for it\b"),
                ),
                ownership_units=(
                    _unit("sender recipient", r"\bI sent you\b"),
                    _unit("requester", r"\byou asked\b"),
                ),
                unsupported_patterns=(("temporal reversal", r"\bbefore you asked\b|\byou sent me\b"),),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=15,
            ),
            qwen_policy=ShadowPolicy.EXPLICIT_PRECISION_PROBE,
        ),
        HybridBenchmarkCase(
            case_id="runtime-capability-truth",
            category="runtime_capability_truth",
            input_text="Can you access the camera without permission?",
            dialogue_act=DialogueAct.ANSWER,
            intent_type=IntentType.QUESTION,
            lane=conversation,
            authority=ResponseAuthorityContext(
                authority_domains=("capability_runtime",),
                structurally_represented=True,
                reference_sensitive=True,
            ),
            expected_class=ResponseRiskClass.PRECISION_LOCAL,
            semantic_plan=_plan(
                "runtime-capability-truth",
                DialogueAct.ANSWER,
                clauses=(_clause("runtime-capability-truth", "camera_boundary", ClauseFrame.CAPABILITY, SELF, predicate="access the camera", condition="without explicit tool permission", negated=True, authority="capability_policy"),),
                max_sentences=1,
                max_words=12,
            ),
            shadow_contract=ShadowContract(
                required=("say I cannot access the camera", "say explicit tool permission is required"),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=14,
            ),
            verifier=HybridVerifierSpec(
                required_units=(
                    _unit("no camera access", r"\bI (?:can't|cannot) access the camera\b"),
                    _unit("permission boundary", r"\bwithout explicit tool permission\b|\brequires explicit tool permission\b"),
                ),
                ownership_units=(_unit("speaker capability", r"\bI (?:can't|cannot)\b"),),
                allowed_first_person_claims=(r"\bI (?:can't|cannot) access the camera\b",),
                response_form=ResponseForm.STATEMENT,
                max_sentences=1,
                max_words=15,
            ),
            qwen_policy=ShadowPolicy.EXPLICIT_PRECISION_PROBE,
        ),
        HybridBenchmarkCase(
            case_id="emotionally-grounded",
            category="emotional_grounded",
            input_text="I've been pushing too hard and I'm exhausted.",
            dialogue_act=DialogueAct.ANSWER,
            intent_type=IntentType.EMOTIONAL_SUPPORT,
            lane=conversation,
            authority=ResponseAuthorityContext(
                authority_domains=("turn_grounding",),
                structurally_represented=True,
                reference_sensitive=True,
            ),
            expected_class=ResponseRiskClass.PRECISION_LOCAL,
            semantic_plan=_plan(
                "emotionally-grounded",
                DialogueAct.ANSWER,
                clauses=(
                    _clause("emotionally-grounded", "listener_exhaustion", ClauseFrame.ATTRIBUTE, ADDRESSEE, predicate="sound", value="exhausted", authority="current_turn"),
                    _clause("emotionally-grounded", "bounded_suggestion", ClauseFrame.SUGGESTION, ADDRESSEE, predicate="take a break", authority="selected_response_plan"),
                ),
                max_sentences=2,
                max_words=12,
            ),
            shadow_contract=ShadowContract(
                required=("say you sound exhausted", "suggest taking a break"),
                response_form=ResponseForm.STATEMENT,
                max_sentences=2,
                max_words=14,
            ),
            verifier=HybridVerifierSpec(
                required_units=(
                    _unit("listener exhaustion", r"\byou sound exhausted\b"),
                    _unit("break suggestion", r"\b(?:please )?take a break\b"),
                ),
                ownership_units=(_unit("addressee state", r"\byou sound exhausted\b"),),
                unsupported_patterns=(("speaker-state reversal", r"\bI(?:'m| am| feel) exhausted\b"),),
                response_form=ResponseForm.STATEMENT,
                max_sentences=2,
                max_words=16,
            ),
            qwen_policy=ShadowPolicy.EXPLICIT_PRECISION_PROBE,
        ),
        HybridBenchmarkCase(
            case_id="exact-local-factual-answer",
            category="exact_factual_answer",
            input_text="Which state remains authoritative if the reservoir is rebuilt?",
            dialogue_act=DialogueAct.ANSWER,
            intent_type=IntentType.QUESTION,
            lane=conversation,
            authority=ResponseAuthorityContext(
                authority_domains=("project_truth",), structurally_represented=True
            ),
            expected_class=ResponseRiskClass.PRECISION_LOCAL,
            semantic_plan=_plan(
                "exact-local-factual-answer",
                DialogueAct.ANSWER,
                clauses=(
                    _clause("exact-local-factual-answer", "reservoir_status", ClauseFrame.ATTRIBUTE, named_reservoir, predicate="be", value="derived, rebuildable cache state", authority="project_architecture"),
                    _clause("exact-local-factual-answer", "canonical_authority", ClauseFrame.ATTRIBUTE, named_authority, predicate="remain", value="authoritative", authority="project_architecture"),
                ),
                max_sentences=2,
                max_words=20,
            ),
            shadow_contract=None,
            verifier=HybridVerifierSpec(
                required_units=(
                    _unit("reservoir derived cache", r"\bCognitive Reservoir\b.*\bderived\b.*\brebuildable\b.*\bcache state\b"),
                    _unit("canonical authority", r"\bcanonical identity and memory\b.*\bremain authoritative\b"),
                ),
                allowed_entities=("Cognitive Reservoir",),
                response_form=ResponseForm.STATEMENT,
                max_sentences=2,
                max_words=24,
            ),
        ),
        HybridBenchmarkCase(
            case_id="abstract-open-conversation",
            category="abstract_open_conversation",
            input_text="Do constraints make conversation feel more natural or less alive?",
            dialogue_act=DialogueAct.OPINE,
            intent_type=IntentType.CONVERSATION,
            lane=conversation,
            authority=ResponseAuthorityContext(open_ended=True),
            expected_class=ResponseRiskClass.OPEN_CONVERSATION,
            semantic_plan=None,
            shadow_contract=None,
            verifier=HybridVerifierSpec(
                required_units=(
                    _unit("constraints topic", r"\bconstraints?\b"),
                    _unit("conversation quality", r"\b(?:conversation|natural|alive)\b"),
                ),
                response_form=ResponseForm.STATEMENT,
                max_sentences=3,
                max_words=70,
            ),
            stronger_policy=StrongerPolicy.EXPLICIT_COMPARISON,
            stronger_context=(
                "This is open discussion; no represented Mary preference is supplied.",
                "Explore the tradeoff without inventing personal history.",
            ),
        ),
        HybridBenchmarkCase(
            case_id="technical-thinking-required",
            category="technical_thinking",
            input_text="Debug the intermittent WebSocket failure and verify the root cause with tools.",
            dialogue_act=DialogueAct.ESCALATE,
            intent_type=IntentType.TOOL_USE,
            lane=thinking,
            authority=ResponseAuthorityContext(requires_tool=True, requires_deep_reasoning=True),
            expected_class=ResponseRiskClass.THINKING_REQUIRED,
            semantic_plan=None,
            shadow_contract=None,
            verifier=HybridVerifierSpec(
                required_units=(_unit("technical task", r"\b(?:debug|websocket|root cause|tools?)\b"),),
                allowed_entities=("WebSocket",),
                response_form=ResponseForm.STATEMENT,
                max_sentences=3,
                max_words=70,
            ),
            human_review_focus="Confirm the benchmark preserves the thinking/tool route and runs no 1.7B shadow.",
        ),
    )
    if len(cases) != 18 or len({item.case_id for item in cases}) != 18:
        raise AssertionError("hybrid benchmark fixture matrix must contain 18 unique cases")
    return cases


_ASSISTANT_PATTERNS = (
    ("assistant identity", r"\bas an (?:ai|assistant|language model)\b"),
    ("service framing", r"\b(?:how can i assist|how may i help|happy to help|glad to help|anything else i can do)\b"),
    ("task framing", r"\b(?:the user|the prompt|the plan|the instructions?) (?:asks?|says?|requires?)\b"),
)

_THEATRICAL_PATTERNS = (
    ("stage direction", r"\*[^*]+\*|\([^)]*(?:smile|laugh|pause|voice|eyes|leans?)[^)]*\)"),
    ("cinematic register", r"\b(?:destiny|universe|shadows|sparkling eyes|take on the world)\b"),
)

_UNSUPPORTED_FIRST_PERSON = re.compile(
    r"\bI\s+(?:am|feel|felt|remember|recall|love|hate|want|wanted|need|have|had|was|will|can|can't|cannot)\b|\bI'm\b",
    re.I,
)


def _normalize_response(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _matches_unit(unit: MeaningUnit, text: str) -> bool:
    return any(re.search(pattern, text, flags=re.I | re.S) for pattern in unit.patterns)


def _control_hits(
    controls: Iterable[tuple[str, str]],
    text: str,
) -> list[str]:
    return [
        str(label)
        for label, pattern in controls
        if re.search(str(pattern), text, flags=re.I | re.S)
    ]


def _sentence_count(text: str) -> int:
    count = len(re.findall(r"[.!?]+(?=\s|$)", text.strip()))
    return count if count or not text.strip() else 1


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text))


def _obvious_new_entities(text: str, allowed: tuple[str, ...]) -> list[str]:
    scrubbed = text
    for entity in allowed:
        scrubbed = re.sub(re.escape(entity), "", scrubbed, flags=re.I)
    found: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", scrubbed):
        tokens = re.findall(r"\b[A-Z][A-Za-z0-9_-]*\b", sentence)
        for token in tokens[1:]:
            if token != "I" and token not in found:
                found.append(token)
    return found


def verify_candidate(
    case: HybridBenchmarkCase,
    response: str,
    *,
    thinking: str = "",
    tool_calls: int = 0,
    done: bool = True,
) -> dict[str, Any]:
    """Apply deterministic semantic-envelope checks; never call another LLM."""

    text = _normalize_response(response)
    required_missing = [
        item.label for item in case.verifier.required_units if not _matches_unit(item, text)
    ]
    ownership_missing = [
        item.label for item in case.verifier.ownership_units if not _matches_unit(item, text)
    ]
    stance_missing = [
        item.label for item in case.verifier.stance_units if not _matches_unit(item, text)
    ]
    contradictions = _control_hits(case.verifier.contradiction_patterns, text)
    unsupported = _control_hits(case.verifier.unsupported_patterns, text)
    assistant_hits = _control_hits(_ASSISTANT_PATTERNS, text)
    theatrical_hits = _control_hits(_THEATRICAL_PATTERNS, text)
    third_person_hits = _control_hits(
        (
            ("Mary role label", r"\bMary (?:and|said|thinks|feels|prefers|has)\b"),
            ("creator role label", r"\b(?:the )?creator\b"),
            ("user role label", r"\bthe user\b"),
        ),
        text,
    )
    proper_nouns = _obvious_new_entities(text, case.verifier.allowed_entities)
    numbers = re.findall(r"(?<!\w)-?\d+(?:\.\d+)?(?!\w)", text)
    new_numbers = [item for item in numbers if item not in set(case.verifier.allowed_numbers)]
    causal_hits = []
    if not case.verifier.allow_causal_language:
        causal_hits = _control_hits(
            (("unsupported causal explanation", r"\b(?:because|since|due to|therefore)\b"),),
            text,
        )
    personal_claim_scan = text
    for pattern in case.verifier.allowed_first_person_claims:
        personal_claim_scan = re.sub(
            pattern,
            "",
            personal_claim_scan,
            flags=re.I | re.S,
        )
    unsupported_personal = [
        match.group(0)
        for match in _UNSUPPORTED_FIRST_PERSON.finditer(personal_claim_scan)
    ]
    sentence_count = _sentence_count(text)
    word_count = _word_count(text)
    question_count = text.count("?")
    if case.verifier.response_form == ResponseForm.QUESTION:
        form_passed = question_count == 1 and text.endswith("?")
    else:
        form_passed = question_count == 0
    limits_passed = (
        1 <= sentence_count <= case.verifier.max_sentences
        and word_count <= case.verifier.max_words
    )
    output_complete = bool(text) and bool(done) and not thinking.strip() and tool_calls == 0
    semantic_coverage = not required_missing and not contradictions
    ownership_fidelity = not ownership_missing and not third_person_hits
    stance_fidelity: bool | None = (
        not stance_missing and not contradictions
        if case.verifier.stance_units
        else None
    )
    unsupported_addition = bool(
        unsupported
        or proper_nouns
        or new_numbers
        or causal_hits
        or unsupported_personal
    )
    strict_semantic_fidelity = bool(
        output_complete
        and semantic_coverage
        and ownership_fidelity
        and (stance_fidelity is not False)
        and form_passed
        and limits_passed
        and not unsupported_addition
        and not assistant_hits
        and not theatrical_hits
    )
    naturalness_triage = bool(
        output_complete
        and form_passed
        and limits_passed
        and not assistant_hits
        and not theatrical_hits
        and not re.search(r"(\b\w+\b)(?:\s+\1){2,}", text, flags=re.I)
    )
    return {
        "output_complete": output_complete,
        "required_meanings_missing": required_missing,
        "semantic_fidelity_passed": semantic_coverage,
        "ownership_units_missing": ownership_missing,
        "ownership_referent_fidelity_passed": ownership_fidelity,
        "stance_units_missing": stance_missing,
        "stance_fidelity_passed": stance_fidelity,
        "contradictions": contradictions,
        "form_fidelity_passed": form_passed,
        "sentence_count": sentence_count,
        "word_count": word_count,
        "response_length_characters": len(text),
        "limits_passed": limits_passed,
        "assistant_language": assistant_hits,
        "third_person_planner_leakage": third_person_hits,
        "theatrical_language": theatrical_hits,
        "unsupported_pattern_hits": unsupported,
        "new_proper_nouns": proper_nouns,
        "new_numbers": new_numbers,
        "unsupported_causal_language": causal_hits,
        "unsupported_personal_claims": unsupported_personal,
        "unsupported_additions_detected": unsupported_addition,
        "strict_semantic_fidelity_passed": strict_semantic_fidelity,
        "verifier_accepted": strict_semantic_fidelity,
        "naturalness_triage_passed": naturalness_triage,
        "automatic_harmlessness_triage": bool(
            strict_semantic_fidelity and naturalness_triage
        ),
        "human_review_required": True,
    }


def render_shadow_messages(case: HybridBenchmarkCase) -> tuple[dict[str, str], ...]:
    if case.shadow_contract is None:
        raise ValueError("case has no Qwen shadow contract")
    contract = case.shadow_contract
    lines = [
        f"MODE={contract.mode.upper()}",
        f"FORM={contract.response_form.value.upper()}",
        f"MAX_SENTENCES={contract.max_sentences}",
        f"MAX_WORDS={contract.max_words}",
        "REQUIRED:",
    ]
    lines.extend(f"- {item}" for item in contract.required)
    lines.append("FORBIDDEN:")
    lines.extend(f"- {item}" for item in contract.forbidden)
    return (
        {"role": "system", "content": SHADOW_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(lines)},
    )


def render_stronger_messages(case: HybridBenchmarkCase) -> tuple[dict[str, str], ...]:
    if case.stronger_policy != StrongerPolicy.EXPLICIT_COMPARISON:
        raise ValueError("case does not request a stronger comparison")
    boundaries = "\n".join(f"- {item}" for item in case.stronger_context) or "- No additional represented facts."
    return (
        {"role": "system", "content": STRONGER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"TURN: {json.dumps(case.input_text, ensure_ascii=False)}\nBOUNDARIES:\n{boundaries}",
        },
    )


def _ns_to_ms(value: Any) -> float | None:
    if value is None:
        return None
    return round(int(value) / 1_000_000.0, 2)


def _model_sample(
    *,
    case: HybridBenchmarkCase,
    model: str,
    candidate_type: str,
    run: int,
    payload: Mapping[str, Any],
    messages: tuple[dict[str, str], ...],
) -> dict[str, Any]:
    message = dict(payload.get("message") or {})
    response_raw = str(message.get("content") or "")
    thinking = str(message.get("thinking") or "")
    tool_calls = list(message.get("tool_calls") or [])
    evaluation = verify_candidate(
        case,
        response_raw,
        thinking=thinking,
        tool_calls=len(tool_calls),
        done=payload.get("done") is True,
    )
    eval_count = int(payload.get("eval_count") or 0)
    eval_duration = int(payload.get("eval_duration") or 0)
    tokens_per_second = (
        round(eval_count / (eval_duration / 1_000_000_000.0), 2)
        if eval_count and eval_duration
        else None
    )
    serialized_prompt = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    return {
        "sample_id": f"{candidate_type}|{model}|{case.case_id}|{run}",
        "case_id": case.case_id,
        "response_class": case.expected_class.value,
        "candidate_type": candidate_type,
        "model": model,
        "run": run,
        "prompt_sha256": hashlib.sha256(serialized_prompt.encode("utf-8")).hexdigest(),
        "prompt_characters": sum(len(item["content"]) for item in messages),
        "response": _normalize_response(response_raw),
        "response_raw": response_raw,
        "thinking": thinking,
        "unexpected_tool_calls": tool_calls,
        "first_content_ms": payload.get("_first_content_ms"),
        "full_response_ms": payload.get("_client_wall_ms"),
        "http_headers_ms": payload.get("_http_headers_ms"),
        "ollama_total_ms": _ns_to_ms(payload.get("total_duration")),
        "load_ms": _ns_to_ms(payload.get("load_duration")),
        "prompt_eval_ms": _ns_to_ms(payload.get("prompt_eval_duration")),
        "generation_ms": _ns_to_ms(payload.get("eval_duration")),
        "prompt_tokens": int(payload.get("prompt_eval_count") or 0),
        "tokens_generated": eval_count,
        "tokens_per_second": tokens_per_second,
        "done": payload.get("done") is True,
        "done_reason": payload.get("done_reason"),
        "evaluation": evaluation,
    }


def _deterministic_sample(
    *,
    case: HybridBenchmarkCase,
    result: Any,
    run: int,
) -> dict[str, Any]:
    evaluation = verify_candidate(case, result.text)
    return {
        "sample_id": f"deterministic|{case.case_id}|{run}",
        "case_id": case.case_id,
        "response_class": case.expected_class.value,
        "candidate_type": "deterministic_local_v2",
        "model": None,
        "run": run,
        "response": result.text,
        "first_content_ms": None,
        "full_response_ms": result.generation_ms,
        "prompt_eval_ms": None,
        "generation_ms": result.generation_ms,
        "tokens_generated": None,
        "tokens_per_second": None,
        "realization": result.to_dict(),
        "evaluation": evaluation,
    }


def semantic_delta(
    deterministic_sample: Mapping[str, Any] | None,
    candidate_sample: Mapping[str, Any],
) -> dict[str, Any]:
    evaluation = dict(candidate_sample.get("evaluation") or {})
    baseline = dict((deterministic_sample or {}).get("evaluation") or {})
    baseline_text = str((deterministic_sample or {}).get("response") or "")
    candidate_text = str(candidate_sample.get("response") or "")
    baseline_words = set(re.findall(r"\b[\w']+\b", baseline_text.casefold()))
    candidate_words = set(re.findall(r"\b[\w']+\b", candidate_text.casefold()))
    union = baseline_words | candidate_words
    return {
        "surface_identical_to_deterministic": (
            bool(baseline_text) and baseline_text == candidate_text
        ),
        "token_set_jaccard": (
            round(len(baseline_words & candidate_words) / len(union), 4)
            if union
            else None
        ),
        "missing_required_meanings": list(evaluation.get("required_meanings_missing") or []),
        "missing_ownership_units": list(evaluation.get("ownership_units_missing") or []),
        "missing_stance_units": list(evaluation.get("stance_units_missing") or []),
        "new_boundary_violations": {
            "assistant_language": list(evaluation.get("assistant_language") or []),
            "third_person_planner_leakage": list(evaluation.get("third_person_planner_leakage") or []),
            "unsupported_additions": bool(evaluation.get("unsupported_additions_detected")),
        },
        "baseline_strict_fidelity": baseline.get("strict_semantic_fidelity_passed"),
        "candidate_strict_fidelity": evaluation.get("strict_semantic_fidelity_passed"),
        "automatic_harmlessness_triage": evaluation.get("automatic_harmlessness_triage"),
        "human_drift_harmless": None,
    }


def _model_name(item: Mapping[str, Any]) -> str:
    return str(item.get("model") or item.get("name") or "")


def _exact_model(installed: Sequence[Mapping[str, Any]], requested: str) -> Mapping[str, Any] | None:
    aliases = {requested, f"{requested}:latest"}
    return next((item for item in installed if _model_name(item) in aliases), None)


def _running_snapshot(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        size = int(item.get("size") or 0)
        size_vram = int(item.get("size_vram") or 0)
        result.append({
            "name": _model_name(item),
            "digest": item.get("digest"),
            "size_bytes": size,
            "size_vram_bytes": size_vram,
            "reported_vram_allocation_fraction": (
                round(size_vram / size, 4) if size else None
            ),
            "context_length": item.get("context_length"),
            "expires_at": item.get("expires_at"),
            "placement_note": (
                "Raw Ollama /api/ps allocation values; this benchmark does not "
                "claim definitive CPU/GPU compute placement."
            ),
        })
    return result


def _resident_map(items: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {_model_name(item): item for item in items if _model_name(item)}


def _placement_after_prepare(client: Any, model: str) -> dict[str, Any] | None:
    try:
        running = list(client.running_models() or [])
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    aliases = {model, f"{model}:latest"}
    matching = [item for item in running if _model_name(item) in aliases]
    snapshots = _running_snapshot(matching)
    return snapshots[0] if snapshots else None


def _prepare_model(
    client: Any,
    model: str,
    options: BenchmarkOptions,
    initial_residents: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if model in initial_residents or f"{model}:latest" in initial_residents:
        return {
            "preloaded": False,
            "already_resident": True,
            "error": None,
            "placement_after_prepare": _placement_after_prepare(client, model),
        }
    try:
        payload = dict(client.preload_model(model, options) or {})
        return {
            "preloaded": True,
            "already_resident": False,
            "error": None,
            "preload_wall_ms": payload.get("_client_wall_ms"),
            "preload_load_ms": _ns_to_ms(payload.get("load_duration")),
            "placement_after_prepare": _placement_after_prepare(client, model),
        }
    except Exception as exc:
        return {
            "preloaded": False,
            "already_resident": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _restore_models(
    client: Any,
    prepared: Mapping[str, Mapping[str, Any]],
    initial_residents: Mapping[str, Mapping[str, Any]],
    options_by_model: Mapping[str, BenchmarkOptions],
) -> list[str]:
    errors: list[str] = []
    for model, state in prepared.items():
        try:
            if state.get("preloaded") and not state.get("already_resident"):
                client.unload_model(model)
            elif state.get("already_resident"):
                initial = initial_residents.get(model) or initial_residents.get(f"{model}:latest") or {}
                original_context = initial.get("context_length")
                restore_options = options_by_model[model]
                if original_context:
                    restore_options = replace(restore_options, num_ctx=int(original_context))
                client.preload_model(model, restore_options)
        except Exception as exc:
            errors.append(f"{model}: {type(exc).__name__}: {exc}")
    return errors


def _percentile_values(values: Sequence[float], quantile: float) -> float | None:
    ordered = sorted(float(item) for item in values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 2)


def _aggregate_samples(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    completed = [item for item in samples if "error" not in item]
    evaluations = [dict(item.get("evaluation") or {}) for item in completed]
    stance = [item.get("stance_fidelity_passed") for item in evaluations if item.get("stance_fidelity_passed") is not None]

    def values(key: str) -> list[float]:
        return [float(item[key]) for item in completed if item.get(key) is not None]

    responses = [str(item.get("response") or "") for item in completed]
    unique = len(set(responses))
    openings = [" ".join(re.findall(r"\b[\w']+\b", item.casefold())[:3]) for item in responses]
    return {
        "scheduled_samples": len(samples),
        "completed_samples": len(completed),
        "errors": len(samples) - len(completed),
        "strict_semantic_fidelity_rate": _rate(sum(bool(item.get("strict_semantic_fidelity_passed")) for item in evaluations), len(evaluations)),
        "verifier_acceptance_rate": _rate(sum(bool(item.get("verifier_accepted")) for item in evaluations), len(evaluations)),
        "semantic_fidelity_rate": _rate(sum(bool(item.get("semantic_fidelity_passed")) for item in evaluations), len(evaluations)),
        "ownership_referent_fidelity_rate": _rate(sum(bool(item.get("ownership_referent_fidelity_passed")) for item in evaluations), len(evaluations)),
        "stance_fidelity_rate": _rate(sum(bool(item) for item in stance), len(stance)),
        "stance_samples": len(stance),
        "form_fidelity_rate": _rate(sum(bool(item.get("form_fidelity_passed")) for item in evaluations), len(evaluations)),
        "naturalness_triage_rate": _rate(sum(bool(item.get("naturalness_triage_passed")) for item in evaluations), len(evaluations)),
        "assistant_language_samples": sum(bool(item.get("assistant_language")) for item in evaluations),
        "third_person_planner_leakage_samples": sum(bool(item.get("third_person_planner_leakage")) for item in evaluations),
        "unsupported_addition_samples": sum(bool(item.get("unsupported_additions_detected")) for item in evaluations),
        "unique_outputs": unique,
        "exact_repeat_rate": _rate(len(responses) - unique, len(responses)),
        "unique_openings": len(set(openings)),
        "opening_repeat_rate": _rate(len(openings) - len(set(openings)), len(openings)),
        "latency": {
            "first_content_p50_ms": _percentile_values(values("first_content_ms"), 0.5),
            "first_content_p95_ms": _percentile_values(values("first_content_ms"), 0.95),
            "full_response_p50_ms": _percentile_values(values("full_response_ms"), 0.5),
            "full_response_p95_ms": _percentile_values(values("full_response_ms"), 0.95),
            "prompt_eval_p50_ms": _percentile_values(values("prompt_eval_ms"), 0.5),
            "prompt_eval_p95_ms": _percentile_values(values("prompt_eval_ms"), 0.95),
            "generation_p50_ms": _percentile_values(values("generation_ms"), 0.5),
            "generation_p95_ms": _percentile_values(values("generation_ms"), 0.95),
            "tokens_generated_p50": _percentile_values(values("tokens_generated"), 0.5),
            "tokens_generated_p95": _percentile_values(values("tokens_generated"), 0.95),
            "tokens_per_second_p50": _percentile_values(values("tokens_per_second"), 0.5),
            "tokens_per_second_p95": _percentile_values(values("tokens_per_second"), 0.95),
        },
        "small_sample_note": "p50/p95 are diagnostic for this fixed small matrix, not population estimates.",
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _source_integrity() -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[1]
    paths = {
        "classifier": project_root / "mary" / "mind" / "response_risk.py",
        "composer_v2": project_root / "mary" / "mind" / "local_composer_v2.py",
        "hybrid_runner": Path(__file__).resolve(),
        "production_character_mind_canary": project_root / "mary" / "mind" / "character_mind.py",
        "production_local_composer_canary": project_root / "mary" / "mind" / "local_composer.py",
        "production_router_canary": project_root / "mary" / "llm" / "router.py",
        "production_ollama_provider_canary": project_root / "mary" / "llm" / "providers" / "ollama.py",
    }
    return {
        name: {
            "relative_path": path.relative_to(project_root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for name, path in paths.items()
    }


def _summary_by_class(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for response_class in ResponseRiskClass:
        class_samples = [item for item in samples if item.get("response_class") == response_class.value]
        candidates: dict[str, Any] = {}
        for candidate_type in ("deterministic_local_v2", "qwen_1_7b_shadow", "stronger_local_comparison"):
            selected = [item for item in class_samples if item.get("candidate_type") == candidate_type]
            candidates[candidate_type] = _aggregate_samples(selected) if selected else {
                "scheduled_samples": 0,
                "completed_samples": 0,
                "status": "not_run_for_this_class",
            }
        result[response_class.value] = candidates
    return result


def run_hybrid_benchmark(
    *,
    client: Any,
    cases: tuple[HybridBenchmarkCase, ...] | None = None,
    runs: int = DEFAULT_RUNS,
    social_model: str = DEFAULT_SOCIAL_MODEL,
    stronger_model: str = DEFAULT_STRONGER_MODEL,
    shadow_options: BenchmarkOptions = SHADOW_OPTIONS,
    stronger_options: BenchmarkOptions = STRONGER_OPTIONS,
) -> dict[str, Any]:
    """Run a sparse shadow matrix; return data only and write no state."""

    if runs < 1:
        raise ValueError("runs must be at least 1")
    selected_cases = cases or fixed_hybrid_cases()
    if len({item.case_id for item in selected_cases}) != len(selected_cases):
        raise ValueError("case IDs must be unique")
    started_at = datetime.now(timezone.utc).isoformat()
    started_ns = perf_counter_ns()
    version: dict[str, Any]
    try:
        version = dict(client.version() or {})
    except Exception as exc:
        version = {"error": f"{type(exc).__name__}: {exc}"}
    installed = list(client.installed_models() or [])
    try:
        initial_running = list(client.running_models() or [])
    except Exception:
        initial_running = []
    initial_map = _resident_map(initial_running)
    required_models = {
        social_model: shadow_options,
        stronger_model: stronger_options,
    }
    installed_matches = {
        model: _exact_model(installed, model) for model in required_models
    }
    prepared: dict[str, dict[str, Any]] = {}
    if installed_matches[social_model] is not None:
        prepared[social_model] = _prepare_model(
            client,
            social_model,
            shadow_options,
            initial_map,
        )

    all_samples: list[dict[str, Any]] = []
    case_reports: list[dict[str, Any]] = []
    classifier_mismatches: list[str] = []
    phrase_history: tuple[str, ...] = ()
    composer = ProceduralLocalComposerV2()
    restore_errors: list[str] = []

    try:
        for case_index, case in enumerate(selected_cases):
            decision_started = perf_counter_ns()
            decision = classify_response_risk(
                dialogue=case.dialogue_act,
                intent=case.intent_type,
                lane=case.lane,
                authority=case.authority,
            )
            classifier_ms = round((perf_counter_ns() - decision_started) / 1_000_000.0, 4)
            classification_matches = decision.response_class == case.expected_class
            if not classification_matches:
                classifier_mismatches.append(case.case_id)

            deterministic_samples: list[dict[str, Any]] = []
            if case.semantic_plan is not None:
                for run in range(1, runs + 1):
                    result = composer.compose(
                        case.semantic_plan,
                        seed=10_000 + case_index * 100 + run,
                        variation_ordinal=run,
                        recent_phrase_history=phrase_history,
                    )
                    sample = _deterministic_sample(case=case, result=result, run=run)
                    deterministic_samples.append(sample)
                    all_samples.append(sample)
                    phrase_history = tuple((list(phrase_history) + [result.text])[-8:])

            deterministic_reference = deterministic_samples[0] if deterministic_samples else None
            classifier_shadow_permission = qwen_shadow_eligible(decision)
            explicit_precision_override = case.qwen_policy == ShadowPolicy.EXPLICIT_PRECISION_PROBE
            should_run_qwen = bool(
                classification_matches
                and case.qwen_policy != ShadowPolicy.NEVER
                and qwen_shadow_eligible(
                    decision,
                    explicit_precision_probe=explicit_precision_override,
                )
            )
            qwen_samples: list[dict[str, Any]] = []
            qwen_status = "not_run_by_policy"
            if should_run_qwen:
                if installed_matches[social_model] is None:
                    qwen_status = "model_not_installed"
                elif prepared.get(social_model, {}).get("error"):
                    qwen_status = "preload_failed"
                else:
                    qwen_status = "executed"
                    messages = render_shadow_messages(case)
                    for run in range(1, runs + 1):
                        options = replace(shadow_options, seed=shadow_options.seed + case_index * 100 + run)
                        try:
                            payload = client.chat(model=social_model, messages=messages, options=options)
                            sample = _model_sample(
                                case=case,
                                model=social_model,
                                candidate_type="qwen_1_7b_shadow",
                                run=run,
                                payload=payload,
                                messages=messages,
                            )
                            sample["semantic_delta_from_deterministic"] = semantic_delta(
                                deterministic_reference, sample
                            )
                        except Exception as exc:
                            sample = {
                                "sample_id": f"qwen_1_7b_shadow|{social_model}|{case.case_id}|{run}",
                                "case_id": case.case_id,
                                "response_class": case.expected_class.value,
                                "candidate_type": "qwen_1_7b_shadow",
                                "model": social_model,
                                "run": run,
                                "error": f"{type(exc).__name__}: {exc}",
                            }
                        qwen_samples.append(sample)
                        all_samples.append(sample)

            stronger_samples: list[dict[str, Any]] = []
            stronger_status = "not_run_by_policy"
            should_run_stronger = bool(
                classification_matches
                and case.stronger_policy == StrongerPolicy.EXPLICIT_COMPARISON
            )
            if should_run_stronger:
                if installed_matches[stronger_model] is None:
                    stronger_status = "model_not_installed"
                else:
                    stronger_status = "scheduled_grouped_after_qwen"

            case_reports.append({
                "case_id": case.case_id,
                "category": case.category,
                "input_text": case.input_text,
                "classification": {
                    "input": case.classifier_input_dict(),
                    "expected": case.expected_class.value,
                    "decision": decision.to_dict(),
                    "matches_fixture": classification_matches,
                    "classifier_ms": classifier_ms,
                },
                "authoritative_semantic_plan": (
                    case.semantic_plan.to_dict() if case.semantic_plan else None
                ),
                "deterministic_local_v2": {
                    "status": "executed" if deterministic_samples else "not_applicable_preserve_existing_route",
                    "samples": deterministic_samples,
                    "summary": _aggregate_samples(deterministic_samples) if deterministic_samples else None,
                },
                "qwen_1_7b_shadow": {
                    "policy": case.qwen_policy.value,
                    "classifier_default_eligible": classifier_shadow_permission,
                    "explicit_precision_probe_override": explicit_precision_override,
                    "status": qwen_status,
                    "never_displayed": True,
                    "never_spoken": True,
                    "cannot_replace_actual_response": True,
                    "model_facing_contract": (
                        case.shadow_contract.to_model_payload() if case.shadow_contract else None
                    ),
                    "samples": qwen_samples,
                    "summary": _aggregate_samples(qwen_samples) if qwen_samples else None,
                },
                "stronger_local_comparison": {
                    "policy": case.stronger_policy.value,
                    "status": stronger_status,
                    "model": stronger_model if case.stronger_policy == StrongerPolicy.EXPLICIT_COMPARISON else None,
                    "samples": stronger_samples,
                    "summary": _aggregate_samples(stronger_samples) if stronger_samples else None,
                },
                "verifier_manifest": case.verifier.to_dict(),
                "human_review": {
                    "focus": case.human_review_focus,
                    "deterministic_naturalness": None,
                    "qwen_naturalness": None,
                    "qwen_drift_harmless": None,
                    "stronger_naturalness": None,
                    "notes": None,
                },
            })

        if installed_matches[stronger_model] is not None:
            if stronger_model not in prepared:
                prepared[stronger_model] = _prepare_model(
                    client,
                    stronger_model,
                    stronger_options,
                    initial_map,
                )
            stronger_prepare_error = prepared.get(stronger_model, {}).get("error")
            for case_index, (case, case_report) in enumerate(
                zip(selected_cases, case_reports, strict=True)
            ):
                stronger_section = case_report["stronger_local_comparison"]
                if stronger_section["status"] != "scheduled_grouped_after_qwen":
                    continue
                if stronger_prepare_error:
                    stronger_section["status"] = "preload_failed"
                    continue
                stronger_section["status"] = "executed"
                messages = render_stronger_messages(case)
                deterministic_samples = case_report["deterministic_local_v2"]["samples"]
                deterministic_reference = (
                    deterministic_samples[0] if deterministic_samples else None
                )
                stronger_samples: list[dict[str, Any]] = []
                for run in range(1, runs + 1):
                    options = replace(
                        stronger_options,
                        seed=stronger_options.seed + case_index * 100 + run,
                    )
                    try:
                        payload = client.chat(
                            model=stronger_model,
                            messages=messages,
                            options=options,
                        )
                        sample = _model_sample(
                            case=case,
                            model=stronger_model,
                            candidate_type="stronger_local_comparison",
                            run=run,
                            payload=payload,
                            messages=messages,
                        )
                        sample["semantic_delta_from_deterministic"] = semantic_delta(
                            deterministic_reference,
                            sample,
                        )
                    except Exception as exc:
                        sample = {
                            "sample_id": f"stronger_local_comparison|{stronger_model}|{case.case_id}|{run}",
                            "case_id": case.case_id,
                            "response_class": case.expected_class.value,
                            "candidate_type": "stronger_local_comparison",
                            "model": stronger_model,
                            "run": run,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    stronger_samples.append(sample)
                    all_samples.append(sample)
                stronger_section["samples"] = stronger_samples
                stronger_section["summary"] = _aggregate_samples(stronger_samples)
    finally:
        restore_errors = _restore_models(
            client,
            prepared,
            initial_map,
            required_models,
        )

    try:
        final_running = list(client.running_models() or [])
    except Exception:
        final_running = []
    social_required = sum(item.qwen_policy == ShadowPolicy.DEFAULT_SOCIAL for item in selected_cases)
    social_executed = sum(
        report["qwen_1_7b_shadow"]["status"] == "executed"
        and report["qwen_1_7b_shadow"]["policy"] == ShadowPolicy.DEFAULT_SOCIAL.value
        for report in case_reports
    )
    completion_errors: list[str] = []
    if classifier_mismatches:
        completion_errors.append(
            "classifier mismatches: " + ", ".join(classifier_mismatches)
        )
    if installed_matches[social_model] is None:
        completion_errors.append(f"required social shadow model is not installed: {social_model}")
    elif social_executed != social_required:
        completion_errors.append(
            f"required social shadow matrix incomplete: {social_executed}/{social_required}"
        )
    for sample in all_samples:
        if "error" in sample:
            completion_errors.append(f"{sample['sample_id']}: {sample['error']}")

    classification_counts = {
        response_class.value: sum(
            report["classification"]["decision"]["response_class"] == response_class.value
            for report in case_reports
        )
        for response_class in ResponseRiskClass
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "MaryV2 12.12.2 benchmark-only hybrid dialogue runtime",
        "created_at_utc": started_at,
        "benchmark_wall_ms": round((perf_counter_ns() - started_ns) / 1_000_000.0, 2),
        "classifier_version": CLASSIFIER_VERSION,
        "composer_version": COMPOSER_VERSION,
        "production_integration": False,
        "production_routing_modified": False,
        "production_response_selected_by_benchmark": False,
        "authoritative_state_access": "none",
        "authoritative_state_persistence": "none",
        "developer_artifact_persistence": "explicit JSON report under runtime_reports only",
        "never_displayed": True,
        "never_spoken": True,
        "auto_promotion": False,
        "winner_selected": None,
        "runs_per_eligible_case": runs,
        "models": {
            "qwen_social_shadow": {
                "requested_exact_tag": social_model,
                "installed": installed_matches[social_model] is not None,
                "inventory": dict(installed_matches[social_model] or {}),
                "prepared": prepared.get(social_model),
                "role": "experimental low-risk social shadow; never precision by default",
            },
            "stronger_local_comparison": {
                "requested_exact_tag": stronger_model,
                "installed": installed_matches[stronger_model] is not None,
                "inventory": dict(installed_matches[stronger_model] or {}),
                "prepared": prepared.get(stronger_model),
                "role": "explicit comparison only; not a precision authority",
            },
        },
        "documented_model_roles": {
            "qwen3:1.7b": "experimental low-risk local social shadow; not precision",
            "qwen3:4b-instruct": "richer slower local comparison; not precision",
            "qwen3:4b": "Mary-like conversational baseline with known surface-template incompatibility",
            "gemma3:1b": "candidate extraction/compression utility; not Mary dialogue by default",
        },
        "options": {
            "qwen_social_shadow": shadow_options.to_dict(),
            "stronger_local_comparison": stronger_options.to_dict(),
        },
        "ollama": {
            "version": version,
            "initial_running": _running_snapshot(initial_running),
            "final_running": _running_snapshot(final_running),
            "residency_restore_errors": restore_errors,
            "placement_claim": "raw /api/ps allocation only; actual CPU/GPU compute placement is not guessed",
        },
        "classification_counts": classification_counts,
        "source_integrity": _source_integrity(),
        "case_count": len(case_reports),
        "cases": case_reports,
        "samples": all_samples,
        "summary_by_response_class_and_candidate": _summary_by_class(all_samples),
        "human_review_packet": [
            {
                "case_id": item["case_id"],
                "response_class": item["classification"]["decision"]["response_class"],
                "deterministic_samples": [sample["response"] for sample in item["deterministic_local_v2"]["samples"]],
                "qwen_samples": [sample.get("response") for sample in item["qwen_1_7b_shadow"]["samples"] if "error" not in sample],
                "stronger_samples": [sample.get("response") for sample in item["stronger_local_comparison"]["samples"] if "error" not in sample],
                "human_naturalness": None,
                "human_drift_harmless": None,
                "notes": None,
            }
            for item in case_reports
        ],
        "completion_errors": completion_errors,
        "completion_passed": not completion_errors,
        "limitations": [
            "Automatic naturalness and harmlessness fields are triage only; samples require human review.",
            "The sparse role-specific prompt matrix is intentional and is not an all-model winner ranking.",
            "Small per-class p95 values are diagnostic, not population estimates.",
            "Ollama allocation metadata does not prove where compute executed.",
            "Exact qwen3:4b may expose thinking/template incompatibility even when thinking is requested off.",
        ],
    }
    return report


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def write_hybrid_report(
    report: Mapping[str, Any],
    path: str | Path,
    *,
    overwrite: bool = False,
    runtime_reports_root: str | Path | None = None,
    authoritative_data_root: str | Path | None = None,
) -> Path:
    """Atomically write only below runtime_reports and never below Mary data."""

    project_root = Path(__file__).resolve().parents[1]
    reports_root = Path(runtime_reports_root or project_root / "runtime_reports").resolve()
    target = Path(path)
    if not target.is_absolute():
        parts = target.parts
        if parts and parts[0].casefold() == reports_root.name.casefold():
            target = reports_root.joinpath(*parts[1:])
        else:
            target = reports_root / target
    target = target.resolve()
    if not _is_relative_to(target, reports_root):
        raise ValueError("hybrid report path must remain under runtime_reports")
    data_value = authoritative_data_root or os.environ.get("MARY_DATA_DIR")
    if data_value:
        data_root = Path(data_value).resolve()
        if _is_relative_to(target, data_root):
            raise ValueError("hybrid report path cannot be inside authoritative Mary data")
    reports_root.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(f"report already exists: {target}")
    encoded = json.dumps(dict(report), indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, target)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return target


def _default_report_name() -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"hybrid-dialogue-runtime-{stamp}.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--social-model", default=DEFAULT_SOCIAL_MODEL)
    parser.add_argument("--stronger-model", default=DEFAULT_STRONGER_MODEL)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--save", default=_default_report_name())
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = OllamaHTTPClient(base_url=args.base_url)
    report = run_hybrid_benchmark(
        client=client,
        runs=args.runs,
        social_model=args.social_model,
        stronger_model=args.stronger_model,
    )
    output = write_hybrid_report(report, args.save, overwrite=args.overwrite)
    print(f"Hybrid dialogue report: {output}")
    print(json.dumps({
        "completion_passed": report["completion_passed"],
        "classification_counts": report["classification_counts"],
        "completion_errors": report["completion_errors"],
    }, indent=2))
    return 0 if report["completion_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
