"""Role-aware projection from local policy decisions to canonical V2 plans.

The projector reads only the already-selected ``DialoguePlan``, Mary's bounded
turn/hot projections, and structured reservoir-hit scalars.  It never parses a
reservoir ``content`` string, retrieves additional state, calls a model, or
persists anything.  Unsupported or incomplete semantics fail closed.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
import math
from numbers import Real
import re
from typing import Any

from mary.cognition.continuity import ConversationalDrive
from mary.conversation.lanes import ConversationLane, LaneDecision
from mary.expression.delivery_plan import DeliveryPlan

from .dialogue_acts import DialogueAct, DialoguePlan
from .local_authority_confirmation import (
    AuthorityConfirmationBundle,
    ConfirmedAuthorityScalar,
)
from .local_composer_v2 import (
    ADDRESSEE,
    JOINT,
    SELF,
    WORLD,
    Certainty,
    ClauseFrame,
    LocalRealizationPlan,
    ParticipantRef,
    ParticipantRole,
    QuestionKind,
    RealizationClause,
    ResponseForm,
    SemanticQuestion,
)
from .response_risk import ResponseAuthorityContext
from .verbalization_plan import (
    CanonicalResponsePlan,
    GroundedFact,
    RepresentedStance,
    VerbalizationFormTarget,
    bounded_response_scalar,
    canonical_grounded_fact_text,
    canonical_required_meanings,
    canonical_response_intent,
    project_verbalization_plan,
)


@dataclass(frozen=True, slots=True)
class LocalResponseProjection:
    """Fail-closed output of the production semantic projector."""

    authority_context: ResponseAuthorityContext
    canonical_plan: CanonicalResponsePlan | None = None
    escalation_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.authority_context, ResponseAuthorityContext):
            raise TypeError("authority_context must be a ResponseAuthorityContext")
        if self.canonical_plan is not None and not isinstance(
            self.canonical_plan,
            CanonicalResponsePlan,
        ):
            raise TypeError("canonical_plan must be a CanonicalResponsePlan or None")
        if (self.canonical_plan is None) == (self.escalation_reason is None):
            raise ValueError("projection must contain exactly one plan or escalation reason")
        if self.escalation_reason is not None:
            object.__setattr__(
                self,
                "escalation_reason",
                bounded_response_scalar(
                    "escalation_reason",
                    self.escalation_reason,
                    limit=160,
                ),
            )

    @property
    def complete(self) -> bool:
        return self.canonical_plan is not None


class _UnsupportedProjection(ValueError):
    def __init__(self, code: str) -> None:
        self.code = bounded_response_scalar("projection error code", code, limit=120)
        super().__init__(self.code)


_SOCIAL_ACTS = frozenset({
    DialogueAct.GREET,
    DialogueAct.ACKNOWLEDGE,
    DialogueAct.THANKS_RESPONSE,
    DialogueAct.GOODBYE,
    DialogueAct.LAUGH,
    DialogueAct.REACT,
    DialogueAct.FOLLOW_UP,
})


def project_response_authority(
    dialogue_plan: DialoguePlan,
    *,
    lane: LaneDecision | ConversationLane,
    input_text: str = "",
) -> ResponseAuthorityContext:
    """Project authority/risk flags without retrieving or interpreting prose."""

    if not isinstance(dialogue_plan, DialoguePlan):
        raise TypeError("dialogue_plan must be a DialoguePlan")
    conversation_lane = lane.lane if isinstance(lane, LaneDecision) else lane
    act = dialogue_plan.act
    slots = dialogue_plan.slots if isinstance(dialogue_plan.slots, Mapping) else {}

    if dialogue_plan.local is not True or act == DialogueAct.ESCALATE:
        literal_domain = _literal_precision_domain(input_text)
        domains = (literal_domain,) if literal_domain else ()
        return ResponseAuthorityContext(
            open_ended=conversation_lane not in {
                ConversationLane.THINKING,
                ConversationLane.EXPERT,
            },
            authority_domains=domains,
            reference_sensitive=literal_domain in {
                "shared_history_reference",
                "pronoun_sensitive_relation",
                "represented_stance_reference",
                "current_project_state",
                "provenance_boundary",
                "preference_ownership",
            },
            represented_uncertainty=literal_domain == "uncertainty_boundary",
        )
    if act == DialogueAct.STATUS:
        return ResponseAuthorityContext(
            authority_domains=("represented_status",),
            structurally_represented=True,
            represented_personal_state=True,
        )
    if act == DialogueAct.KNOWN_FACT:
        return ResponseAuthorityContext(
            authority_domains=("creator_fact",),
            structurally_represented=True,
            reference_sensitive=True,
        )
    if act == DialogueAct.KNOWN_PREFERENCE:
        return ResponseAuthorityContext(
            authority_domains=("mary_preference",),
            structurally_represented=True,
            represented_stance=True,
            reference_sensitive=True,
        )
    if act == DialogueAct.ANSWER:
        raw_hits = slots.get("hits")
        hits = (
            tuple(raw_hits)
            if isinstance(raw_hits, Sequence)
            and not isinstance(raw_hits, (str, bytes, bytearray, Mapping))
            else ()
        )
        domains = tuple(sorted({
            "semantic_memory"
            if isinstance(item, Mapping) and item.get("kind") == "semantic_memory"
            else "structured_local_answer"
            for item in hits
        })) or ("structured_local_answer",)
        reference_sensitive = any(
            str(dict(item.get("metadata") or {}).get("subject") or "").strip().lower()
            in {"mary", "creator", "unbe", "we", "joint", "shared_history"}
            for item in hits
            if isinstance(item, Mapping)
            and isinstance(item.get("metadata"), Mapping)
        )
        return ResponseAuthorityContext(
            authority_domains=domains,
            structurally_represented=True,
            reference_sensitive=reference_sensitive,
        )
    if act == DialogueAct.FOLLOW_UP:
        return ResponseAuthorityContext(fact_free_social_follow_up=True)
    return ResponseAuthorityContext()


def project_canonical_response_plan(
    *,
    dialogue_plan: DialoguePlan,
    input_text: str,
    lane: LaneDecision,
    mind_state: Mapping[str, Any] | None,
    hot_state: Mapping[str, Any] | None,
    owner_confirmations: AuthorityConfirmationBundle | None = None,
) -> LocalResponseProjection:
    """Build a complete immutable plan or return one bounded escalation code."""

    authority = project_response_authority(
        dialogue_plan,
        lane=lane,
        input_text=input_text,
    )
    if dialogue_plan.act == DialogueAct.STAY_QUIET:
        return LocalResponseProjection(
            authority,
            escalation_reason="stay_quiet_is_non_verbalizable",
        )
    if dialogue_plan.local is not True or dialogue_plan.act == DialogueAct.ESCALATE:
        return LocalResponseProjection(
            authority,
            escalation_reason="dialogue_policy_escalation",
        )
    if not isinstance(dialogue_plan.slots, Mapping):
        return LocalResponseProjection(
            authority,
            escalation_reason="dialogue_slots_are_not_structured",
        )

    mind = mind_state if isinstance(mind_state, Mapping) else {}
    hot = hot_state if isinstance(hot_state, Mapping) else {}
    confirmations = (
        owner_confirmations
        if isinstance(owner_confirmations, AuthorityConfirmationBundle)
        else AuthorityConfirmationBundle()
    )
    try:
        if dialogue_plan.act in _SOCIAL_ACTS:
            canonical = _project_social(
                dialogue_plan,
                input_text=input_text,
                authority=authority,
                mind_state=mind,
                hot_state=hot,
            )
        elif dialogue_plan.act == DialogueAct.STATUS:
            canonical = _project_status(
                dialogue_plan,
                input_text=input_text,
                authority=authority,
                mind_state=mind,
                hot_state=hot,
            )
        elif dialogue_plan.act == DialogueAct.KNOWN_FACT:
            canonical = _project_creator_fact(
                dialogue_plan,
                input_text=input_text,
                authority=authority,
                mind_state=mind,
                hot_state=hot,
                owner_confirmations=confirmations,
            )
        elif dialogue_plan.act == DialogueAct.KNOWN_PREFERENCE:
            canonical = _project_mary_preference(
                dialogue_plan,
                input_text=input_text,
                authority=authority,
                mind_state=mind,
                hot_state=hot,
                owner_confirmations=confirmations,
            )
        elif dialogue_plan.act == DialogueAct.ANSWER:
            canonical = _project_semantic_memory_answer(
                dialogue_plan,
                input_text=input_text,
                authority=authority,
                mind_state=mind,
                hot_state=hot,
                owner_confirmations=confirmations,
            )
        else:
            raise _UnsupportedProjection("unsupported_dialogue_act")
    except _UnsupportedProjection as exc:
        return LocalResponseProjection(authority, escalation_reason=exc.code)
    except (TypeError, ValueError, OverflowError):
        return LocalResponseProjection(
            authority,
            escalation_reason="canonical_plan_validation_failed",
        )
    return LocalResponseProjection(authority, canonical_plan=canonical)


def _project_social(
    dialogue_plan: DialoguePlan,
    *,
    input_text: str,
    authority: ResponseAuthorityContext,
    mind_state: Mapping[str, Any],
    hot_state: Mapping[str, Any],
) -> CanonicalResponsePlan:
    act = dialogue_plan.act
    continuity = _mapping(mind_state.get("continuity"))
    allow_question = bool(continuity.get("allow_follow_up_question", True))
    question: SemanticQuestion | None = None
    meanings: tuple[str, ...]
    response_intent: str
    max_sentences = 1
    max_words = 8

    if act == DialogueAct.GREET:
        response_intent = "Acknowledge the greeting briefly."
        meanings = ("Acknowledge the greeting.",)
        if allow_question:
            question = SemanticQuestion(QuestionKind.INVITATION, ADDRESSEE, "talk")
            meanings += ("Invite ordinary conversation to continue.",)
            max_sentences = 2
    elif act == DialogueAct.ACKNOWLEDGE:
        response_intent = "Acknowledge the creator briefly."
        meanings = ("Give one brief acknowledgement.",)
        max_words = 4
    elif act == DialogueAct.THANKS_RESPONSE:
        response_intent = "Respond to the creator's thanks briefly."
        meanings = ("Acknowledge the thanks.",)
        max_words = 5
    elif act == DialogueAct.GOODBYE:
        response_intent = "Acknowledge the goodbye briefly."
        meanings = ("Say goodbye without adding a new claim.",)
        max_words = 6
    elif act in {DialogueAct.LAUGH, DialogueAct.REACT}:
        reaction_kind = str(dialogue_plan.slots.get("reaction_kind") or "").strip().lower()
        if act == DialogueAct.REACT and reaction_kind == "milestone":
            response_intent = (
                "Give one familiar Mary-style reaction to the creator's stated milestone. "
                "Celebrate the beat without turning it into an interview or adding factual claims."
            )
            meanings = ("Acknowledge the creator's stated milestone and let the win land.",)
            max_sentences = 2
            max_words = 18
        else:
            response_intent = "Give one bounded conversational reaction."
            meanings = ("React briefly without adding factual meaning.",)
            max_words = 8
    elif act == DialogueAct.FOLLOW_UP:
        if not allow_question:
            raise _UnsupportedProjection("follow_up_question_budget_exhausted")
        response_intent = "Ask the preselected fact-free follow-up."
        meanings = ("Ask whether to keep going.",)
        question = SemanticQuestion(
            QuestionKind.INVITATION,
            ADDRESSEE,
            "keep going",
        )
        max_words = 8
    else:  # pragma: no cover - guarded by caller
        raise _UnsupportedProjection("unsupported_social_act")

    return _canonical(
        dialogue_plan,
        input_text=input_text,
        authority=authority,
        mind_state=mind_state,
        hot_state=hot_state,
        response_intent=response_intent,
        required_meanings=meanings,
        facts=(),
        clauses=(),
        question=question,
        max_sentences=max_sentences,
        max_words=max_words,
        disposition=(
            "amused" if act == DialogueAct.LAUGH
            else "milestone" if act == DialogueAct.REACT and str(dialogue_plan.slots.get("reaction_kind") or "").strip().lower() == "milestone"
            else "neutral"
        ),
    )


def _project_creator_fact(
    dialogue_plan: DialoguePlan,
    *,
    input_text: str,
    authority: ResponseAuthorityContext,
    mind_state: Mapping[str, Any],
    hot_state: Mapping[str, Any],
    owner_confirmations: AuthorityConfirmationBundle,
) -> CanonicalResponsePlan:
    hit = _mapping_or_error(dialogue_plan.slots.get("hit"), "creator_fact_hit_missing")
    metadata = _mapping_or_error(hit.get("metadata"), "creator_fact_metadata_missing")
    _require_hit_contract(
        hit,
        kind_prefix="creator_",
        allowed_authorities={"creator_explicit", "creator_structured"},
        minimum_confidence=0.85,
        error_code="creator_fact_provenance_unsupported",
    )
    if str(hit.get("subject") or "").strip().lower() != "creator":
        raise _UnsupportedProjection("creator_fact_subject_is_not_creator")
    confirmation = _confirmation_or_error(
        owner_confirmations,
        hit,
        owner="creator_user_model",
    )
    requested_field = _semantic_text(
        dialogue_plan.slots.get("field"),
        "requested creator fact field",
        limit=80,
    )
    field = _semantic_text(
        confirmation.predicate,
        "creator fact field",
        limit=80,
    ).replace("_", " ")
    value = _atomic_semantic_text(
        confirmation.value,
        "creator fact value",
        limit=180,
    )
    if not (
        _semantic_key(field)
        == _semantic_key(hit.get("predicate"))
        == _semantic_key(metadata.get("key"))
        == _semantic_key(requested_field)
    ):
        raise _UnsupportedProjection("creator_fact_predicate_mismatch")
    clause = RealizationClause(
        clause_id="creator-fact",
        frame=ClauseFrame.POSSESSIVE_FACT,
        subject=ADDRESSEE,
        property_name=field,
        value=value,
        authority=confirmation.authority,
        source_id=confirmation.selector_id,
    )
    fact = GroundedFact(
        fact_id=confirmation.selector_id,
        subject=confirmation.subject,
        predicate=confirmation.predicate,
        text=f"The creator's {field} is {value}.",
        kind=confirmation.kind,
        source=confirmation.source,
        authority=confirmation.authority,
        confidence=confirmation.confidence,
        semantic_clause=clause,
    )
    return _canonical(
        dialogue_plan,
        input_text=input_text,
        authority=authority,
        mind_state=mind_state,
        hot_state=hot_state,
        response_intent="State the represented creator fact with second-person ownership.",
        required_meanings=(f"Your {field} is {value}.",),
        facts=(fact,),
        clauses=(clause,),
        max_sentences=1,
        max_words=24,
    )


def _project_mary_preference(
    dialogue_plan: DialoguePlan,
    *,
    input_text: str,
    authority: ResponseAuthorityContext,
    mind_state: Mapping[str, Any],
    hot_state: Mapping[str, Any],
    owner_confirmations: AuthorityConfirmationBundle,
) -> CanonicalResponsePlan:
    raw_hit = dialogue_plan.slots.get("hit")
    hit = raw_hit if isinstance(raw_hit, Mapping) else None
    requested_topic = _semantic_text(
        dialogue_plan.slots.get("topic"),
        "requested Mary preference topic",
        limit=140,
    )
    if hit is not None:
        metadata = _mapping_or_error(hit.get("metadata"), "mary_preference_metadata_missing")
        _require_hit_contract(
            hit,
            exact_kind="mary_preference",
            allowed_authorities={"mary_canonical", "mary_developed"},
            minimum_confidence=0.7,
            error_code="mary_preference_provenance_unsupported",
        )
        if str(hit.get("subject") or "").strip().lower() != "mary":
            raise _UnsupportedProjection("mary_preference_subject_is_not_mary")
        confirmation = _confirmation_or_error(
            owner_confirmations,
            hit,
            owner="mary_preferences",
        )
    else:
        candidates = tuple(
            item for item in owner_confirmations.items
            if item.owner == "mary_preferences"
        )
        if len(candidates) != 1:
            raise _UnsupportedProjection("mary_preference_confirmation_missing")
        confirmation = candidates[0]
        metadata = {"name": confirmation.value}
    topic = _atomic_semantic_text(
        confirmation.value,
        "Mary preference name",
        limit=140,
    ).replace("_", " ")
    if hit is not None:
        if not (
            _semantic_key(topic)
            == _semantic_key(hit.get("predicate"))
            == _semantic_key(metadata.get("name"))
            == _semantic_key(requested_topic)
        ):
            raise _UnsupportedProjection("mary_preference_predicate_mismatch")
    elif _semantic_key(topic) != _semantic_key(requested_topic):
        raise _UnsupportedProjection("mary_preference_predicate_mismatch")
    if confirmation.polarity is None:
        raise _UnsupportedProjection("mary_preference_confirmation_incomplete")
    polarity = confirmation.polarity
    if polarity > 0.05:
        predicate = "like"
        stance_polarity = "prefer"
        stance_text = f"Mary likes {topic}."
    elif polarity < -0.05:
        predicate = "dislike"
        stance_polarity = "oppose"
        stance_text = f"Mary dislikes {topic}."
    else:
        predicate = "feel unsure about"
        stance_polarity = "uncertain"
        stance_text = f"Mary is undecided about {topic}."
    clause = RealizationClause(
        clause_id="mary-preference",
        frame=ClauseFrame.ATTRIBUTE,
        subject=SELF,
        predicate=predicate,
        value=topic,
        authority=confirmation.authority,
        source_id=confirmation.selector_id,
    )
    fact = GroundedFact(
        fact_id=confirmation.selector_id,
        subject=confirmation.subject,
        predicate=confirmation.predicate,
        text=stance_text,
        kind=confirmation.kind,
        source=confirmation.source,
        authority=confirmation.authority,
        confidence=confirmation.confidence,
        semantic_clause=clause,
    )
    try:
        stance = RepresentedStance(
            text=stance_text,
            polarity=stance_polarity,
            source=fact.source,
            authority=fact.authority,
            confidence=fact.confidence,
        )
    except (TypeError, ValueError) as exc:
        raise _UnsupportedProjection("mary_preference_authority_unsupported") from exc
    return _canonical(
        dialogue_plan,
        input_text=input_text,
        authority=authority,
        mind_state=mind_state,
        hot_state=hot_state,
        response_intent="State Mary's represented preference in first person.",
        required_meanings=(f"Own the represented stance toward {topic}.",),
        facts=(fact,),
        clauses=(clause,),
        mary_stance=stance,
        max_sentences=1,
        max_words=24,
    )


def _project_semantic_memory_answer(
    dialogue_plan: DialoguePlan,
    *,
    input_text: str,
    authority: ResponseAuthorityContext,
    mind_state: Mapping[str, Any],
    hot_state: Mapping[str, Any],
    owner_confirmations: AuthorityConfirmationBundle,
) -> CanonicalResponsePlan:
    raw_hits = dialogue_plan.slots.get("hits")
    if (
        isinstance(raw_hits, Mapping)
        or isinstance(raw_hits, (str, bytes, bytearray))
        or not isinstance(raw_hits, Sequence)
    ):
        raise _UnsupportedProjection("structured_answer_hits_missing")
    hits = tuple(raw_hits)
    if not hits or len(hits) > 3:
        raise _UnsupportedProjection("structured_answer_hit_count_unsupported")

    facts: list[GroundedFact] = []
    clauses: list[RealizationClause] = []
    meanings: list[str] = []
    requested_topic = _semantic_text(
        dialogue_plan.slots.get("topic"),
        "requested semantic topic",
        limit=140,
    )
    for index, item in enumerate(hits):
        hit = _mapping_or_error(item, "structured_answer_hit_is_not_mapping")
        if str(hit.get("kind") or "").strip().lower() != "semantic_memory":
            raise _UnsupportedProjection("answer_source_lacks_structured_semantics")
        _require_hit_contract(
            hit,
            exact_kind="semantic_memory",
            allowed_authorities={"semantic_memory"},
            minimum_confidence=0.78,
            error_code="semantic_memory_provenance_unsupported",
        )
        metadata = _mapping_or_error(
            hit.get("metadata"),
            "semantic_memory_metadata_missing",
        )
        confirmation = _confirmation_or_error(
            owner_confirmations,
            hit,
            owner="semantic_memory",
        )
        subject_text = _semantic_text(
            confirmation.subject,
            "semantic subject",
            limit=100,
        )
        predicate = _semantic_text(
            confirmation.predicate,
            "semantic predicate",
            limit=100,
        )
        value = _atomic_semantic_text(
            confirmation.value,
            "semantic value",
            limit=180,
        )
        if not (
            _semantic_key(subject_text)
            == _semantic_key(hit.get("subject"))
            == _semantic_key(metadata.get("subject"))
        ):
            raise _UnsupportedProjection("semantic_memory_subject_mismatch")
        if not (
            _semantic_key(predicate)
            == _semantic_key(hit.get("predicate"))
            == _semantic_key(metadata.get("predicate"))
        ):
            raise _UnsupportedProjection("semantic_memory_predicate_mismatch")
        if _semantic_key(value) != _semantic_key(str(metadata.get("value") or "")):
            raise _UnsupportedProjection("semantic_memory_value_mismatch")
        if _semantic_key(requested_topic) not in {
            _semantic_key(subject_text),
            _semantic_key(predicate),
        }:
            raise _UnsupportedProjection("semantic_memory_topic_mismatch")
        property_name = predicate.replace("_", " ")
        participant = _participant_for_subject(subject_text, hot_state=hot_state)
        clause = RealizationClause(
            clause_id=f"semantic-{index + 1}",
            frame=ClauseFrame.POSSESSIVE_FACT,
            subject=participant,
            property_name=property_name,
            value=value,
            authority=confirmation.authority,
            source_id=confirmation.selector_id,
        )
        fact = GroundedFact(
            fact_id=confirmation.selector_id,
            subject=subject_text,
            predicate=predicate.replace(" ", "_"),
            text=f"{subject_text}'s {property_name} is {value}.",
            kind=confirmation.kind,
            source=confirmation.source,
            authority=confirmation.authority,
            confidence=confirmation.confidence,
            semantic_clause=clause,
        )
        facts.append(fact)
        clauses.append(clause)
        meanings.append(f"Preserve {subject_text}'s {property_name}: {value}.")

    return _canonical(
        dialogue_plan,
        input_text=input_text,
        authority=authority,
        mind_state=mind_state,
        hot_state=hot_state,
        response_intent="State only the selected structured semantic-memory values.",
        required_meanings=tuple(meanings),
        facts=tuple(facts),
        clauses=tuple(clauses),
        max_sentences=min(2, len(clauses)),
        max_words=48,
    )


def _project_status(
    dialogue_plan: DialoguePlan,
    *,
    input_text: str,
    authority: ResponseAuthorityContext,
    mind_state: Mapping[str, Any],
    hot_state: Mapping[str, Any],
) -> CanonicalResponsePlan:
    status_kind = str(dialogue_plan.slots.get("status_kind") or "").strip().lower()
    if status_kind == "emotion":
        emotion = _mapping(mind_state.get("emotion")) or _mapping(hot_state.get("emotion"))
        label = _atomic_semantic_text(
            emotion.get("primary", emotion.get("emotion")),
            "represented emotion",
            limit=60,
        ).replace("_", " ")
        confidence = _optional_unit_float(emotion.get("confidence"), default=1.0)
        clause = RealizationClause(
            clause_id="status-emotion",
            frame=ClauseFrame.ATTRIBUTE,
            subject=SELF,
            predicate="be",
            value=label,
            authority="mary_canonical",
            source_id="turn-status:emotion",
        )
        fact = GroundedFact(
            fact_id="turn-status:emotion",
            subject="mary",
            predicate="current_emotion",
            text=f"Mary's represented current emotion is {label}.",
            kind="represented_status",
            source="turn_mind_state",
            authority="mary_canonical",
            confidence=confidence,
            semantic_clause=clause,
        )
        intent = "State Mary's represented current emotion in first person."
        meanings = (f"Mary's current represented emotion is {label}.",)
    elif status_kind == "activity":
        agency = _mapping(mind_state.get("agency"))
        goals = _mapping_sequence(agency.get("active_goals"))
        if not goals:
            goals = _mapping_sequence(hot_state.get("active_goals"))
        description = None
        if goals:
            description = goals[0].get("description") or goals[0].get("title") or goals[0].get("goal")
        if description is not None:
            value = _atomic_semantic_text(
                description,
                "represented active goal",
                limit=140,
            )
            fact_value = value
            predicate = "am keeping"
            object_text = f"{value} in mind"
        else:
            fact_value = "present in this conversation"
            predicate = "am here in this conversation"
            object_text = ""
        clause = RealizationClause(
            clause_id="status-activity",
            frame=ClauseFrame.EVENT,
            subject=SELF,
            predicate=predicate,
            object_text=object_text,
            authority="mary_canonical",
            source_id="turn-status:activity",
        )
        fact = GroundedFact(
            fact_id="turn-status:activity",
            subject="mary",
            predicate="current_activity",
            text=f"Mary is {fact_value}.",
            kind="represented_status",
            source="turn_mind_state",
            authority="mary_canonical",
            confidence=1.0,
            semantic_clause=clause,
        )
        intent = "State only Mary's represented current activity."
        meanings = (f"Mary's represented activity is {fact_value}.",)
    else:
        raise _UnsupportedProjection("represented_status_kind_unsupported")

    return _canonical(
        dialogue_plan,
        input_text=input_text,
        authority=authority,
        mind_state=mind_state,
        hot_state=hot_state,
        response_intent=intent,
        required_meanings=meanings,
        facts=(fact,),
        clauses=(clause,),
        max_sentences=1,
        max_words=32,
    )


def _canonical(
    dialogue_plan: DialoguePlan,
    *,
    input_text: str,
    authority: ResponseAuthorityContext,
    mind_state: Mapping[str, Any],
    hot_state: Mapping[str, Any],
    response_intent: str,
    required_meanings: tuple[str, ...],
    facts: tuple[GroundedFact, ...],
    clauses: tuple[RealizationClause, ...],
    mary_stance: RepresentedStance | None = None,
    question: SemanticQuestion | None = None,
    max_sentences: int = 2,
    max_words: int = 32,
    disposition: str = "neutral",
) -> CanonicalResponsePlan:
    plan_id = _plan_id(input_text, dialogue_plan, hot_state=hot_state)
    form = (
        ResponseForm.QUESTION
        if question is not None
        else ResponseForm.REACTION
        if dialogue_plan.act in {DialogueAct.REACT, DialogueAct.LAUGH}
        else ResponseForm.STATEMENT
    )
    compact_form = (
        "question"
        if form is ResponseForm.QUESTION
        else "reaction"
        if form is ResponseForm.REACTION
        else "greeting"
        if dialogue_plan.act is DialogueAct.GREET
        else "statement"
    )
    form_target = VerbalizationFormTarget(
        response_form=compact_form,
        sentence_min=1,
        sentence_max=max_sentences,
        max_words=max_words,
        exact_question_count=1 if question is not None else 0,
        terminal_punctuation="?" if question is not None else None,
    )
    disposition_view = _mapping(mind_state.get("disposition"))
    familiarity = _optional_plain_text(
        disposition_view.get("familiarity"),
        default="familiar",
        limit=40,
    )
    realization = LocalRealizationPlan(
        plan_id=plan_id,
        dialogue_act=dialogue_plan.act,
        clauses=clauses,
        response_form=form,
        max_sentences=max_sentences,
        max_words=max_words,
        tone="restrained",
        familiarity=familiarity,
        disposition=disposition,
        question=question,
    )
    # Canonical production descriptions are derived after semantic selection.
    # The caller's natural-language summaries remain useful while projecting,
    # but cannot cross the authority boundary or contradict typed clauses.
    canonical_facts = tuple(
        replace(
            fact,
            text=canonical_grounded_fact_text(fact, fact.semantic_clause),
        )
        for fact in facts
    )
    delivery = _delivery_plan(mind_state)
    verbalization = project_verbalization_plan(
        plan_id=plan_id,
        input_text=bounded_response_scalar("local input", input_text, limit=320),
        dialogue_plan=dialogue_plan,
        conversational_drive=_drive(mind_state, dialogue_plan.act),
        response_intent=canonical_response_intent(realization),
        delivery_plan=delivery,
        delivery_tone="restrained conversational",
        grounded_facts=canonical_facts,
        mary_stance=mary_stance,
        required_meanings=canonical_required_meanings(realization),
        form_target=form_target,
    )
    return CanonicalResponsePlan(
        verbalization=verbalization,
        authority_context=authority,
        realization=realization,
    )


def _delivery_plan(mind_state: Mapping[str, Any]) -> DeliveryPlan:
    disposition = _mapping(mind_state.get("disposition"))
    performance = _mapping(mind_state.get("performance"))
    energy = _optional_unit_float(performance.get("energy"), default=0.4)
    warmth = _optional_unit_float(disposition.get("warmth"), default=0.55)
    theatricality = _optional_unit_float(
        performance.get("theatricality"),
        default=0.2,
    )
    restraint = max(0.75, min(0.95, 1.0 - theatricality * 0.25))
    return DeliveryPlan(
        profile="conversational",
        energy=energy,
        warmth=warmth,
        stability=0.58,
        style=min(0.06, theatricality * 0.08),
        emphasis=0.15,
        gesture_energy=0.18,
        rationale="canonical pre-wording local response target",
        metadata={"restraint": restraint, "performance_mode": "natural_conversation"},
    )


def _drive(
    mind_state: Mapping[str, Any],
    act: DialogueAct,
) -> ConversationalDrive:
    continuity = _mapping(mind_state.get("continuity"))
    value = str(continuity.get("drive") or "").strip().lower()
    try:
        return ConversationalDrive(value)
    except ValueError:
        mapping = {
            DialogueAct.GREET: ConversationalDrive.ACKNOWLEDGE,
            DialogueAct.ACKNOWLEDGE: ConversationalDrive.ACKNOWLEDGE,
            DialogueAct.REACT: ConversationalDrive.REACT,
            DialogueAct.LAUGH: ConversationalDrive.REACT,
            DialogueAct.KNOWN_FACT: ConversationalDrive.ANSWER,
            DialogueAct.KNOWN_PREFERENCE: ConversationalDrive.OPINE,
            DialogueAct.ANSWER: ConversationalDrive.ANSWER,
            DialogueAct.FOLLOW_UP: ConversationalDrive.ASK,
        }
        return mapping.get(act, ConversationalDrive.REACT)


def _participant_for_subject(
    subject: str,
    *,
    hot_state: Mapping[str, Any],
) -> ParticipantRef:
    normalized = " ".join(subject.casefold().replace("_", " ").split())
    mary_name = str(hot_state.get("mary_name") or "mary").strip().casefold()
    creator_name = str(hot_state.get("creator_name") or "unbe").strip().casefold()
    if normalized in {"mary", "self", "i", mary_name}:
        return SELF
    if normalized in {"creator", "user", "addressee", "unbe", creator_name}:
        return ADDRESSEE
    if normalized in {"we", "us", "joint", "shared", "shared history", "shared_history"}:
        return JOINT
    if normalized in {"world", "it"}:
        return WORLD
    surface = bounded_response_scalar(
        "named semantic subject",
        " ".join(subject.replace("_", " ").split()),
        limit=100,
    )
    entity_id = "semantic-" + hashlib.sha256(surface.casefold().encode("utf-8")).hexdigest()[:16]
    return ParticipantRef(
        ParticipantRole.NAMED_ENTITY,
        entity_id=entity_id,
        surface=surface,
    )


def _plan_id(
    input_text: str,
    dialogue_plan: DialoguePlan,
    *,
    hot_state: Mapping[str, Any],
) -> str:
    material = (
        f"{input_text}|{dialogue_plan.act.value}|"
        f"{hot_state.get('dialogue_turn', 0)}"
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    return f"local:{digest}"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_or_error(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _UnsupportedProjection(code)
    return value


def _confirmation_or_error(
    confirmations: AuthorityConfirmationBundle,
    hit: Mapping[str, Any],
    *,
    owner: str,
) -> ConfirmedAuthorityScalar:
    confirmation = confirmations.for_selector(hit.get("record_id"))
    if confirmation is None or confirmation.owner != owner:
        raise _UnsupportedProjection("canonical_owner_confirmation_missing")
    return confirmation


def _mapping_sequence(value: Any) -> tuple[Mapping[str, Any], ...]:
    if (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray, Mapping))
    ):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _semantic_text(value: Any, name: str, *, limit: int) -> str:
    if isinstance(value, bool) or isinstance(value, Mapping) or (
        isinstance(value, Sequence) and not isinstance(value, str)
    ):
        raise _UnsupportedProjection(f"{name.replace(' ', '_')}_is_not_scalar")
    if isinstance(value, Real):
        number = float(value)
        if not math.isfinite(number):
            raise _UnsupportedProjection(f"{name.replace(' ', '_')}_is_not_finite")
        value = str(value)
    try:
        return bounded_response_scalar(name, value, limit=limit)
    except (TypeError, ValueError) as exc:
        raise _UnsupportedProjection(f"{name.replace(' ', '_')}_invalid") from exc


def _atomic_semantic_text(value: Any, name: str, *, limit: int) -> str:
    """Accept one bounded scalar phrase, never an embedded response clause."""

    # Numeric owner values are already finite typed scalars.  Their decimal
    # point is data, not sentence punctuation, so do not reject it as an
    # embedded clause boundary.
    if isinstance(value, Real) and not isinstance(value, bool):
        return _semantic_text(value, name, limit=limit)
    text = _semantic_text(value, name, limit=limit)
    if re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)", text):
        return text
    code = name.replace(" ", "_")
    if re.search(r"[.!?;:\r\n\u2028\u2029]", text):
        raise _UnsupportedProjection(f"{code}_not_atomic")
    if re.search(r"\b(?:i|you|we)\b", text, re.I):
        raise _UnsupportedProjection(f"{code}_not_atomic")
    if re.search(
        r"\bmary\s+(?:is|am|are|likes?|dislikes?|prefers?|thinks?|feels?|knows?|can|cannot|can't)\b",
        text,
        re.I,
    ):
        raise _UnsupportedProjection(f"{code}_not_atomic")
    if re.search(r"\b(?:let me know|if you want|hope that helps)\b", text, re.I):
        raise _UnsupportedProjection(f"{code}_not_atomic")
    return text


def _optional_plain_text(value: Any, *, default: str, limit: int) -> str:
    if value is None or not isinstance(value, str) or not value.strip():
        return default
    try:
        return bounded_response_scalar("optional response scalar", value, limit=limit)
    except (TypeError, ValueError):
        return default


def _real_scalar(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise _UnsupportedProjection(f"{name.replace(' ', '_')}_is_not_numeric")
    number = float(value)
    if not math.isfinite(number):
        raise _UnsupportedProjection(f"{name.replace(' ', '_')}_is_not_finite")
    return number


def _optional_unit_float(value: Any, *, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        return default
    number = float(value)
    if not math.isfinite(number):
        return default
    return max(0.0, min(1.0, number))


def _require_hit_contract(
    hit: Mapping[str, Any],
    *,
    allowed_authorities: set[str],
    minimum_confidence: float,
    error_code: str,
    exact_kind: str | None = None,
    kind_prefix: str | None = None,
) -> None:
    kind = str(hit.get("kind") or "").strip().casefold()
    authority = str(hit.get("authority") or "").strip().casefold()
    try:
        confidence = _real_scalar(hit.get("confidence"), "record confidence")
    except _UnsupportedProjection as exc:
        raise _UnsupportedProjection(error_code) from exc
    kind_ok = (
        kind == exact_kind
        if exact_kind is not None
        else bool(kind_prefix and kind.startswith(kind_prefix))
    )
    if (
        not kind_ok
        or authority not in allowed_authorities
        or not 0.0 <= confidence <= 1.0
        or confidence < minimum_confidence
    ):
        raise _UnsupportedProjection(error_code)


def _semantic_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.casefold().replace("_", " ").split()).strip()


def _literal_precision_domain(input_text: str) -> str | None:
    """Conservatively tag authority-shaped nonlocal questions.

    These tags grant no local answer permission.  They only prevent capability,
    runtime, uncertainty, stance, and reference-sensitive turns from being
    mislabeled as ordinary open conversation before the authoritative/model
    path receives them.
    """

    text = " ".join(str(input_text or "").casefold().split())
    patterns = (
        (
            "creator_fact_reference",
            r"\bwhat(?:'s| is) my [a-z0-9 _-]{2,50}\??$",
        ),
        (
            "mary_fact_reference",
            r"\bwhat(?:'s| is) (?:your|mary's) [a-z0-9 _-]{2,50}\??$",
        ),
        (
            "structured_knowledge_query",
            r"\b(?:what do you know about|tell me what you know about)\b",
        ),
        (
            "shared_history_reference",
            r"\b(?:remember when|when we|(?:did|have) we|we (?:said|did|worked|talked|shipped|built|changed|sent)|our (?:history|conversation)|shared history|last time|earlier conversation)\b",
        ),
        (
            "pronoun_sensitive_relation",
            r"\b(?:you told me|i told you|between you and me|your relationship with|my relationship with|who (?:said|made|created|asked|told|wrote|decided|gave|sent|changed|shipped|built)|who did what)\b",
        ),
        (
            "current_project_state",
            r"\b(?:our project|current project|project state|where (?:are|were) we|what are we working on|status of (?:the|our) project)\b",
        ),
        (
            "provenance_boundary",
            r"\b(?:provenance|source of|where did .{1,80} come from|who does .{1,80} belong to)\b",
        ),
        (
            "preference_ownership",
            r"\b(?:(?:do i|do you|does mary) (?:like|prefer|dislike)|how do you feel about|what do you think of|whose preference|my preference|your preference)\b",
        ),
        (
            "runtime_boundary",
            r"\b(?:runtime|version|provider|model|latency|token budget|system status)\b",
        ),
        (
            "capability_boundary",
            r"\b(?:can you|are you able|do you have access|could you|what can you)\b",
        ),
        (
            "uncertainty_boundary",
            r"\b(?:are you sure|do you know|uncertain|unsure|don't know|do not know|maybe)\b",
        ),
        (
            "represented_stance_reference",
            r"\b(?:i disagree|you disagree|that's wrong|that is wrong|your opinion|your stance)\b",
        ),
    )
    for domain, pattern in patterns:
        if re.search(pattern, text):
            return domain
    return None
