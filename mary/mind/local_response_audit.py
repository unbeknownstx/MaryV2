"""Independent deterministic audit for production-local response wording.

The procedural composer is deliberately not its own final authority.  This
module rechecks its immutable input contract and rendered output for semantic
coverage, speaker ownership, response form, provenance, and capability drift.
It performs no retrieval, persistence, provider selection, or model calls.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import product
import json
import re
from typing import Any

from .dialogue_acts import DialogueAct
from .local_composer_v2 import (
    ClauseFrame,
    ParticipantRef,
    ParticipantRole,
    QuestionKind,
    RealizationClause,
    RealizationResult,
    ResponseForm,
)
from .verbalization_plan import CanonicalResponsePlan


@dataclass(frozen=True, slots=True)
class LocalResponseAudit:
    """Bounded result of the post-composition production safety audit."""

    accepted: bool
    issues: tuple[str, ...]
    semantic_ok: bool
    ownership_ok: bool
    form_ok: bool
    provenance_ok: bool
    capability_ok: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "issues": list(self.issues),
            "semantic_ok": self.semantic_ok,
            "ownership_ok": self.ownership_ok,
            "form_ok": self.form_ok,
            "provenance_ok": self.provenance_ok,
            "capability_ok": self.capability_ok,
        }


def audit_local_response(
    plan: CanonicalResponsePlan,
    result: RealizationResult,
) -> LocalResponseAudit:
    """Revalidate one candidate without trusting composer acceptance flags."""

    if not isinstance(plan, CanonicalResponsePlan):
        raise TypeError("plan must be a CanonicalResponsePlan")
    if not isinstance(result, RealizationResult):
        raise TypeError("result must be a RealizationResult")

    semantic: list[str] = []
    ownership: list[str] = []
    form: list[str] = []
    provenance: list[str] = []
    capability: list[str] = []
    text = " ".join(str(result.text or "").split()).strip()
    folded = text.casefold()
    realization = plan.realization

    if not text:
        form.append("empty_response")
    elif text not in _authorized_realizations(plan):
        semantic.append("unauthorized_surface_realization")
    if not result.accepted or result.verifier_issues:
        semantic.append("composer_verifier_rejected")

    expected_fingerprint = _semantic_fingerprint(realization.to_dict())
    if result.semantic_fingerprint != expected_fingerprint:
        semantic.append("semantic_fingerprint_mismatch")

    expected_clause_ids = tuple(clause.clause_id for clause in realization.clauses)
    if tuple(result.realized_clause_ids) != expected_clause_ids:
        semantic.append("semantic_clause_coverage_mismatch")

    for clause in realization.clauses:
        _audit_clause_semantics(clause, folded, semantic)
        _audit_ownership(clause, folded, ownership)

    _audit_social_semantics(plan, folded, semantic, ownership)
    _audit_form(plan, text, form)
    _audit_provenance(plan, provenance)
    _audit_capability(plan, folded, capability)

    issues = tuple(dict.fromkeys(
        semantic + ownership + form + provenance + capability
    ))
    return LocalResponseAudit(
        accepted=not issues,
        issues=issues,
        semantic_ok=not semantic,
        ownership_ok=not ownership,
        form_ok=not form,
        provenance_ok=not provenance,
        capability_ok=not capability,
    )


def _audit_clause_semantics(
    clause: RealizationClause,
    text: str,
    issues: list[str],
) -> None:
    required: list[str] = []
    if clause.frame == ClauseFrame.ATTRIBUTE:
        if clause.predicate != "be":
            required.append(clause.predicate)
        required.append(clause.value)
    elif clause.frame == ClauseFrame.POSSESSIVE_FACT:
        required.extend((clause.property_name, clause.value))
    elif clause.frame == ClauseFrame.PREFERENCE:
        required.extend((clause.object_text, clause.contrast))
    elif clause.frame == ClauseFrame.DISAGREEMENT:
        required.append(clause.value)
    elif clause.frame == ClauseFrame.UNKNOWN:
        required.append(clause.object_text)
        if not re.search(r"\bi (?:do not|don't) know whether\b", text):
            issues.append("unknown_certainty_not_preserved")
    elif clause.frame == ClauseFrame.EVENT:
        required.append(clause.predicate)
        if clause.object_text:
            required.append(clause.object_text)
        if clause.dependent_event is not None:
            required.extend((
                clause.dependent_event.connector,
                clause.dependent_event.predicate,
            ))
            if clause.dependent_event.object_text:
                required.append(clause.dependent_event.object_text)
    elif clause.frame == ClauseFrame.CAPABILITY:
        required.append(clause.predicate)
        if clause.condition:
            required.append(clause.condition)
        expected = r"\b(?:can't|cannot)\b" if clause.negated else r"\bcan\b"
        if not re.search(expected, text):
            issues.append("capability_polarity_not_preserved")
    elif clause.frame == ClauseFrame.SUGGESTION:
        required.append(clause.predicate)
        if clause.object_text:
            required.append(clause.object_text)
    elif clause.frame == ClauseFrame.RUNTIME_VALUE:
        required.extend((clause.property_name, clause.value))

    for scalar in required:
        if _fold(scalar) not in text:
            issues.append("selected_semantic_scalar_missing")


def _audit_ownership(
    clause: RealizationClause,
    text: str,
    issues: list[str],
) -> None:
    subject = clause.subject
    if clause.frame == ClauseFrame.POSSESSIVE_FACT:
        marker = _possessive_marker(subject)
        if not _contains_marker(text, marker):
            issues.append("possessive_ownership_mismatch")
        if subject.role == ParticipantRole.ADDRESSEE and re.search(r"\bmy\b", text):
            issues.append("addressee_fact_claimed_as_mary_owned")
        if subject.role == ParticipantRole.SELF and re.search(r"\byour\b", text):
            issues.append("mary_fact_claimed_as_addressee_owned")
        return

    marker = _subject_marker(subject)
    if not _contains_marker(text, marker):
        issues.append("subject_ownership_mismatch")


def _audit_social_semantics(
    plan: CanonicalResponsePlan,
    text: str,
    semantic: list[str],
    ownership: list[str],
) -> None:
    if plan.realization.clauses:
        return
    act = plan.dialogue_act
    patterns = {
        DialogueAct.GREET: r"^(?:hey|hi|oh, hey)\b",
        DialogueAct.ACKNOWLEDGE: r"^(?:okay|got it|mmhm)\b",
        DialogueAct.THANKS_RESPONSE: r"^(?:of course|no problem|you're welcome)\b",
        DialogueAct.GOODBYE: r"^(?:good night|okay, later|see you soon)\b",
        DialogueAct.LAUGH: r"^(?:okay|wow|yeah), (?:that was funny|that got me|that was good)\b",
        DialogueAct.REACT: (
            r"^(?:finally|there it is|hell yeah|okayyy|yep)\b"
            if plan.realization.disposition == "milestone"
            else r"^(?:wow|okay|wild)\b"
        ),
    }
    pattern = patterns.get(act)
    if pattern is not None and not re.search(pattern, text):
        semantic.append("social_act_semantics_mismatch")
    if act == DialogueAct.FOLLOW_UP:
        question = plan.realization.question
        if question is None or _fold(question.action) not in text:
            semantic.append("follow_up_semantics_missing")
        if not re.search(r"\b(?:you|want to)\b", text):
            ownership.append("follow_up_addressee_missing")
    if act == DialogueAct.GREET and plan.realization.question is not None:
        if _fold(plan.realization.question.action) not in text:
            semantic.append("greeting_invitation_missing")


def _audit_form(
    plan: CanonicalResponsePlan,
    text: str,
    issues: list[str],
) -> None:
    target = plan.verbalization.form_target
    sentence_count = len(re.findall(r"[.!?]+(?=\s|$)", text))
    word_count = len(re.findall(r"\b[\w']+\b", text))
    question_count = text.count("?")
    if not target.sentence_min <= sentence_count <= target.sentence_max:
        issues.append("sentence_budget_violated")
    if word_count > target.max_words:
        issues.append("word_budget_violated")
    if target.exact_question_count is not None and question_count != target.exact_question_count:
        issues.append("question_count_violated")
    if target.terminal_punctuation is not None and not text.endswith(
        target.terminal_punctuation
    ):
        issues.append("terminal_punctuation_violated")
    expected_form = plan.realization.response_form
    if expected_form == ResponseForm.QUESTION and question_count != 1:
        issues.append("question_form_violated")
    if expected_form != ResponseForm.QUESTION and question_count:
        issues.append("non_question_gained_question")


def _audit_provenance(
    plan: CanonicalResponsePlan,
    issues: list[str],
) -> None:
    facts = {fact.fact_id: fact for fact in plan.verbalization.grounded_facts}
    consumed: set[str] = set()
    for clause in plan.realization.clauses:
        fact = facts.get(clause.source_id)
        if fact is None:
            issues.append("clause_source_missing")
            continue
        consumed.add(clause.source_id)
        if fact.authority != clause.authority:
            issues.append("clause_authority_mismatch")
    if consumed != set(facts):
        issues.append("grounded_fact_not_consumed")


def _audit_capability(
    plan: CanonicalResponsePlan,
    text: str,
    issues: list[str],
) -> None:
    if re.search(
        r"\b(?:the assistant|language model|planner|system prompt|source id|"
        r"authority|provenance|benchmark fixture)\b",
        text,
    ):
        issues.append("planner_or_provenance_language_leaked")
    if re.search(r"\bmary (?:is|am|likes?|dislikes?|thinks?|feels?|knows?|can)\b", text):
        issues.append("mary_third_person_leakage")

    supports_capability = any(
        clause.frame == ClauseFrame.CAPABILITY
        for clause in plan.realization.clauses
    )
    if not supports_capability and re.search(
        r"\bi (?:can|can't|cannot|remember|know|promised|decided)\b",
        text,
    ):
        issues.append("unsupported_first_person_capability_claim")


def _semantic_fingerprint(payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _authorized_realizations(plan: CanonicalResponsePlan) -> frozenset[str]:
    """Independently enumerate the exact finite grammar authorized by a plan."""

    realization = plan.realization
    if not realization.clauses:
        return frozenset(_authorized_social(realization))

    clause_options = tuple(
        _authorized_clause_surfaces(clause)
        for clause in realization.clauses
    )
    outputs: set[str] = set()
    for selected in product(*clause_options):
        rendered_variants: tuple[tuple[str, ...], ...]
        if realization.allow_acknowledgement:
            rendered_variants = tuple(
                (
                    f"{ack}, {selected[0][0].lower()}{selected[0][1:]}",
                    *selected[1:],
                )
                for ack in ("Yeah", "Okay")
            )
        else:
            rendered_variants = (selected,)
        for rendered in rendered_variants:
            force_sentences = any(
                clause.frame == ClauseFrame.SUGGESTION
                for clause in realization.clauses
            ) and len(rendered) > 1
            if len(rendered) == 1:
                outputs.add(_terminal(rendered[0], question=False))
                continue
            if len(rendered) <= realization.max_sentences:
                outputs.add(" ".join(
                    _terminal(item, question=False)
                    for item in rendered
                ))
                if force_sentences:
                    continue
            joined = rendered[0]
            for item in rendered[1:]:
                joined += ", and " + (
                    item if item.startswith("I ") else item[0].lower() + item[1:]
                )
            outputs.add(_terminal(joined, question=False))
    return frozenset(outputs)


def _authorized_social(realization: Any) -> set[str]:
    act = realization.dialogue_act
    if act == DialogueAct.GREET:
        greetings = ("Hey", "Hi", "Oh, hey")
        if realization.question is None:
            return {_terminal(item, question=False) for item in greetings}
        questions = _authorized_questions(realization.question)
        return {
            f"{_terminal(greeting, question=False)} {_terminal(question, question=True)}"
            for greeting in greetings
            for question in questions
        }
    if act == DialogueAct.ACKNOWLEDGE:
        return {_terminal(item, question=False) for item in ("Okay", "Got it", "Mmhm")}
    if act == DialogueAct.THANKS_RESPONSE:
        return {
            _terminal(item, question=False)
            for item in ("Of course", "No problem", "You're welcome")
        }
    if act == DialogueAct.GOODBYE:
        return {
            _terminal(item, question=False)
            for item in ("Good night", "Okay, later", "See you soon")
        }
    if act in {DialogueAct.LAUGH, DialogueAct.REACT}:
        if realization.disposition == "amused":
            return {
                _terminal(f"{opening}, {reaction}", question=False)
                for opening in ("Okay", "Wow", "Yeah")
                for reaction in ("that was funny", "that got me", "that was good")
            }
        if realization.disposition == "milestone":
            return {
                _terminal(item, question=False)
                for item in (
                    "Finally. That's a W",
                    "There it is. Nice",
                    "Hell yeah. We got there",
                    "Okayyy. I'll take that win",
                    "Finally. That one can stop haunting us",
                    "Yep. That's the good stuff",
                )
            }
        return {_terminal(item, question=False) for item in ("Wow", "Okay", "Wild")}
    if act == DialogueAct.FOLLOW_UP and realization.question is not None:
        return {
            _terminal(item, question=True)
            for item in _authorized_questions(realization.question)
        }
    return set()


def _authorized_questions(question: Any) -> tuple[str, ...]:
    subject = _surface_subject(question.subject, capital=False)
    if question.kind == QuestionKind.INVITATION:
        return (
            f"Want to {question.action}",
            f"Do you want to {question.action}",
        )
    if question.kind == QuestionKind.POLAR:
        return (f"Did {subject} {question.action}",)
    if question.kind == QuestionKind.ALTERNATIVE:
        first, second = question.alternatives
        return (f"Was {question.action} {first} or {second}",)
    return ()


def _authorized_clause_surfaces(clause: RealizationClause) -> tuple[str, ...]:
    subject = _surface_subject(clause.subject, capital=True)
    if clause.frame == ClauseFrame.ATTRIBUTE:
        linked = _surface_link(clause.predicate, clause.subject)
        variants = [f"{subject} {linked} {clause.value}"]
        if clause.predicate == "be":
            contraction = {
                ParticipantRole.SELF: "I'm",
                ParticipantRole.ADDRESSEE: "You're",
                ParticipantRole.JOINT: "We're",
                ParticipantRole.WORLD: "It's",
            }.get(clause.subject.role)
            if contraction:
                variants.append(f"{contraction} {clause.value}")
        elif clause.subject.role == ParticipantRole.SELF:
            variants.append(f"I do {clause.predicate} {clause.value}")
        return tuple(variants)
    if clause.frame == ClauseFrame.POSSESSIVE_FACT:
        possessive = _surface_possessive(clause.subject, capital=True)
        return (
            f"{possessive} {clause.property_name} is {clause.value}",
            f"{clause.value[0].upper()}{clause.value[1:]} is {possessive.lower()} {clause.property_name}",
        )
    if clause.frame == ClauseFrame.PREFERENCE:
        return (
            f"I prefer {clause.object_text} to {clause.contrast}",
            f"I'd choose {clause.object_text} over {clause.contrast}",
        )
    if clause.frame == ClauseFrame.DISAGREEMENT:
        return (f"I disagree: {clause.value}", f"I disagree - {clause.value}")
    if clause.frame == ClauseFrame.UNKNOWN:
        return (
            f"I don't know whether {clause.object_text}",
            f"I do not know whether {clause.object_text}",
        )
    if clause.frame == ClauseFrame.EVENT:
        parts = [subject, clause.predicate]
        if clause.recipient is not None:
            parts.append(_surface_object(clause.recipient))
        if clause.object_text:
            parts.append(clause.object_text)
        text = " ".join(parts)
        if clause.dependent_event is not None:
            dependent = clause.dependent_event
            dependent_parts = [
                dependent.connector,
                _surface_subject(dependent.subject, capital=False),
                dependent.predicate,
            ]
            if dependent.recipient is not None:
                dependent_parts.append(_surface_object(dependent.recipient))
            if dependent.object_text:
                dependent_parts.append(dependent.object_text)
            text += " " + " ".join(dependent_parts)
        return (text,)
    if clause.frame == ClauseFrame.CAPABILITY:
        modals = ("can't", "cannot") if clause.negated else ("can",)
        return tuple(
            f"{subject} {modal} {clause.predicate}"
            + (f" {clause.condition}" if clause.condition else "")
            for modal in modals
        )
    if clause.frame == ClauseFrame.SUGGESTION:
        body = clause.predicate + (
            f" {clause.object_text}" if clause.object_text else ""
        )
        return (
            body[0].upper() + body[1:],
            f"Please {body}",
        )
    if clause.frame == ClauseFrame.RUNTIME_VALUE:
        return (f"{subject} {clause.property_name} is {clause.value}",)
    return ()


def _surface_subject(participant: ParticipantRef, *, capital: bool) -> str:
    value = (
        participant.surface
        if participant.role == ParticipantRole.NAMED_ENTITY
        else {
            ParticipantRole.SELF: "I",
            ParticipantRole.ADDRESSEE: "you",
            ParticipantRole.JOINT: "we",
            ParticipantRole.WORLD: "it",
        }[participant.role]
    )
    assert value is not None
    return value[0].upper() + value[1:] if capital and value != "I" else value


def _surface_object(participant: ParticipantRef) -> str:
    if participant.role == ParticipantRole.NAMED_ENTITY:
        return str(participant.surface)
    return {
        ParticipantRole.SELF: "me",
        ParticipantRole.ADDRESSEE: "you",
        ParticipantRole.JOINT: "us",
        ParticipantRole.WORLD: "it",
    }[participant.role]


def _surface_possessive(participant: ParticipantRef, *, capital: bool) -> str:
    value = (
        f"{participant.surface}'s"
        if participant.role == ParticipantRole.NAMED_ENTITY
        else {
            ParticipantRole.SELF: "my",
            ParticipantRole.ADDRESSEE: "your",
            ParticipantRole.JOINT: "our",
            ParticipantRole.WORLD: "its",
        }[participant.role]
    )
    return value[0].upper() + value[1:] if capital else value


def _surface_link(predicate: str, participant: ParticipantRef) -> str:
    if predicate == "be":
        if participant.role == ParticipantRole.SELF:
            return "am"
        if participant.role in {ParticipantRole.ADDRESSEE, ParticipantRole.JOINT}:
            return "are"
        return "is"
    if participant.role in {ParticipantRole.WORLD, ParticipantRole.NAMED_ENTITY} and predicate == "sound":
        return "sounds"
    return predicate


def _terminal(text: str, *, question: bool) -> str:
    return text.strip().rstrip(".!?") + ("?" if question else ".")


def _fold(value: str) -> str:
    return " ".join(str(value).casefold().split()).strip()


def _subject_marker(participant: ParticipantRef) -> str:
    return {
        ParticipantRole.SELF: "i",
        ParticipantRole.ADDRESSEE: "you",
        ParticipantRole.JOINT: "we",
        ParticipantRole.WORLD: "it",
        ParticipantRole.NAMED_ENTITY: _fold(participant.surface or ""),
    }[participant.role]


def _possessive_marker(participant: ParticipantRef) -> str:
    return {
        ParticipantRole.SELF: "my",
        ParticipantRole.ADDRESSEE: "your",
        ParticipantRole.JOINT: "our",
        ParticipantRole.WORLD: "its",
        ParticipantRole.NAMED_ENTITY: _fold(f"{participant.surface}'s"),
    }[participant.role]


def _contains_marker(text: str, marker: str) -> bool:
    if not marker:
        return False
    return re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", text) is not None
