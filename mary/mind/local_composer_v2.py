"""Typed procedural dialogue renderer for Mary's local response path.

V2 consumes an immutable, already-authorized semantic plan with explicit
participant roles.  It never parses reservoir prose, retrieves state, calls a
model, owns authority, or writes phrase history.  The hybrid benchmark also
exercises this deterministic engine, while all Qwen candidates remain
invisible benchmark-only shadows.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from numbers import Real
import random
import re
from time import perf_counter_ns
from typing import Any
import unicodedata

from .dialogue_acts import DialogueAct


class ParticipantRole(str, Enum):
    SELF = "self"
    ADDRESSEE = "addressee"
    JOINT = "joint"
    WORLD = "world"
    NAMED_ENTITY = "named_entity"


class ClauseFrame(str, Enum):
    ATTRIBUTE = "attribute"
    POSSESSIVE_FACT = "possessive_fact"
    PREFERENCE = "preference"
    DISAGREEMENT = "disagreement"
    EVENT = "event"
    CAPABILITY = "capability"
    UNKNOWN = "unknown"
    SUGGESTION = "suggestion"
    RUNTIME_VALUE = "runtime_value"


class Certainty(str, Enum):
    CERTAIN = "certain"
    QUALIFIED = "qualified"
    UNKNOWN = "unknown"


class ResponseForm(str, Enum):
    STATEMENT = "statement"
    QUESTION = "question"
    REACTION = "reaction"


class QuestionKind(str, Enum):
    INVITATION = "invitation"
    POLAR = "polar"
    ALTERNATIVE = "alternative"


@dataclass(frozen=True, slots=True)
class ParticipantRef:
    role: ParticipantRole
    entity_id: str | None = None
    surface: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.role, ParticipantRole):
            raise TypeError("participant role must be a ParticipantRole")
        if self.role == ParticipantRole.NAMED_ENTITY:
            entity_id = _piece(self.entity_id, "participant entity_id", limit=160)
            surface = _piece(self.surface, "participant surface", limit=120)
            object.__setattr__(self, "entity_id", entity_id)
            object.__setattr__(self, "surface", surface)
        elif self.entity_id is not None or self.surface is not None:
            raise ValueError("speaker-relative participants cannot carry identity labels")

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "entity_id": self.entity_id,
            "surface": self.surface,
        }


SELF = ParticipantRef(ParticipantRole.SELF)
ADDRESSEE = ParticipantRef(ParticipantRole.ADDRESSEE)
JOINT = ParticipantRef(ParticipantRole.JOINT)
WORLD = ParticipantRef(ParticipantRole.WORLD)


@dataclass(frozen=True, slots=True)
class DependentEvent:
    connector: str
    subject: ParticipantRef
    predicate: str
    object_text: str = ""
    recipient: ParticipantRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.subject, ParticipantRef):
            raise TypeError("dependent-event subject must be a ParticipantRef")
        if self.recipient is not None and not isinstance(self.recipient, ParticipantRef):
            raise TypeError("dependent-event recipient must be a ParticipantRef or None")
        connector = _piece(self.connector, "dependent connector")
        predicate = _piece(self.predicate, "dependent predicate")
        if connector not in {"after", "before", "while", "when"}:
            raise ValueError("unsupported dependent-event connector")
        object.__setattr__(self, "connector", connector.lower())
        object.__setattr__(self, "predicate", predicate)
        object.__setattr__(
            self,
            "object_text",
            _optional_piece(self.object_text, "dependent object_text", limit=240),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector": self.connector,
            "subject": self.subject.to_dict(),
            "predicate": self.predicate,
            "object_text": self.object_text,
            "recipient": self.recipient.to_dict() if self.recipient else None,
        }


@dataclass(frozen=True, slots=True)
class RealizationClause:
    clause_id: str
    frame: ClauseFrame
    subject: ParticipantRef
    predicate: str = ""
    object_text: str = ""
    recipient: ParticipantRef | None = None
    property_name: str = ""
    value: str = ""
    contrast: str = ""
    condition: str = ""
    dependent_event: DependentEvent | None = None
    certainty: Certainty = Certainty.CERTAIN
    negated: bool = False
    authority: str = "benchmark_fixture"
    source_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.frame, ClauseFrame):
            raise TypeError("clause frame must be a ClauseFrame")
        if not isinstance(self.subject, ParticipantRef):
            raise TypeError("clause subject must be a ParticipantRef")
        if self.recipient is not None and not isinstance(self.recipient, ParticipantRef):
            raise TypeError("clause recipient must be a ParticipantRef or None")
        if self.dependent_event is not None and not isinstance(
            self.dependent_event,
            DependentEvent,
        ):
            raise TypeError("dependent_event must be a DependentEvent or None")
        if not isinstance(self.certainty, Certainty):
            raise TypeError("clause certainty must be a Certainty")
        if not isinstance(self.negated, bool):
            raise TypeError("clause negated must be a bool")
        clause_id = _piece(self.clause_id, "clause_id", limit=160)
        object.__setattr__(self, "clause_id", clause_id)
        for field_name in (
            "predicate",
            "object_text",
            "property_name",
            "value",
            "contrast",
            "condition",
            "authority",
            "source_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_piece(
                    getattr(self, field_name),
                    f"clause {field_name}",
                    limit=240,
                ),
            )
        self._validate_frame()

    def _validate_frame(self) -> None:
        if not self.authority:
            raise ValueError("every realization clause requires authority")
        if self.frame == ClauseFrame.ATTRIBUTE:
            _require(self.predicate and self.value, "attribute requires predicate and value")
        elif self.frame == ClauseFrame.POSSESSIVE_FACT:
            _require(
                self.property_name and self.value,
                "possessive fact requires property_name and value",
            )
        elif self.frame == ClauseFrame.PREFERENCE:
            _require(
                self.subject.role == ParticipantRole.SELF
                and self.object_text
                and self.contrast,
                "preference requires SELF, object_text, and contrast",
            )
        elif self.frame == ClauseFrame.DISAGREEMENT:
            _require(
                self.subject.role == ParticipantRole.SELF and self.value,
                "disagreement requires SELF and a represented stance value",
            )
        elif self.frame == ClauseFrame.EVENT:
            _require(bool(self.predicate), "event requires a selected predicate")
        elif self.frame == ClauseFrame.CAPABILITY:
            _require(bool(self.predicate), "capability requires a selected action")
        elif self.frame == ClauseFrame.UNKNOWN:
            _require(
                self.subject.role == ParticipantRole.SELF
                and self.object_text
                and self.certainty == Certainty.UNKNOWN,
                "unknown requires SELF, a proposition, and UNKNOWN certainty",
            )
        elif self.frame == ClauseFrame.SUGGESTION:
            _require(bool(self.predicate), "suggestion requires a selected action")
        elif self.frame == ClauseFrame.RUNTIME_VALUE:
            _require(
                self.property_name and self.value,
                "runtime value requires property_name and value",
            )
        else:  # pragma: no cover - enum exhaustiveness guard
            raise ValueError(f"unsupported clause frame: {self.frame}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "clause_id": self.clause_id,
            "frame": self.frame.value,
            "subject": self.subject.to_dict(),
            "predicate": self.predicate,
            "object_text": self.object_text,
            "recipient": self.recipient.to_dict() if self.recipient else None,
            "property_name": self.property_name,
            "value": self.value,
            "contrast": self.contrast,
            "condition": self.condition,
            "dependent_event": (
                self.dependent_event.to_dict() if self.dependent_event else None
            ),
            "certainty": self.certainty.value,
            "negated": self.negated,
            "authority": self.authority,
            "source_id": self.source_id,
        }


@dataclass(frozen=True, slots=True)
class SemanticQuestion:
    kind: QuestionKind
    subject: ParticipantRef
    action: str
    alternatives: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, QuestionKind):
            raise TypeError("question kind must be a QuestionKind")
        if not isinstance(self.subject, ParticipantRef):
            raise TypeError("question subject must be a ParticipantRef")
        object.__setattr__(self, "action", _piece(self.action, "question action"))
        alternatives = _text_tuple(
            self.alternatives,
            "question alternatives",
            max_items=2,
            item_limit=160,
        )
        if self.kind == QuestionKind.ALTERNATIVE and len(alternatives) != 2:
            raise ValueError("alternative questions require exactly two alternatives")
        if self.kind != QuestionKind.ALTERNATIVE and alternatives:
            raise ValueError("only alternative questions accept alternatives")
        object.__setattr__(self, "alternatives", alternatives)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "subject": self.subject.to_dict(),
            "action": self.action,
            "alternatives": list(self.alternatives),
        }


@dataclass(frozen=True, slots=True)
class LocalRealizationPlan:
    plan_id: str
    dialogue_act: DialogueAct
    clauses: tuple[RealizationClause, ...] = ()
    response_form: ResponseForm = ResponseForm.STATEMENT
    max_sentences: int = 2
    max_words: int = 40
    tone: str = "restrained"
    familiarity: str = "familiar"
    disposition: str = "neutral"
    allow_acknowledgement: bool = False
    question: SemanticQuestion | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.dialogue_act, DialogueAct):
            raise TypeError("dialogue_act must be a DialogueAct")
        if not isinstance(self.response_form, ResponseForm):
            raise TypeError("response_form must be a ResponseForm")
        if isinstance(self.clauses, Mapping) or isinstance(
            self.clauses,
            (str, bytes, bytearray),
        ) or not isinstance(self.clauses, Sequence):
            raise TypeError("clauses must be a sequence of RealizationClause values")
        clauses = tuple(self.clauses)
        if any(not isinstance(item, RealizationClause) for item in clauses):
            raise TypeError("clauses must contain RealizationClause values")
        if not isinstance(self.max_sentences, int) or isinstance(self.max_sentences, bool):
            raise TypeError("max_sentences must be an integer")
        if not isinstance(self.max_words, int) or isinstance(self.max_words, bool):
            raise TypeError("max_words must be an integer")
        if not isinstance(self.allow_acknowledgement, bool):
            raise TypeError("allow_acknowledgement must be a bool")
        if self.question is not None and not isinstance(self.question, SemanticQuestion):
            raise TypeError("question must be a SemanticQuestion or None")
        object.__setattr__(self, "plan_id", _piece(self.plan_id, "plan_id", limit=160))
        if len({item.clause_id for item in clauses}) != len(clauses):
            raise ValueError("clause IDs must be unique")
        if not 1 <= self.max_sentences <= 3:
            raise ValueError("max_sentences must be between 1 and 3")
        if not 1 <= self.max_words <= 80:
            raise ValueError("max_words must be between 1 and 80")
        for field_name in ("tone", "familiarity", "disposition"):
            object.__setattr__(self, field_name, _piece(getattr(self, field_name), field_name))
        if self.response_form == ResponseForm.QUESTION and self.question is None:
            raise ValueError("question response form requires a semantic question")
        if self.question is not None and self.response_form != ResponseForm.QUESTION:
            raise ValueError("semantic questions require question response form")
        social_without_clauses = self.dialogue_act in {
            DialogueAct.GREET,
            DialogueAct.ACKNOWLEDGE,
            DialogueAct.THANKS_RESPONSE,
            DialogueAct.GOODBYE,
            DialogueAct.LAUGH,
            DialogueAct.REACT,
            DialogueAct.FOLLOW_UP,
        }
        if not clauses and not social_without_clauses:
            raise ValueError("non-social realization plans require semantic clauses")
        object.__setattr__(self, "clauses", clauses)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "dialogue_act": self.dialogue_act.value,
            "clauses": [item.to_dict() for item in self.clauses],
            "response_form": self.response_form.value,
            "max_sentences": self.max_sentences,
            "max_words": self.max_words,
            "tone": self.tone,
            "familiarity": self.familiarity,
            "disposition": self.disposition,
            "allow_acknowledgement": self.allow_acknowledgement,
            "question": self.question.to_dict() if self.question else None,
        }


@dataclass(frozen=True, slots=True)
class RealizationResult:
    text: str
    semantic_fingerprint: str
    candidate_id: str
    selected_components: tuple[str, ...]
    realized_clause_ids: tuple[str, ...]
    repetition_score: float
    generation_ms: float
    accepted: bool = True
    verifier_issues: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _piece(self.text, "result text", limit=2_000))
        fingerprint = _piece(
            self.semantic_fingerprint,
            "semantic fingerprint",
            limit=64,
        ).casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise ValueError("semantic fingerprint must be a SHA-256 hex digest")
        object.__setattr__(self, "semantic_fingerprint", fingerprint)
        object.__setattr__(
            self,
            "candidate_id",
            _piece(self.candidate_id, "candidate_id", limit=64),
        )
        object.__setattr__(
            self,
            "selected_components",
            _text_tuple(
                self.selected_components,
                "selected_components",
                max_items=24,
                item_limit=160,
            ),
        )
        object.__setattr__(
            self,
            "realized_clause_ids",
            _text_tuple(
                self.realized_clause_ids,
                "realized_clause_ids",
                max_items=3,
                item_limit=160,
            ),
        )
        object.__setattr__(
            self,
            "verifier_issues",
            _text_tuple(
                self.verifier_issues,
                "verifier_issues",
                max_items=12,
                item_limit=200,
            ),
        )
        if not isinstance(self.accepted, bool):
            raise TypeError("accepted must be a bool")
        object.__setattr__(
            self,
            "repetition_score",
            _bounded_real(
                self.repetition_score,
                "repetition_score",
                minimum=0.0,
                maximum=10_000.0,
            ),
        )
        object.__setattr__(
            self,
            "generation_ms",
            _bounded_real(
                self.generation_ms,
                "generation_ms",
                minimum=0.0,
                maximum=60_000.0,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "semantic_fingerprint": self.semantic_fingerprint,
            "candidate_id": self.candidate_id,
            "selected_components": list(self.selected_components),
            "realized_clause_ids": list(self.realized_clause_ids),
            "repetition_score": self.repetition_score,
            "generation_ms": self.generation_ms,
            "accepted": self.accepted,
            "verifier_issues": list(self.verifier_issues),
        }


class LocalRealizationError(ValueError):
    """Raised when the selected semantics cannot be safely rendered."""


class ProceduralLocalComposerV2:
    """Enumerate small safe constructions and select one deterministically."""

    def compose(
        self,
        plan: LocalRealizationPlan,
        *,
        seed: int,
        variation_ordinal: int = 0,
        recent_phrase_history: tuple[str, ...] = (),
    ) -> RealizationResult:
        if not isinstance(plan, LocalRealizationPlan):
            raise TypeError("plan must be a LocalRealizationPlan")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise TypeError("seed must be an integer")
        if not -(2**127) <= seed < 2**127:
            raise ValueError("seed must fit in a signed 128-bit integer")
        if not isinstance(variation_ordinal, int) or isinstance(variation_ordinal, bool):
            raise TypeError("variation_ordinal must be an integer")
        if not 0 <= variation_ordinal <= 1_000_000:
            raise ValueError("variation_ordinal must be between 0 and 1000000")
        history = _text_tuple(
            recent_phrase_history,
            "recent_phrase_history",
            max_items=8,
            item_limit=320,
        )
        started_ns = perf_counter_ns()
        fingerprint = _semantic_fingerprint(plan)
        candidates: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}

        for attempt in range(24):
            material = f"{fingerprint}|{int(seed)}|{int(variation_ordinal)}|{attempt}"
            local_seed = int.from_bytes(
                hashlib.sha256(material.encode("utf-8")).digest()[:8],
                "big",
                signed=False,
            )
            text, components, clause_ids = self._compose_once(plan, random.Random(local_seed))
            issues = _validate_realization(plan, text, clause_ids)
            if not issues:
                candidates.setdefault(text, (components, clause_ids))

        if not candidates:
            raise LocalRealizationError(
                "no bounded construction preserved the complete semantic plan"
            )

        ranked: list[tuple[float, str, str, tuple[str, ...], tuple[str, ...]]] = []
        for text, (components, clause_ids) in candidates.items():
            score = _repetition_score(text, history)
            tie_material = (
                f"{fingerprint}|{int(seed)}|{int(variation_ordinal)}|{text}"
            )
            tie = hashlib.sha256(tie_material.encode("utf-8")).hexdigest()
            ranked.append((score, tie, text, components, clause_ids))
        ranked.sort(key=lambda item: (item[0], item[1]))
        score, tie, text, components, clause_ids = ranked[0]
        elapsed_ms = round((perf_counter_ns() - started_ns) / 1_000_000.0, 4)
        return RealizationResult(
            text=text,
            semantic_fingerprint=fingerprint,
            candidate_id=tie[:16],
            selected_components=components,
            realized_clause_ids=clause_ids,
            repetition_score=round(score, 4),
            generation_ms=elapsed_ms,
        )

    def _compose_once(
        self,
        plan: LocalRealizationPlan,
        rng: random.Random,
    ) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
        components: list[str] = []
        clause_ids: list[str] = []

        if not plan.clauses:
            text, social_components = _render_social(plan, rng)
            return text, social_components, ()

        rendered_clauses: list[str] = []
        for clause in plan.clauses:
            rendered, component = _render_clause(clause, rng)
            rendered_clauses.append(rendered)
            components.append(component)
            clause_ids.append(clause.clause_id)

        if plan.allow_acknowledgement:
            acknowledgement = rng.choice(("Yeah", "Okay"))
            rendered_clauses[0] = f"{acknowledgement}, {rendered_clauses[0][0].lower()}{rendered_clauses[0][1:]}"
            components.append(f"ack:{acknowledgement.lower()}")

        force_separate_sentences = any(
            clause.frame == ClauseFrame.SUGGESTION for clause in plan.clauses
        ) and len(rendered_clauses) > 1
        if len(rendered_clauses) == 1:
            text = _terminal(rendered_clauses[0], question=False)
        elif len(rendered_clauses) <= plan.max_sentences and (
            force_separate_sentences or rng.randrange(2) == 0
        ):
            text = " ".join(_terminal(item, question=False) for item in rendered_clauses)
            components.append("join:sentences")
        else:
            joined = rendered_clauses[0]
            for item in rendered_clauses[1:]:
                joined += ", and " + _lower_subject(item)
            text = _terminal(joined, question=False)
            components.append("join:coordination")
        return text, tuple(components), tuple(clause_ids)


def _render_social(
    plan: LocalRealizationPlan,
    rng: random.Random,
) -> tuple[str, tuple[str, ...]]:
    act = plan.dialogue_act
    components: list[str] = []
    if act == DialogueAct.GREET:
        greeting = rng.choice(("Hey", "Hi", "Oh, hey"))
        components.append(f"greet:{greeting.lower()}")
        if plan.question:
            question, component = _render_question(plan.question, rng)
            components.append(component)
            return f"{_terminal(greeting, question=False)} {_terminal(question, question=True)}", tuple(components)
        return _terminal(greeting, question=False), tuple(components)
    if act == DialogueAct.ACKNOWLEDGE:
        acknowledgement = rng.choice(("Okay", "Got it", "Mmhm"))
        return _terminal(acknowledgement, question=False), (
            f"ack:{acknowledgement.lower()}",
        )
    if act == DialogueAct.THANKS_RESPONSE:
        response = rng.choice(("Of course", "No problem", "You're welcome"))
        return _terminal(response, question=False), (f"thanks:{response.lower()}",)
    if act == DialogueAct.GOODBYE:
        response = rng.choice(("Good night", "Okay, later", "See you soon"))
        return _terminal(response, question=False), (f"goodbye:{response.lower()}",)
    if act in {DialogueAct.LAUGH, DialogueAct.REACT}:
        if plan.disposition == "amused":
            opening = rng.choice(("Okay", "Wow", "Yeah"))
            reaction = rng.choice(("that was funny", "that got me", "that was good"))
            return _terminal(f"{opening}, {reaction}", question=False), (
                f"reaction-open:{opening.lower()}",
                f"reaction:{reaction}",
            )
        if plan.disposition == "milestone":
            response = rng.choice((
                "Finally. That's a W",
                "There it is. Nice",
                "Hell yeah. We got there",
                "Okayyy. I'll take that win",
                "Finally. That one can stop haunting us",
                "Yep. That's the good stuff",
            ))
            return _terminal(response, question=False), (f"milestone:{response.lower()}",)
        reaction = rng.choice(("Wow", "Okay", "Wild"))
        return _terminal(reaction, question=False), (f"reaction:{reaction.lower()}",)
    if act == DialogueAct.FOLLOW_UP and plan.question:
        question, component = _render_question(plan.question, rng)
        return _terminal(question, question=True), (component,)
    raise LocalRealizationError(f"unsupported social act: {act.value}")


def _render_question(
    question: SemanticQuestion,
    rng: random.Random,
) -> tuple[str, str]:
    subject = _subject(question.subject, capital=False)
    if question.kind == QuestionKind.INVITATION:
        if question.subject.role != ParticipantRole.ADDRESSEE:
            raise LocalRealizationError("invitation questions require the addressee")
        prefix = rng.choice(("Want to", "Do you want to"))
        return f"{prefix} {question.action}", f"question:{prefix.lower()}"
    if question.kind == QuestionKind.POLAR:
        return f"Did {subject} {question.action}", "question:polar"
    if question.kind == QuestionKind.ALTERNATIVE:
        first, second = question.alternatives
        return (
            f"Was {question.action} {first} or {second}",
            "question:alternative",
        )
    raise LocalRealizationError(f"unsupported question kind: {question.kind.value}")


def _render_clause(
    clause: RealizationClause,
    rng: random.Random,
) -> tuple[str, str]:
    subject = _subject(clause.subject, capital=True)
    if clause.frame == ClauseFrame.ATTRIBUTE:
        predicate = _conjugate_link(clause.predicate, clause.subject)
        variants = [(f"{subject} {predicate} {clause.value}", "clause:attribute")]
        if clause.predicate == "be":
            contraction = {
                ParticipantRole.SELF: "I'm",
                ParticipantRole.ADDRESSEE: "You're",
                ParticipantRole.JOINT: "We're",
                ParticipantRole.WORLD: "It's",
            }.get(clause.subject.role)
            if contraction:
                variants.append((
                    f"{contraction} {clause.value}",
                    "clause:attribute-contracted",
                ))
        elif clause.subject.role == ParticipantRole.SELF:
            variants.append((
                f"I do {clause.predicate} {clause.value}",
                "clause:attribute-emphatic",
            ))
        return rng.choice(variants)
    if clause.frame == ClauseFrame.POSSESSIVE_FACT:
        possessive = _possessive(clause.subject, capital=True)
        if rng.randrange(2) == 0:
            return (
                f"{possessive} {clause.property_name} is {clause.value}",
                "clause:possessive-forward",
            )
        return (
            f"{clause.value[0].upper()}{clause.value[1:]} is {possessive.lower()} {clause.property_name}",
            "clause:possessive-inverted",
        )
    if clause.frame == ClauseFrame.PREFERENCE:
        if rng.randrange(2) == 0:
            return (
                f"I prefer {clause.object_text} to {clause.contrast}",
                "clause:preference-prefer",
            )
        return (
            f"I'd choose {clause.object_text} over {clause.contrast}",
            "clause:preference-choose",
        )
    if clause.frame == ClauseFrame.DISAGREEMENT:
        separator = rng.choice((": ", " - "))
        return f"I disagree{separator}{clause.value}", "clause:disagreement"
    if clause.frame == ClauseFrame.UNKNOWN:
        prefix = rng.choice(("I don't know whether", "I do not know whether"))
        return f"{prefix} {clause.object_text}", "clause:unknown"
    if clause.frame == ClauseFrame.EVENT:
        parts = [subject, clause.predicate]
        if clause.recipient is not None:
            parts.append(_object_pronoun(clause.recipient))
        if clause.object_text:
            parts.append(clause.object_text)
        text = " ".join(parts)
        if clause.dependent_event:
            dependent = clause.dependent_event
            dependent_parts = [
                dependent.connector,
                _subject(dependent.subject, capital=False),
                dependent.predicate,
            ]
            if dependent.recipient is not None:
                dependent_parts.append(_object_pronoun(dependent.recipient))
            if dependent.object_text:
                dependent_parts.append(dependent.object_text)
            text += " " + " ".join(dependent_parts)
        return text, "clause:event"
    if clause.frame == ClauseFrame.CAPABILITY:
        if clause.negated:
            modal = rng.choice(("can't", "cannot"))
        else:
            modal = "can"
        text = f"{subject} {modal} {clause.predicate}"
        if clause.condition:
            text += f" {clause.condition}"
        return text, f"clause:capability-{modal.replace(chr(39), '')}"
    if clause.frame == ClauseFrame.SUGGESTION:
        prefix = rng.choice(("", "Please "))
        text = prefix + clause.predicate
        if clause.object_text:
            text += " " + clause.object_text
        return text[0].upper() + text[1:], "clause:suggestion"
    if clause.frame == ClauseFrame.RUNTIME_VALUE:
        return (
            f"{subject} {clause.property_name} is {clause.value}",
            "clause:runtime-value",
        )
    raise LocalRealizationError(f"unsupported clause frame: {clause.frame.value}")


def _subject(participant: ParticipantRef, *, capital: bool) -> str:
    values = {
        ParticipantRole.SELF: "I",
        ParticipantRole.ADDRESSEE: "you",
        ParticipantRole.JOINT: "we",
        ParticipantRole.WORLD: "it",
    }
    value = participant.surface if participant.role == ParticipantRole.NAMED_ENTITY else values[participant.role]
    if capital and value != "I":
        value = value[0].upper() + value[1:]
    return value


def _object_pronoun(participant: ParticipantRef) -> str:
    values = {
        ParticipantRole.SELF: "me",
        ParticipantRole.ADDRESSEE: "you",
        ParticipantRole.JOINT: "us",
        ParticipantRole.WORLD: "it",
    }
    return participant.surface if participant.role == ParticipantRole.NAMED_ENTITY else values[participant.role]


def _possessive(participant: ParticipantRef, *, capital: bool) -> str:
    values = {
        ParticipantRole.SELF: "my",
        ParticipantRole.ADDRESSEE: "your",
        ParticipantRole.JOINT: "our",
        ParticipantRole.WORLD: "its",
    }
    if participant.role == ParticipantRole.NAMED_ENTITY:
        value = f"{participant.surface}'s"
    else:
        value = values[participant.role]
    return value[0].upper() + value[1:] if capital else value


def _conjugate_link(predicate: str, subject: ParticipantRef) -> str:
    if predicate == "be":
        if subject.role == ParticipantRole.SELF:
            return "am"
        if subject.role in {ParticipantRole.ADDRESSEE, ParticipantRole.JOINT}:
            return "are"
        return "is"
    if subject.role in {ParticipantRole.WORLD, ParticipantRole.NAMED_ENTITY} and predicate == "sound":
        return "sounds"
    return predicate


def _terminal(text: str, *, question: bool) -> str:
    value = text.strip().rstrip(".!?")
    return value + ("?" if question else ".")


def _lower_subject(text: str) -> str:
    if text.startswith("I "):
        return text
    return text[0].lower() + text[1:]


def _sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?]+(?=\s|$)", text.strip()))


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text))


def _validate_realization(
    plan: LocalRealizationPlan,
    text: str,
    realized_clause_ids: tuple[str, ...],
) -> tuple[str, ...]:
    issues: list[str] = []
    expected_ids = tuple(item.clause_id for item in plan.clauses)
    if realized_clause_ids != expected_ids:
        issues.append("not every selected semantic clause was consumed exactly once")
    sentence_count = _sentence_count(text)
    if sentence_count < 1 or sentence_count > plan.max_sentences:
        issues.append("sentence ceiling violated")
    if _word_count(text) > plan.max_words:
        issues.append("word ceiling violated")
    question_count = text.count("?")
    if plan.response_form == ResponseForm.QUESTION and question_count != 1:
        issues.append("question form violated")
    if plan.response_form != ResponseForm.QUESTION and question_count:
        issues.append("statement/reaction gained a question")
    if re.search(r"\b(?:the user|the creator|the assistant|Mary (?:said|thinks|feels))\b", text, re.I):
        issues.append("planner or third-person identity language appeared")
    return tuple(issues)


def _semantic_fingerprint(plan: LocalRealizationPlan) -> str:
    serialized = json.dumps(
        plan.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _opening(text: str, words: int = 3) -> str:
    return " ".join(re.findall(r"\b[\w']+\b", text.casefold())[:words])


def _trigrams(text: str) -> set[tuple[str, str, str]]:
    words = re.findall(r"\b[\w']+\b", text.casefold())
    return set(zip(words, words[1:], words[2:]))


def _repetition_score(text: str, history: tuple[str, ...]) -> float:
    normalized = " ".join(text.casefold().split())
    opening = _opening(text)
    trigrams = _trigrams(text)
    score = 0.0
    for recent in history[-8:]:
        recent_normalized = " ".join(recent.casefold().split())
        if normalized == recent_normalized:
            score += 100.0
        if opening and opening == _opening(recent):
            score += 20.0
        recent_trigrams = _trigrams(recent)
        if trigrams and recent_trigrams:
            score += 4.0 * (len(trigrams & recent_trigrams) / len(trigrams | recent_trigrams))
    return score


_UNSAFE_TEXT_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})


def _piece(value: Any, label: str, *, limit: int = 240) -> str:
    text = _optional_piece(value, label, limit=limit)
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _optional_piece(
    value: Any,
    label: str = "text",
    *,
    limit: int = 240,
) -> str:
    if value is None:
        return ""
    if isinstance(value, Mapping):
        raise TypeError(f"{label} must be scalar text, not a mapping")
    if isinstance(value, Sequence) and not isinstance(value, str):
        raise TypeError(f"{label} must be scalar text, not a sequence")
    if isinstance(value, (bytes, bytearray)) or not isinstance(value, str):
        raise TypeError(f"{label} must be scalar text")
    if any(
        unicodedata.category(character) in _UNSAFE_TEXT_CATEGORIES
        for character in value
    ):
        raise ValueError(f"{label} must not contain control or formatting characters")
    text = " ".join(value.split()).strip()
    if len(text) > limit:
        raise ValueError(f"{label} exceeds {limit} characters")
    return text


def _text_tuple(
    value: Any,
    label: str,
    *,
    max_items: int,
    item_limit: int,
) -> tuple[str, ...]:
    if isinstance(value, Mapping) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{label} must be a sequence of strings")
    if not isinstance(value, Sequence):
        raise TypeError(f"{label} must be a sequence of strings")
    items = tuple(
        _piece(item, f"{label} item", limit=item_limit)
        for item in value
    )
    if len(items) > max_items:
        raise ValueError(f"{label} may contain at most {max_items} items")
    return items


def _bounded_real(
    value: Any,
    label: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{label} must be a real numeric scalar")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)
