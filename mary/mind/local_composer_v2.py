"""Typed procedural dialogue renderer used only by hybrid shadow benchmarks.

The production :class:`mary.mind.local_composer.LocalResponseComposer` is not
replaced or imported here.  V2 consumes an immutable, already-authorized
semantic plan with explicit participant roles.  It never parses reservoir
prose, retrieves state, calls a model, or writes phrase history.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import random
import re
from time import perf_counter_ns
from typing import Any

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
        if self.role == ParticipantRole.NAMED_ENTITY:
            entity_id = " ".join(str(self.entity_id or "").split()).strip()
            surface = " ".join(str(self.surface or "").split()).strip()
            if not entity_id or not surface:
                raise ValueError("named participants require entity_id and surface")
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
        connector = _piece(self.connector, "dependent connector")
        predicate = _piece(self.predicate, "dependent predicate")
        if connector not in {"after", "before", "while", "when"}:
            raise ValueError("unsupported dependent-event connector")
        object.__setattr__(self, "connector", connector.lower())
        object.__setattr__(self, "predicate", predicate)
        object.__setattr__(self, "object_text", _optional_piece(self.object_text))

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
        clause_id = _piece(self.clause_id, "clause_id")
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
            object.__setattr__(self, field_name, _optional_piece(getattr(self, field_name)))
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
        object.__setattr__(self, "action", _piece(self.action, "question action"))
        alternatives = tuple(_piece(item, "question alternative") for item in self.alternatives)
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
        object.__setattr__(self, "plan_id", _piece(self.plan_id, "plan_id"))
        clauses = tuple(self.clauses)
        if len({item.clause_id for item in clauses}) != len(clauses):
            raise ValueError("clause IDs must be unique")
        if not 1 <= int(self.max_sentences) <= 3:
            raise ValueError("max_sentences must be between 1 and 3")
        if not 1 <= int(self.max_words) <= 80:
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
        history = tuple(_optional_piece(item) for item in recent_phrase_history if str(item).strip())
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
        return f"{subject} {predicate} {clause.value}", "clause:attribute"
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


def _piece(value: Any, label: str) -> str:
    text = _optional_piece(value)
    if not text:
        raise ValueError(f"{label} is required")
    if "\n" in str(value) or "\r" in str(value):
        raise ValueError(f"{label} must be one line")
    return text


def _optional_piece(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)
