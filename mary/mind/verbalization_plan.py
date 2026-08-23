"""Immutable boundary between Mary's decided intent and replaceable wording.

This module does not call a model and is not wired into production routing.  It
only defines the compact, provider-independent projection used by the Qwen
Micro-Cortex benchmark.  Canonical identity, memory, relationship, preference,
knowledge, and agency owners remain outside this object.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from numbers import Real
import re
from typing import Any
import unicodedata

from mary.cognition.continuity import ConversationalDrive
from mary.expression.delivery_plan import DeliveryPlan

from .dialogue_acts import DialogueAct, DialoguePlan


GROUNDING_AUTHORITIES = frozenset({
    "creator_explicit",
    "creator_structured",
    "mary_canonical",
    "mary_developed",
    "semantic_memory",
    "episodic_history",
    "knowledge_verified",
    "turn_literal",
    "experiment_contract",
})

# Relationship/context hints are narrower than general factual grounding. A
# verified knowledge record can support a fact, but it cannot by itself create
# relationship truth. Keep only authorities that can legitimately represent
# Mary's or the creator's context, history, or the literal current turn.
RELATIONSHIP_HINT_AUTHORITIES = frozenset({
    "creator_explicit",
    "creator_structured",
    "mary_canonical",
    "mary_developed",
    "semantic_memory",
    "episodic_history",
    "turn_literal",
    "experiment_contract",
})

VERBALIZER_CAPABILITY_CONSTRAINTS = (
    "wording_only",
    "no_identity_or_personality_decisions",
    "no_memory_creation_or_authoritative_state_changes",
    "no_new_facts_preferences_motives_relationship_claims_or_capabilities",
    "no_deep_reasoning",
)

VERBALIZER_PROVENANCE_CONSTRAINT = (
    "Grounded facts, represented stance, literal turn text, and relevant context "
    "hints are exhaustive; unsupported claims must not be added."
)

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,95}$")
_STANCE_POLARITIES = frozenset({"prefer", "oppose", "agree", "disagree", "uncertain", "mixed"})
_NON_TEXT_SEQUENCE_TYPES = (bytes, bytearray, memoryview)
_UNSAFE_TEXT_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})
_MAX_REQUIRED_MEANINGS = 4
_MAX_REQUIRED_MEANING_LENGTH = 280
_MAX_REQUIRED_MEANINGS_TOTAL = 800


def _require_plain_string(name: str, value: Any) -> str:
    """Accept only plain scalar text with no hidden control/format characters."""

    if isinstance(value, Mapping):
        raise TypeError(f"{name} must be a string, not a mapping")
    if isinstance(value, Sequence) and not isinstance(value, str):
        raise TypeError(f"{name} must be a string, not a sequence")
    if isinstance(value, _NON_TEXT_SEQUENCE_TYPES):
        raise TypeError(f"{name} must be a string, not bytes")
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if any(unicodedata.category(character) in _UNSAFE_TEXT_CATEGORIES for character in value):
        raise ValueError(f"{name} must not contain control or formatting characters")
    return value


def _bounded_text(name: str, value: Any, *, limit: int) -> str:
    text = " ".join(_require_plain_string(name, value).split()).strip()
    if not text:
        raise ValueError(f"{name} is required")
    if len(text) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return text


def _bounded_unit_float(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real numeric scalar")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


def _bounded_id(name: str, value: Any) -> str:
    text = _require_plain_string(name, value).strip().lower()
    if not _ID_RE.fullmatch(text):
        raise ValueError(f"{name} must be a compact stable identifier")
    return text


def _bounded_text_tuple(
    name: str,
    values: Any,
    *,
    max_items: int,
    item_limit: int,
    total_limit: int,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, Mapping):
        raise TypeError(f"{name} must be a sequence of strings, not a mapping")
    if isinstance(values, (str, *_NON_TEXT_SEQUENCE_TYPES)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be a sequence of strings")
    items = tuple(_bounded_text(f"{name} item", item, limit=item_limit) for item in values)
    if not allow_empty and not items:
        raise ValueError(f"{name} must contain at least one item")
    if len(items) > max_items:
        raise ValueError(f"{name} may contain at most {max_items} items")
    if len(set(items)) != len(items):
        raise ValueError(f"{name} must not contain duplicate items")
    if sum(len(item) for item in items) > total_limit:
        raise ValueError(f"{name} exceeds the compact total of {total_limit} characters")
    return items


def _bounded_int(name: str, value: Any, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class GroundedFact:
    """A scalar-only projection of one represented fact."""

    fact_id: str
    subject: str
    predicate: str
    text: str
    kind: str
    source: str
    authority: str
    confidence: float

    def __post_init__(self) -> None:
        # SemanticMemory deliberately preserves domain subjects/predicates such
        # as project names. Keep them bounded and scalar without forcing them
        # into the smaller creator/mary/world vocabulary used by other sources.
        object.__setattr__(self, "fact_id", _bounded_text("fact_id", self.fact_id, limit=160))
        object.__setattr__(self, "subject", _bounded_text("fact subject", self.subject, limit=120))
        object.__setattr__(self, "predicate", _bounded_text("fact predicate", self.predicate, limit=120))
        object.__setattr__(self, "text", _bounded_text("fact text", self.text, limit=320))
        object.__setattr__(self, "kind", _bounded_text("fact kind", self.kind, limit=80))
        object.__setattr__(self, "source", _bounded_text("fact source", self.source, limit=120))
        authority = _bounded_id("fact authority", self.authority)
        if authority not in GROUNDING_AUTHORITIES:
            raise ValueError(f"unsupported grounding authority: {authority or '<empty>'}")
        object.__setattr__(self, "authority", authority)
        object.__setattr__(self, "confidence", _bounded_unit_float("fact confidence", self.confidence))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GroundedFact":
        """Load an already-sanitized fact and reject hidden/unknown fields."""

        expected = {
            "fact_id", "subject", "predicate", "text", "kind", "source",
            "authority", "confidence",
        }
        keys = set(payload)
        if keys != expected:
            missing = sorted(expected - keys)
            extra = sorted(keys - expected)
            raise ValueError(f"grounded fact fields mismatch; missing={missing}, extra={extra}")
        return cls(**{key: payload[key] for key in expected})

    @classmethod
    def from_reservoir_hit(cls, hit: Any) -> "GroundedFact":
        """Copy only provenance-bearing scalar fields from a reservoir hit.

        Reservoir metadata and scores are deliberately not forwarded.  This is
        the narrow projection boundary that keeps raw/user state out of a model
        prompt.
        """

        payload = hit.to_dict() if callable(getattr(hit, "to_dict", None)) else dict(hit)
        return cls(
            fact_id=payload.get("record_id"),
            subject=payload.get("subject"),
            predicate=payload.get("predicate"),
            text=payload.get("content"),
            kind=payload.get("kind"),
            source=payload.get("source"),
            authority=payload.get("authority"),
            confidence=payload.get("confidence"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "subject": self.subject,
            "predicate": self.predicate,
            "text": self.text,
            "kind": self.kind,
            "source": self.source,
            "authority": self.authority,
            "confidence": round(self.confidence, 3),
        }


@dataclass(frozen=True, slots=True)
class RepresentedStance:
    """A stance Mary already owns; never a model-created preference."""

    text: str
    polarity: str
    source: str
    authority: str
    confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _bounded_text("stance text", self.text, limit=240))
        polarity = _bounded_id("stance polarity", self.polarity)
        if polarity not in _STANCE_POLARITIES:
            raise ValueError(f"unsupported stance polarity: {polarity or '<empty>'}")
        object.__setattr__(self, "polarity", polarity)
        object.__setattr__(self, "source", _bounded_text("stance source", self.source, limit=120))
        authority = _bounded_id("stance authority", self.authority)
        if authority not in {"mary_canonical", "mary_developed"}:
            raise ValueError("Mary stance must come from mary_canonical or mary_developed authority")
        object.__setattr__(self, "authority", authority)
        object.__setattr__(self, "confidence", _bounded_unit_float("stance confidence", self.confidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "polarity": self.polarity,
            "source": self.source,
            "authority": self.authority,
            "confidence": round(self.confidence, 3),
        }


@dataclass(frozen=True, slots=True)
class RelationshipHint:
    """One relevant relationship/context hint, not a general profile dump."""

    text: str
    source: str
    authority: str
    confidence: float
    relevance: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _bounded_text("relationship hint", self.text, limit=200))
        object.__setattr__(self, "source", _bounded_text("relationship-hint source", self.source, limit=120))
        authority = _bounded_id("relationship-hint authority", self.authority)
        if authority not in RELATIONSHIP_HINT_AUTHORITIES:
            raise ValueError(f"unsupported relationship-hint authority: {authority or '<empty>'}")
        object.__setattr__(self, "authority", authority)
        object.__setattr__(self, "confidence", _bounded_unit_float("hint confidence", self.confidence))
        relevance = _bounded_unit_float("hint relevance", self.relevance)
        if relevance < 0.7:
            raise ValueError("relationship hints must be directly relevant (>= 0.7)")
        object.__setattr__(self, "relevance", relevance)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "authority": self.authority,
            "confidence": round(self.confidence, 3),
            "relevance": round(self.relevance, 3),
        }


@dataclass(frozen=True, slots=True)
class VerbalizationDeliveryTarget:
    """Compact pre-wording projection of the provider-independent delivery plan."""

    profile: str
    tone: str
    energy: float
    warmth: float
    restraint: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile", _bounded_id("delivery profile", self.profile))
        object.__setattr__(self, "tone", _bounded_text("delivery tone", self.tone, limit=120))
        object.__setattr__(self, "energy", _bounded_unit_float("delivery energy", self.energy))
        object.__setattr__(self, "warmth", _bounded_unit_float("delivery warmth", self.warmth))
        object.__setattr__(self, "restraint", _bounded_unit_float("delivery restraint", self.restraint))

    @classmethod
    def from_delivery_plan(cls, plan: DeliveryPlan, *, tone: str) -> "VerbalizationDeliveryTarget":
        metadata = dict(plan.metadata or {})
        restraint = metadata.get("restraint")
        if restraint is None:
            restraint = max(0.0, min(1.0, 1.0 - (float(plan.style) * 2.0)))
        return cls(
            profile=plan.profile,
            tone=tone,
            energy=plan.energy,
            warmth=plan.warmth,
            restraint=restraint,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "tone": self.tone,
            "energy": round(self.energy, 3),
            "warmth": round(self.warmth, 3),
            "restraint": round(self.restraint, 3),
        }


@dataclass(frozen=True, slots=True)
class VerbalizationFormTarget:
    """Scalar-only surface form already selected before model wording."""

    response_form: str
    sentence_min: int = 1
    sentence_max: int = 2
    max_words: int = 32
    exact_question_count: int | None = None
    terminal_punctuation: str | None = None

    def __post_init__(self) -> None:
        response_form = _bounded_id("response form", self.response_form)
        object.__setattr__(self, "response_form", response_form)
        sentence_min = _bounded_int("sentence_min", self.sentence_min, minimum=1, maximum=2)
        sentence_max = _bounded_int("sentence_max", self.sentence_max, minimum=1, maximum=2)
        if sentence_min > sentence_max:
            raise ValueError("sentence_min must not exceed sentence_max")
        max_words = _bounded_int("max_words", self.max_words, minimum=1, maximum=64)
        if max_words < sentence_min:
            raise ValueError("max_words must allow at least one word per requested sentence")

        question_count = self.exact_question_count
        punctuation = self.terminal_punctuation
        if response_form == "question":
            if question_count is None:
                question_count = 1
            if punctuation is None:
                punctuation = "?"
        if question_count is not None:
            question_count = _bounded_int(
                "exact_question_count",
                question_count,
                minimum=0,
                maximum=2,
            )
            if question_count > sentence_max:
                raise ValueError("exact_question_count must not exceed sentence_max")

        if punctuation is not None:
            punctuation = _require_plain_string("terminal_punctuation", punctuation)
            if punctuation not in {".", "?", "!"}:
                raise ValueError("terminal_punctuation must be one of '.', '?', '!', or None")
        if question_count and punctuation != "?":
            raise ValueError("a positive exact_question_count requires '?' terminal punctuation")
        if question_count == 0 and punctuation == "?":
            raise ValueError("zero exact questions cannot require '?' terminal punctuation")

        object.__setattr__(self, "sentence_min", sentence_min)
        object.__setattr__(self, "sentence_max", sentence_max)
        object.__setattr__(self, "max_words", max_words)
        object.__setattr__(self, "exact_question_count", question_count)
        object.__setattr__(self, "terminal_punctuation", punctuation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "response_form": self.response_form,
            "sentence_min": self.sentence_min,
            "sentence_max": self.sentence_max,
            "max_words": self.max_words,
            "exact_question_count": self.exact_question_count,
            "terminal_punctuation": self.terminal_punctuation,
        }


@dataclass(frozen=True, slots=True)
class CompactVerbalizationPlan:
    """Everything a wording-only model may see, and nothing authoritative."""

    plan_id: str
    input_text: str
    dialogue_act: DialogueAct
    conversational_drive: ConversationalDrive
    response_intent: str
    required_meanings: tuple[str, ...]
    grounded_facts: tuple[GroundedFact, ...]
    mary_stance: RepresentedStance | None
    relationship_hints: tuple[RelationshipHint, ...]
    delivery_target: VerbalizationDeliveryTarget
    form_target: VerbalizationFormTarget
    capability_constraints: tuple[str, ...] = field(
        default=VERBALIZER_CAPABILITY_CONSTRAINTS,
        init=False,
    )
    provenance_constraint: str = field(
        default=VERBALIZER_PROVENANCE_CONSTRAINT,
        init=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", _bounded_id("plan_id", self.plan_id))
        object.__setattr__(self, "input_text", _bounded_text("input_text", self.input_text, limit=320))
        if not isinstance(self.dialogue_act, DialogueAct):
            raise TypeError("dialogue_act must be a DialogueAct")
        if not isinstance(self.conversational_drive, ConversationalDrive):
            raise TypeError("conversational_drive must be a ConversationalDrive")
        object.__setattr__(self, "response_intent", _bounded_text("response_intent", self.response_intent, limit=280))
        meanings = _bounded_text_tuple(
            "required_meanings",
            self.required_meanings,
            max_items=_MAX_REQUIRED_MEANINGS,
            item_limit=_MAX_REQUIRED_MEANING_LENGTH,
            total_limit=_MAX_REQUIRED_MEANINGS_TOTAL,
        )
        if isinstance(self.grounded_facts, Mapping) or isinstance(
            self.grounded_facts,
            (str, *_NON_TEXT_SEQUENCE_TYPES),
        ) or not isinstance(self.grounded_facts, Sequence):
            raise TypeError("grounded_facts must be a sequence of GroundedFact values")
        if isinstance(self.relationship_hints, Mapping) or isinstance(
            self.relationship_hints,
            (str, *_NON_TEXT_SEQUENCE_TYPES),
        ) or not isinstance(self.relationship_hints, Sequence):
            raise TypeError("relationship_hints must be a sequence of RelationshipHint values")
        facts = tuple(self.grounded_facts)
        hints = tuple(self.relationship_hints)
        if len(facts) > 3:
            raise ValueError("compact plans may include at most three grounded facts")
        if any(not isinstance(item, GroundedFact) for item in facts):
            raise TypeError("grounded_facts must contain GroundedFact values")
        if len({item.fact_id for item in facts}) != len(facts):
            raise ValueError("grounded facts must have unique fact_id values")
        if len(hints) > 2:
            raise ValueError("compact plans may include at most two relationship hints")
        if any(not isinstance(item, RelationshipHint) for item in hints):
            raise TypeError("relationship_hints must contain RelationshipHint values")
        if self.mary_stance is not None and not isinstance(self.mary_stance, RepresentedStance):
            raise TypeError("mary_stance must be a RepresentedStance or None")
        if not isinstance(self.delivery_target, VerbalizationDeliveryTarget):
            raise TypeError("delivery_target must be a VerbalizationDeliveryTarget")
        if not isinstance(self.form_target, VerbalizationFormTarget):
            raise TypeError("form_target must be a VerbalizationFormTarget")
        object.__setattr__(self, "required_meanings", meanings)
        object.__setattr__(self, "grounded_facts", facts)
        object.__setattr__(self, "relationship_hints", hints)

    @property
    def sentence_min(self) -> int:
        """Compatibility view for existing benchmark renderers/evaluators."""

        return self.form_target.sentence_min

    @property
    def sentence_max(self) -> int:
        """Compatibility view for existing benchmark renderers/evaluators."""

        return self.form_target.sentence_max

    def to_prompt_payload(self) -> dict[str, Any]:
        """Return the complete model-visible projection and no raw source IDs."""

        return {
            "input_text": self.input_text,
            "dialogue_act": self.dialogue_act.value,
            "conversational_drive": self.conversational_drive.value,
            "response_intent": self.response_intent,
            "required_meanings": list(self.required_meanings),
            "grounded_facts": [
                {
                    "text": item.text,
                    "authority": item.authority,
                    "confidence": round(item.confidence, 3),
                }
                for item in self.grounded_facts
            ],
            "mary_stance": (
                {
                    "text": self.mary_stance.text,
                    "polarity": self.mary_stance.polarity,
                    "authority": self.mary_stance.authority,
                    "confidence": round(self.mary_stance.confidence, 3),
                }
                if self.mary_stance
                else None
            ),
            "relationship_hints": [
                {
                    "text": item.text,
                    "authority": item.authority,
                    "confidence": round(item.confidence, 3),
                    "relevance": round(item.relevance, 3),
                }
                for item in self.relationship_hints
            ],
            "delivery_target": self.delivery_target.to_dict(),
            "form_target": self.form_target.to_dict(),
            "sentence_target": {"min": self.sentence_min, "max": self.sentence_max},
            "capability_constraints": list(self.capability_constraints),
            "provenance_constraint": self.provenance_constraint,
            "authoritative_state_access": "none",
        }

    def to_model_dict(self) -> dict[str, Any]:
        """Compatibility alias for the canonical model-visible projection."""

        return self.to_prompt_payload()

    def to_report_dict(self) -> dict[str, Any]:
        payload = self.to_prompt_payload()
        payload["grounded_facts"] = [item.to_dict() for item in self.grounded_facts]
        payload["mary_stance"] = self.mary_stance.to_dict() if self.mary_stance else None
        payload["relationship_hints"] = [item.to_dict() for item in self.relationship_hints]
        return {"plan_id": self.plan_id, **payload}


_NON_VERBALIZABLE_ACTS = frozenset({DialogueAct.STAY_QUIET, DialogueAct.ESCALATE})
_QUESTION_ACTS = frozenset({DialogueAct.ASK, DialogueAct.FOLLOW_UP, DialogueAct.CLARIFY})


def _validate_projectable_dialogue_plan(plan: Any) -> DialoguePlan:
    if not isinstance(plan, DialoguePlan):
        raise TypeError("dialogue_plan must be a DialoguePlan")
    if plan.local is not True:
        raise ValueError("verbalization projection requires an already-decided local DialoguePlan")
    if not isinstance(plan.act, DialogueAct):
        raise TypeError("dialogue_plan.act must be a DialogueAct")
    if plan.act in _NON_VERBALIZABLE_ACTS:
        raise ValueError(f"dialogue act {plan.act.value} must not be projected to a verbalizer")
    if not isinstance(plan.slots, Mapping):
        raise TypeError("dialogue_plan.slots must be a mapping")
    return plan


def grounded_facts_from_dialogue_plan(plan: DialoguePlan) -> tuple[GroundedFact, ...]:
    """Project selected reservoir hits from mutable DialoguePlan slots."""

    plan = _validate_projectable_dialogue_plan(plan)
    raw: list[Any] = []
    hit = plan.slots.get("hit")
    if hit is not None:
        raw.append(hit)
    hits = plan.slots.get("hits")
    if hits is None:
        hits = ()
    if isinstance(hits, Mapping) or isinstance(hits, (str, *_NON_TEXT_SEQUENCE_TYPES)) or not isinstance(hits, Sequence):
        raise TypeError("dialogue_plan.slots['hits'] must be a sequence of reservoir hits")
    raw.extend(hits)
    facts: list[GroundedFact] = []
    seen: dict[str, GroundedFact] = {}
    for item in raw:
        fact = GroundedFact.from_reservoir_hit(item)
        existing = seen.get(fact.fact_id)
        if existing is None:
            seen[fact.fact_id] = fact
            facts.append(fact)
        elif existing != fact:
            raise ValueError(
                f"conflicting duplicate fact_id in dialogue plan: {fact.fact_id}"
            )
    return tuple(facts)


def project_verbalization_plan(
    *,
    plan_id: str,
    input_text: str,
    dialogue_plan: DialoguePlan,
    conversational_drive: ConversationalDrive,
    response_intent: str,
    delivery_plan: DeliveryPlan,
    delivery_tone: str,
    grounded_facts: Sequence[GroundedFact] | None = None,
    mary_stance: RepresentedStance | None = None,
    relationship_hints: Sequence[RelationshipHint] = (),
    required_meanings: Sequence[str] | None = None,
    form_target: VerbalizationFormTarget | None = None,
    response_form: str | None = None,
    sentence_min: int | None = None,
    sentence_max: int | None = None,
    max_words: int | None = None,
    exact_question_count: int | None = None,
    terminal_punctuation: str | None = None,
) -> CompactVerbalizationPlan:
    """Copy an already-decided local response into the immutable boundary."""

    dialogue_plan = _validate_projectable_dialogue_plan(dialogue_plan)
    if grounded_facts is not None and (
        isinstance(grounded_facts, Mapping)
        or isinstance(grounded_facts, (str, *_NON_TEXT_SEQUENCE_TYPES))
        or not isinstance(grounded_facts, Sequence)
    ):
        raise TypeError("grounded_facts must be a sequence of GroundedFact values")
    if (
        isinstance(relationship_hints, Mapping)
        or isinstance(relationship_hints, (str, *_NON_TEXT_SEQUENCE_TYPES))
        or not isinstance(relationship_hints, Sequence)
    ):
        raise TypeError("relationship_hints must be a sequence of RelationshipHint values")
    selected = (
        tuple(grounded_facts)
        if grounded_facts is not None
        else grounded_facts_from_dialogue_plan(dialogue_plan)
    )
    selected_meanings: Sequence[str] = (
        (response_intent,)
        if required_meanings is None
        else required_meanings
    )

    if form_target is not None:
        if not isinstance(form_target, VerbalizationFormTarget):
            raise TypeError("form_target must be a VerbalizationFormTarget")
        if any(value is not None for value in (
            response_form,
            sentence_min,
            sentence_max,
            max_words,
            exact_question_count,
            terminal_punctuation,
        )):
            raise ValueError("form_target cannot be combined with individual form arguments")
        selected_form_target = form_target
    else:
        target_length = _bounded_id("dialogue target_length", dialogue_plan.target_length)
        selected_response_form = (
            response_form
            if response_form is not None
            else (
                "question" if dialogue_plan.act in _QUESTION_ACTS else
                "reaction" if dialogue_plan.act in {DialogueAct.REACT, DialogueAct.LAUGH} else
                "greeting" if dialogue_plan.act is DialogueAct.GREET else
                "statement"
            )
        )
        selected_sentence_min = 1 if sentence_min is None else sentence_min
        selected_sentence_max = 2 if sentence_max is None else sentence_max
        selected_max_words = (
            (18 if target_length == "micro" else 32)
            if max_words is None
            else max_words
        )
        selected_question_count = exact_question_count
        selected_terminal_punctuation = terminal_punctuation
        if selected_response_form == "question":
            if selected_question_count is None:
                selected_question_count = 1
            if selected_terminal_punctuation is None:
                selected_terminal_punctuation = "?"
        selected_form_target = VerbalizationFormTarget(
            response_form=selected_response_form,
            sentence_min=selected_sentence_min,
            sentence_max=selected_sentence_max,
            max_words=selected_max_words,
            exact_question_count=selected_question_count,
            terminal_punctuation=selected_terminal_punctuation,
        )

    return CompactVerbalizationPlan(
        plan_id=plan_id,
        input_text=input_text,
        dialogue_act=dialogue_plan.act,
        conversational_drive=conversational_drive,
        response_intent=response_intent,
        required_meanings=selected_meanings,
        grounded_facts=selected,
        mary_stance=mary_stance,
        relationship_hints=tuple(relationship_hints),
        delivery_target=VerbalizationDeliveryTarget.from_delivery_plan(
            delivery_plan,
            tone=delivery_tone,
        ),
        form_target=selected_form_target,
    )
