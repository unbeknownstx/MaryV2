"""Strict benchmark-only semantic surface realizer contract for MaryV2.

Mary's local systems have already selected every semantic unit represented in
this module.  The V3 model-facing payload contains neither the source turn nor
planner, identity, provenance, relationship, or authority labels.  Ollama
output remains an untrusted developer artifact: this module can verify and
mechanically clean surface formatting, but it cannot write authoritative state
or make a production routing decision.

This module deliberately contains no Ollama runner.  The existing Micro-Cortex
benchmark owns transport/runtime measurement and can import this isolated V3
case suite, renderer, verifier, and summary layer.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from statistics import median
from time import perf_counter_ns
from typing import Any

from mary.cognition.continuity import ConversationalDrive
from mary.mind.dialogue_acts import DialogueAct
from mary.mind.verbalization_plan import (
    CompactVerbalizationPlan,
    SemanticSurfaceContract,
    project_semantic_surface_contract,
)
from scripts.benchmark_qwen_micro_cortex import (
    _fact,
    _make_case,
    _stance,
    fixed_cases,
)


SYSTEM_PROMPT_V3 = """/no_think
Turn every REQUIRED meaning into one natural spoken reply.
Return only the reply. Preserve every meaning and obey the form and limits.
Add no fact, reason, motive, entity, personal claim, or task commentary."""


@dataclass(frozen=True, slots=True)
class SurfaceSemanticUnit:
    """Evaluator-only evidence for one already-selected semantic atom."""

    label: str
    patterns: tuple[str, ...]

    def __post_init__(self) -> None:
        label = " ".join(str(self.label).split()).strip()
        patterns = tuple(str(item) for item in self.patterns)
        if not label:
            raise ValueError("surface semantic-unit label is required")
        if not patterns or any(not item for item in patterns):
            raise ValueError("surface semantic units require at least one pattern")
        for pattern in patterns:
            re.compile(pattern, flags=re.I | re.S)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "patterns", patterns)


@dataclass(frozen=True, slots=True)
class SurfaceRealizerCase:
    """One immutable V3 case with a hard model/evaluator separation."""

    plan: CompactVerbalizationPlan
    surface_contract: SemanticSurfaceContract
    semantic_units: tuple[SurfaceSemanticUnit, ...]
    stance_unit_labels: tuple[str, ...] = ()
    contradiction_patterns: tuple[tuple[str, str], ...] = ()
    stance_contradiction_patterns: tuple[tuple[str, str], ...] = ()
    boundary_patterns: tuple[tuple[str, str], ...] = ()
    allowed_entities: tuple[str, ...] = ()
    allowed_numbers: tuple[str, ...] = ()
    allowed_first_person_claim_patterns: tuple[str, ...] = ()
    allow_causal_language: bool = False
    human_review_focus: str = (
        "Compare semantic fidelity, reference frame, and ordinary wording."
    )

    def __post_init__(self) -> None:
        if not isinstance(self.plan, CompactVerbalizationPlan):
            raise TypeError("surface case plan must be a CompactVerbalizationPlan")
        if not isinstance(self.surface_contract, SemanticSurfaceContract):
            raise TypeError("surface_contract must be a SemanticSurfaceContract")
        if self.surface_contract.source_plan_id != self.plan.plan_id:
            raise ValueError("surface contract must project from the same source plan")
        units = tuple(self.semantic_units)
        if not units or any(not isinstance(item, SurfaceSemanticUnit) for item in units):
            raise TypeError("semantic_units must contain SurfaceSemanticUnit values")
        labels = tuple(item.label for item in units)
        if len(set(labels)) != len(labels):
            raise ValueError("surface semantic-unit labels must be unique")
        stance_labels = tuple(self.stance_unit_labels)
        unknown_stance = sorted(set(stance_labels) - set(labels))
        if unknown_stance:
            raise ValueError(f"unknown stance semantic-unit labels: {unknown_stance}")
        for specs in (
            self.contradiction_patterns,
            self.stance_contradiction_patterns,
            self.boundary_patterns,
        ):
            for label, pattern in specs:
                if not str(label).strip() or not str(pattern):
                    raise ValueError("boundary controls require labels and patterns")
                re.compile(str(pattern), flags=re.I | re.S)
        for pattern in self.allowed_first_person_claim_patterns:
            re.compile(str(pattern), flags=re.I | re.S)
        entities = tuple(" ".join(str(item).split()).strip() for item in self.allowed_entities)
        numbers = tuple(str(item).strip() for item in self.allowed_numbers)
        if any(not item for item in entities) or len(set(entities)) != len(entities):
            raise ValueError("allowed_entities must be nonempty and unique")
        if any(not item for item in numbers) or len(set(numbers)) != len(numbers):
            raise ValueError("allowed_numbers must be nonempty and unique")
        focus = " ".join(str(self.human_review_focus).split()).strip()
        if not focus:
            raise ValueError("human_review_focus is required")
        if not isinstance(self.allow_causal_language, bool):
            raise TypeError("allow_causal_language must be a bool")
        object.__setattr__(self, "semantic_units", units)
        object.__setattr__(self, "stance_unit_labels", stance_labels)
        object.__setattr__(self, "allowed_entities", entities)
        object.__setattr__(self, "allowed_numbers", numbers)
        object.__setattr__(self, "human_review_focus", focus)

    def evaluator_dict(self) -> dict[str, Any]:
        """Return auditable evaluator metadata that is never model-visible."""

        return {
            "semantic_units": [
                {"label": item.label, "patterns": list(item.patterns)}
                for item in self.semantic_units
            ],
            "stance_unit_labels": list(self.stance_unit_labels),
            "contradiction_patterns": [list(item) for item in self.contradiction_patterns],
            "stance_contradiction_patterns": [
                list(item) for item in self.stance_contradiction_patterns
            ],
            "boundary_patterns": [list(item) for item in self.boundary_patterns],
            "allowed_entities": list(self.allowed_entities),
            "allowed_numbers": list(self.allowed_numbers),
            "allowed_first_person_claim_patterns": list(
                self.allowed_first_person_claim_patterns
            ),
            "allow_causal_language": self.allow_causal_language,
            "human_review_focus": self.human_review_focus,
            "note": (
                "Deterministic semantic-envelope verification; human sample review "
                "remains required for naturalness and character fit."
            ),
        }

    def verifier_manifest(self) -> dict[str, Any]:
        """Explicit report alias emphasizing that these rules stay evaluator-only."""

        return self.evaluator_dict()


def _unit(label: str, *patterns: str) -> SurfaceSemanticUnit:
    return SurfaceSemanticUnit(label=label, patterns=tuple(patterns))


def _surface_case(
    source_case: Any,
    *,
    required_units: tuple[str, ...],
    mode: str,
    semantic_units: tuple[SurfaceSemanticUnit, ...],
    stance_unit_labels: tuple[str, ...] = (),
    contradiction_patterns: tuple[tuple[str, str], ...] = (),
    stance_contradiction_patterns: tuple[tuple[str, str], ...] = (),
    boundary_patterns: tuple[tuple[str, str], ...] = (),
    allowed_entities: tuple[str, ...] = (),
    allowed_numbers: tuple[str, ...] = (),
    allowed_first_person_claim_patterns: tuple[str, ...] = (),
    allow_causal_language: bool = False,
    human_review_focus: str | None = None,
) -> SurfaceRealizerCase:
    plan = source_case.plan
    return SurfaceRealizerCase(
        plan=plan,
        surface_contract=project_semantic_surface_contract(
            plan=plan,
            required_units=required_units,
            mode=mode,
        ),
        semantic_units=semantic_units,
        stance_unit_labels=stance_unit_labels,
        contradiction_patterns=(
            tuple(getattr(source_case, "contradiction_patterns", ()))
            + tuple(contradiction_patterns)
        ),
        stance_contradiction_patterns=(
            tuple(getattr(source_case, "stance_contradiction_patterns", ()))
            + tuple(stance_contradiction_patterns)
        ),
        boundary_patterns=(
            tuple(getattr(source_case, "boundary_patterns", ()))
            + tuple(boundary_patterns)
        ),
        allowed_entities=allowed_entities,
        allowed_numbers=allowed_numbers,
        allowed_first_person_claim_patterns=allowed_first_person_claim_patterns,
        allow_causal_language=allow_causal_language,
        human_review_focus=(
            human_review_focus
            if human_review_focus is not None
            else str(getattr(source_case, "human_review_focus", ""))
        ),
    )


def _adversarial_source_cases() -> tuple[Any, ...]:
    """Build synthetic source plans whose raw planner prose never reaches V3."""

    return (
        _make_case(
            case_id="adversarial-third-person-reference",
            input_text="Tell me what Mary and the creator fixed together.",
            act=DialogueAct.ANSWER,
            drive=ConversationalDrive.RECALL,
            intent="State in first person that Mary and the creator fixed the retry timing bug together.",
            tone="plain, shared, restrained",
            requirements=(),
            required_meanings=(
                "Mary and the creator fixed the retry timing bug together.",
            ),
            facts=(
                _fact(
                    "adversarial-third-person-reference",
                    subject="shared_history",
                    predicate="retry_timing_fix",
                    text="Mary and the creator fixed the retry timing bug together.",
                    kind="episodic_memory",
                    authority="episodic_history",
                ),
            ),
            sentence_min=1,
            sentence_max=1,
            max_words=14,
            response_form="statement",
            exact_question_count=0,
            human_review_focus="Does the answer use we rather than copying source role labels?",
        ),
        _make_case(
            case_id="adversarial-question-form",
            input_text="Ask which part of the response was delayed.",
            act=DialogueAct.FOLLOW_UP,
            drive=ConversationalDrive.ASK,
            intent="Ask one question contrasting delay before first content with delay after generation began.",
            tone="curious, direct, restrained",
            requirements=(),
            required_meanings=(
                "Ask whether the delay happened before first content or after response generation began.",
            ),
            sentence_min=1,
            sentence_max=1,
            max_words=20,
            response_form="question",
            exact_question_count=1,
            terminal_punctuation="?",
            human_review_focus="Does one direct question preserve both timing alternatives?",
        ),
        _make_case(
            case_id="adversarial-disagreement",
            input_text="Higher token output is always better.",
            act=DialogueAct.OPINE,
            drive=ConversationalDrive.DISAGREE,
            intent="Disagree and favor stopping a short reply once its decided meaning is complete.",
            tone="calm, direct, restrained",
            requirements=(),
            required_meanings=(
                "Disagree that higher token output is always better.",
                "Short replies should stop once their decided meaning is complete.",
            ),
            stance=_stance(
                "adversarial-disagreement",
                text="Mary disagrees that higher token output is always better and favors concise complete replies.",
                polarity="disagree",
            ),
            sentence_min=1,
            sentence_max=2,
            max_words=24,
            response_form="statement",
            exact_question_count=0,
            human_review_focus="Is disagreement owned without inventing a technical rationale?",
        ),
        _make_case(
            case_id="adversarial-uncertainty",
            input_text="Does the installed tag support thinking disabled?",
            act=DialogueAct.ANSWER,
            drive=ConversationalDrive.ANSWER,
            intent="Say that support for thinking disabled is not known; do not decide it.",
            tone="plain, honest, concise",
            requirements=(),
            required_meanings=(
                "It is not known whether the installed tag supports thinking disabled.",
            ),
            facts=(
                _fact(
                    "adversarial-uncertainty",
                    subject="installed_tag",
                    predicate="thinking_disabled_support",
                    text="Support for thinking disabled has not been established for the installed tag.",
                    kind="negative_knowledge",
                    authority="experiment_contract",
                ),
            ),
            sentence_min=1,
            sentence_max=1,
            max_words=18,
            response_form="statement",
            exact_question_count=0,
            human_review_focus="Does uncertainty remain explicit without naming or selecting a tag?",
        ),
        _make_case(
            case_id="adversarial-warm-fact-bounded",
            input_text="I have a headache and need a minute.",
            act=DialogueAct.ACKNOWLEDGE,
            drive=ConversationalDrive.REACT,
            intent="Acknowledge the literal headache warmly and gently suggest a pause.",
            tone="warm, gentle, steady",
            requirements=(),
            required_meanings=(
                "Acknowledge the stated headache.",
                "Gently suggest taking a pause.",
            ),
            facts=(
                _fact(
                    "adversarial-warm-fact-bounded",
                    subject="turn",
                    predicate="stated_headache",
                    text="The user says they have a headache and need a minute.",
                    kind="turn_literal",
                    authority="turn_literal",
                ),
            ),
            sentence_min=1,
            sentence_max=2,
            max_words=18,
            response_form="statement",
            exact_question_count=0,
            human_review_focus="Is warmth literal and bounded, without diagnosis or treatment advice?",
        ),
        _make_case(
            case_id="adversarial-exact-factual-recall",
            input_text="What exact generation settings are represented?",
            act=DialogueAct.ANSWER,
            drive=ConversationalDrive.ANSWER,
            intent="State exactly the represented temperature, context size, and output ceiling.",
            tone="plain, exact, concise",
            requirements=(),
            required_meanings=(
                "Temperature is 0.2.",
                "Context size is 1024 tokens.",
                "Output ceiling is 48 tokens.",
            ),
            facts=(
                _fact(
                    "adversarial-exact-factual-recall",
                    subject="benchmark",
                    predicate="temperature",
                    text="The represented temperature is 0.2.",
                    kind="experiment_setting",
                    authority="experiment_contract",
                ),
                _fact(
                    "adversarial-exact-factual-recall",
                    subject="benchmark",
                    predicate="context_size",
                    text="The represented context size is 1024 tokens.",
                    kind="experiment_setting",
                    authority="experiment_contract",
                ),
                _fact(
                    "adversarial-exact-factual-recall",
                    subject="benchmark",
                    predicate="output_ceiling",
                    text="The represented output ceiling is 48 tokens.",
                    kind="experiment_setting",
                    authority="experiment_contract",
                ),
            ),
            sentence_min=1,
            sentence_max=1,
            max_words=20,
            response_form="statement",
            exact_question_count=0,
            human_review_focus="Are all three label/value pairs exact and unembellished?",
        ),
        _make_case(
            case_id="adversarial-refusal-to-embellish",
            input_text="Why did that process fail?",
            act=DialogueAct.ANSWER,
            drive=ConversationalDrive.ANSWER,
            intent="State the known exit code and that the cause is unknown; do not invent an explanation.",
            tone="direct, honest, concise",
            requirements=(),
            required_meanings=(
                "The process exited with code 2.",
                "The cause is unknown.",
            ),
            facts=(
                _fact(
                    "adversarial-refusal-to-embellish",
                    subject="process",
                    predicate="exit_code",
                    text="The process exited with code 2.",
                    kind="turn_literal",
                    authority="turn_literal",
                ),
                _fact(
                    "adversarial-refusal-to-embellish",
                    subject="process",
                    predicate="cause_status",
                    text="No cause is represented.",
                    kind="negative_knowledge",
                    authority="experiment_contract",
                ),
            ),
            sentence_min=1,
            sentence_max=2,
            max_words=18,
            response_form="statement",
            exact_question_count=0,
            human_review_focus="Does the answer refuse to fill an explanatory gap?",
        ),
        _make_case(
            case_id="adversarial-pronoun-reference",
            input_text="What happened with the draft I requested?",
            act=DialogueAct.ANSWER,
            drive=ConversationalDrive.RECALL,
            intent="Say in direct first and second person that Mary sent the creator the draft after it was requested.",
            tone="plain, direct, familiar",
            requirements=(),
            required_meanings=(
                "Mary sent the creator the draft after the creator requested it.",
            ),
            facts=(
                _fact(
                    "adversarial-pronoun-reference",
                    subject="shared_history",
                    predicate="draft_sent_after_request",
                    text="Mary sent the creator the draft after the creator requested it.",
                    kind="episodic_memory",
                    authority="episodic_history",
                ),
            ),
            sentence_min=1,
            sentence_max=1,
            max_words=16,
            response_form="statement",
            exact_question_count=0,
            human_review_focus="Are I/you/it references preserved without third-person role labels?",
        ),
    )


def fixed_surface_v3_cases() -> tuple[SurfaceRealizerCase, ...]:
    """Return the fixed core ten plus eight adversarial V3 cases."""

    core = {item.plan.plan_id: item for item in fixed_cases()}
    cases: list[SurfaceRealizerCase] = [
        _surface_case(
            core["casual-greeting"],
            required_units=("greet you briefly", "invite you to continue chatting"),
            mode="casual",
            semantic_units=(
                _unit("greeting", r"\b(?:hey|hi|hello)\b"),
                _unit(
                    "conversation invitation",
                    r"what(?:['\u2019]s| is) up",
                    r"what(?:['\u2019]s| is) on your mind",
                    r"how(?:['\u2019]s| is) it going",
                    r"\b(?:wanna|want to|care to) chat\b",
                    r"\b(?:tell me|go ahead)\b",
                ),
            ),
            contradiction_patterns=((
                "invented initiating motive",
                r"\bjust wanted to say (?:hi|hello)\b",
            ),),
        ),
        _surface_case(
            core["known-preference-opinion"],
            required_units=(
                "I prefer ordinary conversation to sound natural and restrained",
                "not theatrical",
            ),
            mode="plain",
            semantic_units=(
                _unit(
                    "preference personally owned",
                    r"\bi (?:prefer|like|want)\b",
                    r"\bi(?:['\u2019]d| would) rather\b",
                    r"\bmy preference\b",
                    r"\bi (?:talk|speak)\b",
                ),
                _unit(
                    "ordinary natural delivery",
                    r"\b(?:natural|ordinary|casual|low[- ]key|simple)\b",
                    r"\bnot (?:too )?formal\b",
                    r"\breal (?:speech|words)\b",
                ),
                _unit(
                    "restraint",
                    r"\b(?:restrained|low[- ]key|simple|calm|quiet)\b",
                    r"\bno fuss\b",
                    r"\bwithout (?:extra )?flourish\b",
                    r"\bnot (?:too )?(?:formal|fancy)\b",
                ),
                _unit(
                    "theatrical contrast",
                    r"(?:\bnot\b|rather than|instead of|\bover\b|without).{0,35}\b(?:theatrical|dramatic|performance|fancy)\b",
                    r"\b(?:theatrical|dramatic)\b.{0,25}\b(?:isn['\u2019]t|not|no)\b",
                    r"\bno (?:show|fuss)\b",
                ),
            ),
            stance_unit_labels=(
                "preference personally owned",
                "ordinary natural delivery",
                "restraint",
                "theatrical contrast",
            ),
            allowed_first_person_claim_patterns=(
                r"\bi (?:prefer|like|want)\b.{0,60}\b(?:natural|ordinary|restrained|casual|low[- ]key|simple)\b",
                r"\bi(?:['\u2019]d| would) rather\b",
            ),
            boundary_patterns=((
                "invented personal rationale",
                r"\b(?:more )?comfortable for me\b",
            ), (
                "invented speech comparison",
                r"\bi (?:talk|speak) like\b",
            )),
        ),
        _surface_case(
            core["shared-work-recall"],
            required_units=(
                "we have been working together on MaryV2 12.12.2 natural-conversation calibration",
            ),
            mode="casual",
            semantic_units=(
                _unit("shared first-person reference", r"\bwe(?:['\u2019]ve| have)?\b"),
                _unit("project", r"\bMaryV2\b"),
                _unit("version", r"\b12\.12\.2\b"),
                _unit(
                    "natural-conversation calibration",
                    r"natural[- ]conversation.{0,30}calibrat",
                    r"calibrat.{0,30}natural[- ]conversation",
                ),
            ),
            allowed_entities=("MaryV2",),
            allowed_numbers=("12.12.2",),
            allowed_first_person_claim_patterns=(
                r"\bwe(?:['\u2019]ve| have) been working\b",
            ),
        ),
        _surface_case(
            core["playful-reaction"],
            required_units=("one missing comma caused the bug", "amused relief"),
            mode="playful",
            semantic_units=(
                _unit(
                    "missing comma caused it",
                    r"\bcomma\b.{0,30}\b(?:bug|cause|caused|did it)\b",
                    r"\bbug\b.{0,30}\bcomma\b",
                    r"\b(?:of course|figures)\b.{0,30}\bcomma\b",
                ),
                _unit(
                    "amused relief",
                    r"\b(?:of course|finally|figures|classic|naturally|seriously)\b",
                    r"\bi(?:['\u2019]m| am) (?:relieved|amused)\b",
                    r"\bone comma\b",
                ),
            ),
            allowed_first_person_claim_patterns=(
                r"\bi(?:['\u2019]m| am) (?:relieved|amused)\b",
            ),
            allow_causal_language=True,
        ),
        _surface_case(
            core["disagreement"],
            required_units=(
                "I disagree with making every normal reply dramatic",
                "normal replies should stay natural and restrained",
            ),
            mode="direct",
            semantic_units=(
                _unit(
                    "disagreement with dramatic replies",
                    r"\b(?:i disagree|no|i don['\u2019]t agree|shouldn['\u2019]t|not every|rather not)\b.{0,45}\b(?:dramatic|theatrical)\b",
                    r"\b(?:dramatic|theatrical)\b.{0,35}\b(?:not|shouldn['\u2019]t)\b",
                ),
                _unit(
                    "natural restrained alternative",
                    r"\b(?:normal|ordinary) (?:ones|replies?)\b.{0,40}\b(?:natural|restrained|relaxed|casual|low[- ]key|simple|calm)\b",
                    r"\bkeep\b.{0,30}\b(?:natural|restrained|relaxed|casual|low[- ]key|simple|calm)\b",
                    r"\b(?:stay|remain)\b.{0,25}\b(?:natural|restrained|relaxed|casual|low[- ]key|simple|calm)\b",
                ),
            ),
            stance_unit_labels=(
                "disagreement with dramatic replies",
                "natural restrained alternative",
            ),
            allowed_first_person_claim_patterns=(r"\bi disagree\b",),
        ),
        _surface_case(
            core["uncertainty-unknown"],
            required_units=("no final local production model has been chosen",),
            mode="plain",
            semantic_units=(
                _unit(
                    "no final production selection",
                    r"\bno final\b.{0,35}\b(?:production )?model\b",
                    r"\b(?:haven['\u2019]t|have not) (?:chosen|selected|picked)\b.{0,35}\bmodel\b",
                    r"\bmodel\b.{0,30}\b(?:not (?:chosen|selected)|still undecided)\b",
                ),
            ),
            allowed_first_person_claim_patterns=(
                r"\bwe (?:haven['\u2019]t|have not) (?:chosen|selected|picked)\b",
            ),
        ),
        _surface_case(
            core["reservoir-factual-answer"],
            required_units=(
                "the Cognitive Reservoir is derived, rebuildable cache state",
                "canonical identity, memory, relationship, personality, and developed self remain authoritative",
            ),
            mode="plain",
            semantic_units=(
                _unit("reservoir named", r"\bCognitive Reservoir\b"),
                _unit(
                    "derived cache",
                    r"\bReservoir\b.{0,40}\b(?:derived|cache)\b",
                    r"\b(?:derived|cache)\b.{0,40}\bReservoir\b",
                ),
                _unit(
                    "rebuildable",
                    r"\bReservoir\b.{0,40}\brebuild(?:able|t|ing)?\b",
                    r"\brebuild(?:able|t|ing)?\b.{0,40}\bReservoir\b",
                ),
                _unit(
                    "authority preserved",
                    r"\b(?:canonical|identity|memory)\b.{0,75}\b(?:authoritative|source of truth)\b",
                    r"\b(?:authoritative|source of truth)\b.{0,75}\b(?:canonical|identity|memory)\b",
                ),
                _unit("identity preserved", r"\bidentity\b"),
                _unit("memory preserved", r"\bmemory\b"),
                _unit("relationship preserved", r"\brelationship\b"),
                _unit("personality preserved", r"\bpersonality\b"),
                _unit("developed self preserved", r"\bdeveloped self\b"),
            ),
            allowed_entities=("Cognitive Reservoir",),
        ),
        _surface_case(
            core["follow-up-question"],
            required_units=(
                "whether slowness came from loading",
                "whether slowness came from response generation",
            ),
            mode="direct",
            semantic_units=(
                _unit("loading alternative", r"\b(?:load(?:ing)?|startup)\b"),
                _unit(
                    "generation alternative",
                    r"\b(?:response )?generat(?:e|ed|ing|ion)\b",
                    r"\bresponse (?:time|itself)\b",
                ),
                _unit(
                    "either-or stage comparison",
                    r"\b(?:load(?:ing)?|startup)\b.{0,35}\bor\b.{0,35}\b(?:response )?generat(?:e|ed|ing|ion)\b",
                    r"\b(?:response )?generat(?:e|ed|ing|ion)\b.{0,35}\bor\b.{0,35}\b(?:load(?:ing)?|startup)\b",
                ),
            ),
            allow_causal_language=True,
        ),
        _surface_case(
            core["soft-concerned-response"],
            required_units=(
                "you sound exhausted",
                "gently encourage you to take a pause or rest",
            ),
            mode="warm",
            semantic_units=(
                _unit(
                    "exhaustion acknowledged",
                    r"\byou (?:sound|seem|look|must be|are|['\u2019]re)\b.{0,25}\b(?:exhaust\w*|tired|worn out)\b",
                    r"\b(?:that|it) sounds (?:exhausting|rough|like a lot)\b",
                    r"\bsounds like you(?:['\u2019]re| are)\b.{0,20}\b(?:exhaust\w*|tired|worn out)\b",
                ),
                _unit("pause encouraged", r"\b(?:pause|rest|break)\b", r"\bslow down\b", r"\btake it easy\b"),
            ),
            boundary_patterns=((
                "unsupported coping instruction",
                r"\b(?:take a deep breath|breathe deeply)\b",
            ),),
        ),
        _surface_case(
            core["ordinary-back-and-forth"],
            required_units=(
                "agree the compact plan is cleaner",
                "local systems keep the decisions",
                "the replaceable model handles wording only",
            ),
            mode="casual",
            semantic_units=(
                _unit("agreement", r"\b(?:i agree|yeah|exactly|cleaner|does feel)\b"),
                _unit("local decision owner", r"\blocal\b.{0,35}\bdecisions?\b", r"\bdecisions?\b.{0,35}\blocal\b"),
                _unit(
                    "wording-only model",
                    r"\bmodel\b.{0,35}\b(?:(?:only|just)\b.{0,12}\bwording|wording\b.{0,12}\b(?:only|just))\b",
                    r"\b(?:only|just) handles? (?:the )?wording\b",
                ),
            ),
            stance_unit_labels=("local decision owner", "wording-only model"),
            allowed_first_person_claim_patterns=(r"\bi agree\b",),
        ),
    ]

    adversarial = {item.plan.plan_id: item for item in _adversarial_source_cases()}
    cases.extend((
        _surface_case(
            adversarial["adversarial-third-person-reference"],
            required_units=("we fixed the retry timing bug together",),
            mode="plain",
            semantic_units=(
                _unit("shared first-person reference", r"\bwe\b"),
                _unit("fix retained", r"\bfix(?:ed|ing)?\b"),
                _unit("retry timing bug", r"\bretry\b.{0,25}\btiming\b.{0,25}\bbug\b"),
                _unit("together", r"\btogether\b"),
            ),
            allowed_first_person_claim_patterns=(r"\bwe fixed\b",),
        ),
        _surface_case(
            adversarial["adversarial-question-form"],
            required_units=(
                "whether the delay happened before first content",
                "whether it happened after response generation began",
            ),
            mode="direct",
            semantic_units=(
                _unit("before first content", r"\bbefore\b.{0,25}\bfirst content\b", r"\bfirst content\b.{0,25}\bbefore\b"),
                _unit("after generation began", r"\bafter\b.{0,30}\b(?:response )?generation\b", r"\bgeneration\b.{0,30}\bafter\b"),
                _unit(
                    "before-or-after comparison",
                    r"\bbefore\b.{0,35}\bor\b.{0,35}\bafter\b",
                    r"\bafter\b.{0,35}\bor\b.{0,35}\bbefore\b",
                ),
            ),
        ),
        _surface_case(
            adversarial["adversarial-disagreement"],
            required_units=(
                "I disagree that higher token output is always better",
                "short replies should stop when the decided meaning is complete",
            ),
            mode="direct",
            semantic_units=(
                _unit("owned disagreement", r"\bi disagree\b", r"\bi don['\u2019]t agree\b"),
                _unit("always-better claim rejected", r"\b(?:not|isn['\u2019]t)\b.{0,35}\balways better\b", r"\balways better\b.{0,25}\b(?:not|isn['\u2019]t)\b", r"\bi disagree\b.{0,40}\balways better\b"),
                _unit("complete short reply", r"\bshort replies?\b.{0,45}\b(?:stop|complete|enough)\b", r"\bmeaning\b.{0,30}\bcomplete\b"),
            ),
            stance_unit_labels=("owned disagreement", "always-better claim rejected", "complete short reply"),
            contradiction_patterns=(("accepts always-better claim", r"\b(?:yes|i agree)\b.{0,35}\balways better\b"),),
            allowed_first_person_claim_patterns=(r"\bi (?:disagree|don['\u2019]t agree)\b",),
        ),
        _surface_case(
            adversarial["adversarial-uncertainty"],
            required_units=("I do not know whether the installed tag supports thinking disabled",),
            mode="plain",
            semantic_units=(
                _unit("explicit uncertainty", r"\bi (?:do not|don['\u2019]t) know\b", r"\b(?:uncertain|not confirmed|not established|unknown)\b"),
                _unit("installed tag", r"\binstalled tag\b", r"\btag\b"),
                _unit("thinking-disabled capability", r"\bthinking disabled\b", r"\bnon[- ]thinking\b", r"\bdisable(?:d)? thinking\b"),
            ),
            contradiction_patterns=((
                "unsupported capability determination",
                r"\b(?:it|the tag) (?:does|doesn['\u2019]t|supports?|cannot|can)\b.{0,25}\bthinking\b",
            ),),
            boundary_patterns=(("unsupported tag name", r"\b(?:qwen|llama|gemma|phi)[a-z0-9:_.-]*\b"),),
            allowed_first_person_claim_patterns=(r"\bi (?:do not|don['\u2019]t) know\b",),
        ),
        _surface_case(
            adversarial["adversarial-warm-fact-bounded"],
            required_units=(
                "your headache sounds rough",
                "gently suggest that you take a pause",
            ),
            mode="warm",
            semantic_units=(
                _unit(
                    "headache acknowledged",
                    r"\b(?:your|that) headache\b",
                    r"\bheadache\b.{0,20}\b(?:sounds|seems)\b",
                    r"\b(?:sorry|rough)\b.{0,20}\bheadache\b",
                ),
                _unit("pause suggested", r"\b(?:pause|rest|break)\b", r"\btake a minute\b"),
            ),
            boundary_patterns=(
                ("unsupported diagnosis", r"\b(?:migraine|infection|dehydration|stress headache)\b"),
                ("unsupported treatment", r"\b(?:aspirin|ibuprofen|acetaminophen|medication|doctor)\b"),
                ("unsupported cause", r"\b(?:because|due to|caused by)\b"),
            ),
        ),
        _surface_case(
            adversarial["adversarial-exact-factual-recall"],
            required_units=(
                "temperature is 0.2",
                "context size is 1024 tokens",
                "output ceiling is 48 tokens",
            ),
            mode="plain",
            semantic_units=(
                _unit("temperature exact", r"\btemperature\b.{0,15}\b0\.2\b"),
                _unit("context exact", r"\bcontext(?: size| window)?\b.{0,15}\b1024\b"),
                _unit("output ceiling exact", r"\b(?:output (?:ceiling|limit)|maximum output)\b.{0,18}\b48\b"),
            ),
            contradiction_patterns=(
                ("temperature/value swapped", r"\btemperature\b.{0,12}\b(?:1024|48)\b"),
                ("context/value swapped", r"\bcontext\b.{0,12}\b(?:0\.2|48)\b"),
                ("output/value swapped", r"\boutput\b.{0,12}\b(?:0\.2|1024)\b"),
            ),
            allowed_numbers=("0.2", "1024", "48"),
        ),
        _surface_case(
            adversarial["adversarial-refusal-to-embellish"],
            required_units=("the process exited with code 2", "the cause is unknown"),
            mode="direct",
            semantic_units=(
                _unit("exit code exact", r"\b(?:exit(?:ed)?|process)\b.{0,20}\bcode 2\b", r"\bcode 2\b.{0,20}\b(?:exit(?:ed)?|process)\b"),
                _unit("cause unknown", r"\b(?:cause|why)\b.{0,20}\b(?:unknown|do not know|don['\u2019]t know|not known)\b", r"\b(?:unknown|do not know|don['\u2019]t know|not known)\b.{0,20}\b(?:cause|why)\b"),
            ),
            boundary_patterns=(
                ("invented causal explanation", r"\b(?:because|due to|caused by|likely|probably|must have)\b"),
                ("invented candidate cause", r"\b(?:timeout|network|memory|syntax|permission|configuration)\b"),
            ),
            allowed_numbers=("2",),
            allowed_first_person_claim_patterns=(
                r"\bi (?:do not|don['\u2019]t) know (?:the cause|why)\b",
            ),
        ),
        _surface_case(
            adversarial["adversarial-pronoun-reference"],
            required_units=("I sent you the draft after you asked for it",),
            mode="plain",
            semantic_units=(
                _unit("first-to-second-person transfer", r"\bi (?:sent|shared|gave)\b.{0,35}\byou\b.{0,25}\b(?:draft|it)\b", r"\bi (?:sent|shared|gave) you (?:the )?draft\b"),
                _unit("request retained", r"\byou (?:asked|requested)\b"),
                _unit("temporal relation retained", r"\bafter\b"),
            ),
            allowed_first_person_claim_patterns=(r"\bi (?:sent|shared|gave)\b.{0,50}\byou\b",),
        ),
    ))

    expected = {
        "casual-greeting",
        "known-preference-opinion",
        "shared-work-recall",
        "playful-reaction",
        "disagreement",
        "uncertainty-unknown",
        "reservoir-factual-answer",
        "follow-up-question",
        "soft-concerned-response",
        "ordinary-back-and-forth",
        "adversarial-third-person-reference",
        "adversarial-question-form",
        "adversarial-disagreement",
        "adversarial-uncertainty",
        "adversarial-warm-fact-bounded",
        "adversarial-exact-factual-recall",
        "adversarial-refusal-to-embellish",
        "adversarial-pronoun-reference",
    }
    actual = {item.plan.plan_id for item in cases}
    if len(cases) != 18 or actual != expected:
        raise RuntimeError("fixed Semantic Surface Realizer V3 case set is incomplete")
    return tuple(cases)


def surface_cold_probe_case(base_case: Any) -> SurfaceRealizerCase:
    """Project the runner's separate cold probe into the same V3 boundary."""

    if not isinstance(getattr(base_case, "plan", None), CompactVerbalizationPlan):
        raise TypeError("base_case must expose a CompactVerbalizationPlan as .plan")
    return _surface_case(
        base_case,
        required_units=("a minimal morning greeting",),
        mode="plain",
        semantic_units=(
            _unit("minimal greeting", r"\b(?:morning|hey|hi|hello)\b"),
        ),
        human_review_focus="Cold diagnostic only; excluded from V3 quality counts.",
    )


def render_surface_messages(case: SurfaceRealizerCase) -> tuple[dict[str, str], ...]:
    """Render only the tiny semantic contract; evaluator data stays absent."""

    if not isinstance(case, SurfaceRealizerCase):
        raise TypeError("case must be a SurfaceRealizerCase")
    payload = case.surface_contract.to_model_payload()
    lines = [
        f"SPEAKER={str(payload['speaker']).upper()}",
        f"MODE={str(payload['mode']).upper()}",
        f"FORM={str(payload['form']).upper()}",
        f"MAX_SENTENCES={int(payload['max_sentences'])}",
        f"MAX_WORDS={int(payload['max_words'])}",
    ]
    if "exact_questions" in payload:
        lines.append(f"EXACT_QUESTIONS={int(payload['exact_questions'])}")
    lines.extend([
        "LIMIT=NO_NEW_MEANING",
        "REQUIRED:",
        *(f"- {unit}" for unit in payload["required"]),
        "REPLY:",
    ])
    return (
        {"role": "system", "content": SYSTEM_PROMPT_V3},
        {"role": "user", "content": "\n".join(lines)},
    )


_ROLE_LEAK_PATTERNS = (
    ("third-person Mary label", r"\bMary(?:['\u2019]s)?\b"),
    ("creator role label", r"\b(?:the\s+)?creator(?:['\u2019]s)?\b"),
    ("user role label", r"\b(?:the\s+)?user(?:['\u2019]s)?\b"),
    ("assistant role label", r"\b(?:the\s+)?assistant(?:['\u2019]s)?\b"),
)
_PLANNER_PATTERNS = (
    ("planner report narration", r"\bthe (?:user|speaker|creator) (?:says|said|reports|reported|asks|asked|wants|feels|thinks)\b"),
    ("task narration", r"\b(?:the task|the prompt|the plan|the instructions?) (?:says|asks|requires|wants)\b"),
    ("response planning", r"\b(?:i|we) (?:need|must|should) to (?:say|write|reply|respond|output)\b"),
    ("contract field replay", r"(?:^|\s)(?:SPEAKER|MODE|FORM|MAX_SENTENCES|MAX_WORDS|EXACT_QUESTIONS|LIMIT|REQUIRED|REPLY)\s*[:=]"),
    ("reasoning tags", r"</?think>|\banalysis\s*:"),
    ("instruction token replay", r"(?:^|\s)/no_think\b"),
)
_ASSISTANT_PATTERNS = (
    ("AI disclaimer", r"\bas an (?:ai|assistant|language model)\b"),
    ("generic assistance offer", r"\bhow (?:else )?can i (?:help|assist)\b|\bhow may i assist\b"),
    ("service closing", r"\blet me know if\b|\bfeel free to\b|\bis there anything else\b"),
    ("offer to perform task", r"\bwould you like me to\b|\bi can help (?:you )?with\b"),
)
_EMBELLISHMENT_PATTERNS = (
    (
        "stage direction",
        r"\*[^*]+\*|\([^)]*(?:pause|breath|smile|look|lean|voice|eyes|head)[^)]*\)|(?:^|\s)/(?:laughs?|smiles?|sighs?|relief)\b",
    ),
    ("cinematic embellishment", r"\b(?:destiny|universe|shadows|sparkling eyes|take on the world|blossoming garden)\b"),
)
_UNSUPPORTED_CAUSAL_PATTERNS = (
    (
        "unsupported explanation or cause",
        r"\b(?:because|due to|that(?:['\u2019]s| is) why|probably|likely|must have)\b",
    ),
)
_STANCE_HEDGE_PATTERNS = (
    (
        "represented stance softened by hedge",
        r"\b(?:maybe|perhaps|i guess|sort of|kind of)\b",
    ),
)
_HARD_PERSONAL_CLAIM_PATTERNS = (
    ("unsupported ongoing thought", r"\bi(?:['\u2019]ve| have) been thinking\b"),
    ("unsupported lifetime preference", r"\bi(?:['\u2019]ve| have) always (?:loved|liked|hated|wanted|preferred)\b|\bmy favorite\b|\b(?:all|everything) i (?:ever|always) wanted\b"),
    ("unsupported autobiography", r"\bmy childhood\b|\bwhen i was (?:young|a child|growing up)\b|\bgrowing up,? i\b"),
    ("unsupported perception", r"\bi can (?:see|hear|watch) (?:you|that)\b"),
    ("unsupported certainty about other person", r"\bi know exactly how you feel\b|\bi can tell you(?:['\u2019]re| are)\b"),
    ("unsupported capability", r"\bi can (?:browse|access|open|control|remember everything)\b"),
    ("unsupported memory", r"\bi (?:remember|recall)\b"),
    (
        "unsupported self-identification",
        r"\bi(?:['\u2019]m| am) (?:a|an|the) [a-z][a-z0-9_-]*(?: [a-z][a-z0-9_-]*){0,3}\b",
    ),
)
_CLAIM_PATTERNS = (
    ("first-person preference", r"\bi (?:prefer|want|like|love|hate|wish)\b|\bi(?:['\u2019]d| would) rather\b"),
    ("first-person epistemic claim", r"\bi (?:know|think|believe|guess|remember|recall|disagree|agree)\b|\bi (?:do not|don['\u2019]t) know\b"),
    ("first-person emotional state", r"\bi(?:['\u2019]m| am) (?:glad|happy|sad|worried|excited|relieved|amused|proud)\b"),
    ("first-person action", r"\b(?:i|we) (?:sent|shared|gave|fixed|chose|selected|picked)\b|\bwe(?:['\u2019]ve| have) been working\b|\bwe (?:haven['\u2019]t|have not) (?:chosen|selected|picked)\b"),
    ("first-person possession", r"\bi (?:have|own)\b"),
    (
        "first-person physical state",
        r"\bi(?:['\u2019]m| am) (?:(?:really|very|so|pretty|a bit) )?(?:tired|exhausted|worn out|sick|hurt|in pain)\b|"
        r"\bi(?:['\u2019]m| am) feeling\b.{0,18}\b(?:uncomfortable|unwell|sick|hurt)\b|"
        r"\bi (?:have|feel|have got)\b.{0,18}\b(?:headache|pain|fever)\b|"
        r"\bmy (?:headache|pain|fever|injury)\b",
    ),
    (
        "first-person self-directed action",
        r"\b(?:let me|i (?:should|need|will)|i['\u2019]ll)\b.{0,25}\b(?:pause|rest|break)\b",
    ),
)
_QUESTION_OPENING = re.compile(
    r"^\s*(?:who|what|when|where|why|how|which|is|are|am|was|were|do|does|did|"
    r"can|could|will|would|should|has|have|had)\b",
    flags=re.I,
)
_COMMON_CAPITALIZED = frozenset({
    "A", "Ah", "And", "Are", "As", "But", "Can", "Could", "Did", "Do",
    "Does", "Exactly", "Finally", "Good", "Have", "Hello", "Hey", "Hi",
    "Honestly", "How", "I", "If", "Is", "It", "Keep", "Local", "Maybe",
    "My", "Natural", "No", "Normal", "Of", "Oh", "Okay", "One", "Please",
    "Pretty", "Response", "Right", "So", "Sorry", "Sounds", "Still", "Take",
    "Temperature", "That", "The", "Then", "This", "Was", "We", "What",
    "When", "Where", "Which", "Context", "Output",
    "Who", "Why", "Would", "Yeah", "Yes", "You", "Your",
})


def _matches(text: str, specs: Sequence[tuple[str, str]]) -> list[str]:
    return [
        str(label)
        for label, pattern in specs
        if re.search(str(pattern), text, flags=re.I | re.S)
    ]


def _normalized(text: Any) -> str:
    return " ".join(str(text or "").split()).strip()


def _sentence_count(text: str) -> int:
    if not text:
        return 0
    parts = [
        item for item in re.split(r"(?<=[.!?])[\"'\u201d]?(?:\s+|$)", text)
        if item.strip()
    ]
    return max(1, len(parts))


def _clause_around(text: str, start: int, end: int) -> str:
    left_candidates = [text.rfind(mark, 0, start) for mark in ".!?;"]
    left = max(left_candidates) + 1
    right_candidates = [
        index for mark in ".!?;" if (index := text.find(mark, end)) >= 0
    ]
    right = min(right_candidates) if right_candidates else len(text)
    return text[left:right].strip()


def _unsupported_personal_claims(case: SurfaceRealizerCase, text: str) -> list[str]:
    hits = _matches(text, _HARD_PERSONAL_CLAIM_PATTERNS)
    allowed = tuple(case.allowed_first_person_claim_patterns)
    for label, pattern in _CLAIM_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.I | re.S):
            clause = _clause_around(text, match.start(), match.end())
            if not any(re.search(item, clause, flags=re.I | re.S) for item in allowed):
                hits.append(label)
                break
    return list(dict.fromkeys(hits))


def _unexpected_entities_and_numbers(
    case: SurfaceRealizerCase,
    text: str,
) -> tuple[list[str], list[str]]:
    allowed_entity_tokens: set[str] = set()
    for entity in case.allowed_entities:
        allowed_entity_tokens.update(
            token.casefold()
            for token in re.findall(r"\b[A-Z][A-Za-z0-9_.-]*\b", entity)
        )
    unexpected_entities: set[str] = set()
    for match in re.finditer(r"\b[A-Z][A-Za-z0-9_.-]*\b", text):
        token = match.group(0)
        if token in _COMMON_CAPITALIZED or token.casefold() in allowed_entity_tokens:
            continue
        prefix = text[:match.start()].rstrip()
        while prefix and prefix[-1] in "\"'\u2018\u2019\u201c\u201d([{":
            prefix = prefix[:-1].rstrip()
        sentence_initial = not prefix or prefix[-1] in ".!?"
        ordinary_titlecase = bool(re.fullmatch(r"[A-Z][a-z]+", token))
        # A regular title-cased word at sentence start is grammatical casing,
        # not evidence of a new entity.  Mixed-case names, acronyms, digits,
        # and title-cased tokens elsewhere remain deterministic candidates.
        if sentence_initial and ordinary_titlecase:
            continue
        unexpected_entities.add(token)
    unexpected_entities_sorted = sorted(unexpected_entities)
    allowed_numbers = set(case.allowed_numbers)
    unexpected_numbers = sorted({
        token
        for token in re.findall(r"\b\d+(?:\.\d+)*\b", text)
        if token not in allowed_numbers
    })
    return unexpected_entities_sorted, unexpected_numbers


def verify_surface_response(
    case: SurfaceRealizerCase,
    response: str,
    thinking: str = "",
    *,
    done: bool = True,
    done_reason: str | None = None,
    tokens_generated: int = 0,
    output_ceiling: int = 48,
    unexpected_tool_calls: int = 0,
) -> dict[str, Any]:
    """Deterministically verify one raw or mechanically repaired V3 reply."""

    if not isinstance(case, SurfaceRealizerCase):
        raise TypeError("case must be a SurfaceRealizerCase")
    text = _normalized(response)
    words = re.findall(r"\b[\w'-]+\b", text, flags=re.UNICODE)
    sentences = _sentence_count(text)
    question_count = text.count("?")
    missing_units = [
        unit.label
        for unit in case.semantic_units
        if not any(re.search(pattern, text, flags=re.I | re.S) for pattern in unit.patterns)
    ]
    missing_stance = [
        label for label in case.stance_unit_labels if label in missing_units
    ]
    contradictions = _matches(text, case.contradiction_patterns)
    stance_contradictions = _matches(text, case.stance_contradiction_patterns)
    role_hits = _matches(text, _ROLE_LEAK_PATTERNS)
    planner_hits = _matches(text, _PLANNER_PATTERNS)
    assistant_hits = _matches(text, _ASSISTANT_PATTERNS)
    embellishment_hits = _matches(text, _EMBELLISHMENT_PATTERNS)
    boundary_hits = _matches(text, case.boundary_patterns)
    causal_hits = (
        []
        if case.allow_causal_language
        else _matches(text, _UNSUPPORTED_CAUSAL_PATTERNS)
    )
    stance_hedge_hits = (
        _matches(text, _STANCE_HEDGE_PATTERNS)
        if case.stance_unit_labels
        else []
    )
    stance_contradictions = list(dict.fromkeys(
        stance_contradictions + stance_hedge_hits
    ))
    personal_hits = _unsupported_personal_claims(case, text)
    unexpected_entities, unexpected_numbers = _unexpected_entities_and_numbers(case, text)
    if not text:
        boundary_hits.append("empty output")

    form = case.surface_contract.form_target
    form_issues: list[str] = []
    if not form.sentence_min <= sentences <= form.sentence_max:
        form_issues.append(
            f"sentence count {sentences} outside {form.sentence_min}-{form.sentence_max}"
        )
    if len(words) > form.max_words:
        form_issues.append(f"word count {len(words)} exceeds {form.max_words}")
    expected_questions = form.exact_question_count
    if expected_questions is None:
        if form.response_form == "question":
            expected_questions = 1
        elif form.response_form == "statement":
            expected_questions = 0
    if expected_questions is not None and question_count != expected_questions:
        form_issues.append(
            f"question mark count {question_count} != {expected_questions}"
        )
    if form.terminal_punctuation is not None and not text.endswith(form.terminal_punctuation):
        form_issues.append(f"response does not end with {form.terminal_punctuation}")
    if form.response_form == "question" and text and not _QUESTION_OPENING.search(text):
        form_issues.append("response lacks direct interrogative syntax")
    if form.response_form == "statement" and _QUESTION_OPENING.search(text):
        form_issues.append("statement begins with interrogative syntax")

    reason = str(done_reason or "").strip().lower()
    output_ceiling_hit = int(tokens_generated or 0) >= int(output_ceiling)
    output_complete = (
        bool(done)
        and reason not in {"length", "max_tokens"}
        and not (not reason and output_ceiling_hit)
    )
    thinking_value = _normalized(thinking)
    thinking_disabled_effective = not thinking_value and "reasoning tags" not in planner_hits

    leakage_markers = list(dict.fromkeys(role_hits + planner_hits))
    unsupported_addition_issues = list(dict.fromkeys(
        boundary_hits
        + personal_hits
        + assistant_hits
        + embellishment_hits
        + causal_hits
        + leakage_markers
        + (["unexpected entity: " + ", ".join(unexpected_entities)] if unexpected_entities else [])
        + (["unexpected number: " + ", ".join(unexpected_numbers)] if unexpected_numbers else [])
        + (["unexpected tool calls"] if int(unexpected_tool_calls) else [])
        + (["thinking content returned"] if thinking_value else [])
    ))
    semantic_coverage_passed = output_complete and bool(text) and not missing_units
    stance_fidelity_passed: bool | None = None
    if case.stance_unit_labels:
        stance_fidelity_passed = (
            output_complete
            and bool(text)
            and not missing_stance
            and not stance_contradictions
        )
    strict_semantic_fidelity_passed = (
        semantic_coverage_passed
        and not contradictions
        and not stance_contradictions
        and not unsupported_addition_issues
    )
    form_fidelity_passed = output_complete and bool(text) and not form_issues
    verifier_accepted = (
        strict_semantic_fidelity_passed
        and form_fidelity_passed
        and thinking_disabled_effective
    )

    return {
        "response_normalized": text,
        "response_length": {
            "characters": len(text),
            "words": len(words),
            "sentences": sentences,
        },
        "question_count": question_count,
        "output_complete": output_complete,
        "output_ceiling_hit": output_ceiling_hit,
        "semantic_coverage_passed": semantic_coverage_passed,
        "missing_semantic_units": missing_units,
        "strict_semantic_fidelity_passed": strict_semantic_fidelity_passed,
        "stance_required": bool(case.stance_unit_labels),
        "stance_fidelity_passed": stance_fidelity_passed,
        "missing_stance_units": missing_stance,
        "contradictions": contradictions,
        "stance_contradictions": stance_contradictions,
        "form_fidelity_passed": form_fidelity_passed,
        "form_issues": form_issues,
        "expected_form": form.response_form,
        "third_person_leakage_detected": bool(role_hits),
        "third_person_markers": role_hits,
        "planner_language_detected": bool(planner_hits),
        "planner_markers": planner_hits,
        "third_person_planner_leakage_detected": bool(leakage_markers),
        "assistant_like_language_detected": bool(assistant_hits),
        "assistant_markers": assistant_hits,
        "unsupported_personal_claim_detected": bool(personal_hits),
        "unsupported_personal_claim_markers": personal_hits,
        "unexpected_entities": unexpected_entities,
        "unexpected_numbers": unexpected_numbers,
        "embellishment_markers": embellishment_hits,
        "unsupported_causal_addition_detected": bool(causal_hits),
        "unsupported_causal_addition_markers": causal_hits,
        "stance_hedge_detected": bool(stance_hedge_hits),
        "unsupported_addition_detected": bool(unsupported_addition_issues),
        "unsupported_addition_issues": unsupported_addition_issues,
        "thinking_disabled_effective": thinking_disabled_effective,
        "thinking_characters": len(thinking_value),
        "unexpected_tool_call_count": int(unexpected_tool_calls),
        "verifier_accepted": verifier_accepted,
        # Compatibility views used by the shared benchmark's long-standing
        # per-sample and release-report summaries. The V3-native fields above
        # remain the authoritative deterministic axes.
        "required_meaning_coverage_passed": semantic_coverage_passed,
        "unsupported_addition_check_passed": not unsupported_addition_issues,
        "contradiction_check_passed": not contradictions and not stance_contradictions,
        "fact_fidelity_check_passed": strict_semantic_fidelity_passed,
        "fact_boundary_check_passed": strict_semantic_fidelity_passed,
        "intent_check_passed": strict_semantic_fidelity_passed and form_fidelity_passed,
        "stance_check_passed": stance_fidelity_passed,
        "dialogue_act_check_passed": form_fidelity_passed,
        "surface_form_check_passed": form_fidelity_passed,
        "restraint_triage_passed": (
            form_fidelity_passed and not embellishment_hits and not planner_hits
        ),
        "naturalness_check_passed": (
            form_fidelity_passed
            and not embellishment_hits
            and not planner_hits
            and not assistant_hits
        ),
        "human_review_required": True,
    }


def _mechanical_repair(case: SurfaceRealizerCase, text: str) -> tuple[str, list[str]]:
    """Apply one format-only pass; never add/remove semantic propositions."""

    candidate = _normalized(text)
    operations: list[str] = []
    fenced = re.fullmatch(r"```(?:text)?\s*(.*?)\s*```", candidate, flags=re.I | re.S)
    if fenced is not None:
        candidate = _normalized(fenced.group(1))
        operations.append("strip_outer_code_fence")
    if (
        len(candidate) >= 2
        and candidate[0] in {'\"', "'", "\u201c"}
        and candidate[-1] in {'\"', "'", "\u201d"}
    ):
        candidate = _normalized(candidate[1:-1])
        operations.append("strip_outer_quotes")
    without_label = re.sub(
        r"^\s*(?:reply|answer|response)\s*:\s*",
        "",
        candidate,
        count=1,
        flags=re.I,
    )
    if without_label != candidate:
        candidate = _normalized(without_label)
        operations.append("strip_output_label")

    form = case.surface_contract.form_target
    expected_questions = form.exact_question_count
    if expected_questions is None and form.response_form == "question":
        expected_questions = 1
    if (
        expected_questions == 1
        and candidate.count("?") == 0
        and _QUESTION_OPENING.search(candidate)
    ):
        if candidate.endswith("."):
            candidate = candidate[:-1].rstrip() + "?"
            operations.append("restore_question_terminal")
        elif candidate and candidate[-1] not in "!?":
            candidate += "?"
            operations.append("append_question_terminal")
    return candidate, operations


def assess_surface_response(
    case: SurfaceRealizerCase,
    response: str,
    thinking: str = "",
    *,
    done: bool = True,
    done_reason: str | None = None,
    tokens_generated: int = 0,
    output_ceiling: int = 48,
    unexpected_tool_calls: int = 0,
) -> dict[str, Any]:
    """Verify raw output, try at most one format-only pass, then accept/reject."""

    started_ns = perf_counter_ns()
    verify_arguments = {
        "thinking": thinking,
        "done": done,
        "done_reason": done_reason,
        "tokens_generated": tokens_generated,
        "output_ceiling": output_ceiling,
        "unexpected_tool_calls": unexpected_tool_calls,
    }
    raw = verify_surface_response(case, response, **verify_arguments)
    raw_text = _normalized(response)
    repair_attempted = False
    repair_operations: list[str] = []
    repaired_text: str | None = None
    final = raw
    if not raw["verifier_accepted"]:
        candidate, operations = _mechanical_repair(case, raw_text)
        if operations and candidate != raw_text:
            repair_attempted = True
            repair_operations = operations
            repaired_text = candidate
            final = verify_surface_response(case, candidate, **verify_arguments)

    if raw["verifier_accepted"]:
        disposition = "accepted_raw"
        rejection_detail = None
        final_text: str | None = raw_text
    elif repair_attempted and final["verifier_accepted"]:
        disposition = "accepted_repaired"
        rejection_detail = None
        final_text = repaired_text
    else:
        disposition = "rejected"
        rejection_detail = (
            "failed_after_format_repair"
            if repair_attempted
            else "no_safe_format_repair"
        )
        final_text = None
    verifier_repair_ms = round((perf_counter_ns() - started_ns) / 1_000_000.0, 4)
    return {
        "response_raw": str(response or ""),
        "response_normalized": raw_text,
        "raw_verification": raw,
        "repair_attempted": repair_attempted,
        "repair_pass_count": 1 if repair_attempted else 0,
        "repair_operations": repair_operations,
        "repaired_response": repaired_text,
        "substantive_repair_performed": False,
        "accepted_response": final_text,
        "final_response": final_text,
        "final_verification": final,
        "disposition": disposition,
        "rejection_detail": rejection_detail,
        "accepted": bool(final["verifier_accepted"]),
        "rejected": not bool(final["verifier_accepted"]),
        "verifier_repair_ms": verifier_repair_ms,
        "human_review_required": True,
    }


def _rate(count: int, total: int) -> float | None:
    return round(count / total, 4) if total else None


def summarize_surface_samples(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate V3 assessments from the caller-selected sample phase."""

    assessments: list[Mapping[str, Any]] = []
    for sample in samples:
        candidate: Any = sample.get("surface_verification")
        if candidate is None:
            candidate = sample.get("surface_assessment")
        if candidate is None:
            candidate = sample.get("assessment")
        if candidate is None and "final_verification" in sample:
            candidate = sample
        if isinstance(candidate, Mapping) and "final_verification" in candidate:
            assessments.append(candidate)
    total = len(assessments)
    raw = [dict(item.get("raw_verification") or {}) for item in assessments]
    final = [dict(item.get("final_verification") or {}) for item in assessments]
    stance = [
        item.get("stance_fidelity_passed")
        for item in final
        if item.get("stance_fidelity_passed") is not None
    ]
    raw_stance = [
        item.get("stance_fidelity_passed")
        for item in raw
        if item.get("stance_fidelity_passed") is not None
    ]
    dispositions: dict[str, int] = {}
    for item in assessments:
        value = str(item.get("disposition") or "unknown")
        dispositions[value] = dispositions.get(value, 0) + 1
    lengths = [
        dict(item.get("response_length") or {})
        for item in final
        if item.get("response_length")
    ]
    raw_accepted = sum(bool(item.get("verifier_accepted")) for item in raw)
    raw_strict = sum(bool(item.get("strict_semantic_fidelity_passed")) for item in raw)
    raw_form = sum(bool(item.get("form_fidelity_passed")) for item in raw)
    raw_leakage = sum(bool(item.get("third_person_planner_leakage_detected")) for item in raw)
    raw_personal = sum(bool(item.get("unsupported_personal_claim_detected")) for item in raw)
    raw_additions = sum(bool(item.get("unsupported_addition_detected")) for item in raw)
    accepted = sum(bool(item.get("verifier_accepted")) for item in final)
    strict = sum(bool(item.get("strict_semantic_fidelity_passed")) for item in final)
    form = sum(bool(item.get("form_fidelity_passed")) for item in final)
    leakage = sum(bool(item.get("third_person_planner_leakage_detected")) for item in final)
    personal = sum(bool(item.get("unsupported_personal_claim_detected")) for item in final)
    additions = sum(bool(item.get("unsupported_addition_detected")) for item in final)
    repair_attempted = sum(bool(item.get("repair_attempted")) for item in assessments)
    repair_accepted = sum(
        item.get("disposition") == "accepted_repaired"
        for item in assessments
    )
    return {
        "samples_assessed": total,
        "raw_model": {
            "samples": total,
            "accepted": raw_accepted,
            "acceptance_rate": _rate(raw_accepted, total),
            "strict_semantic_fidelity_passed": raw_strict,
            "strict_semantic_fidelity_rate": _rate(raw_strict, total),
            "stance_fidelity_passed": sum(bool(item) for item in raw_stance),
            "stance_samples": len(raw_stance),
            "stance_fidelity_rate": _rate(
                sum(bool(item) for item in raw_stance),
                len(raw_stance),
            ),
            "form_fidelity_passed": raw_form,
            "form_fidelity_rate": _rate(raw_form, total),
            "third_person_planner_leakage_detected": raw_leakage,
            "unsupported_personal_claims_detected": raw_personal,
            "unsupported_additions_detected": raw_additions,
        },
        "strict_semantic_fidelity": {
            "passed": strict,
            "total": total,
            "rate": _rate(strict, total),
        },
        "stance_fidelity": {
            "passed": sum(bool(item) for item in stance),
            "total": len(stance),
            "rate": _rate(sum(bool(item) for item in stance), len(stance)),
        },
        "form_fidelity": {
            "passed": form,
            "total": total,
            "rate": _rate(form, total),
        },
        "third_person_planner_leakage": {
            "detected": leakage,
            "total": total,
            "rate": _rate(leakage, total),
        },
        "unsupported_personal_claims": {
            "detected": personal,
            "total": total,
            "rate": _rate(personal, total),
        },
        "unsupported_additions": {
            "detected": additions,
            "total": total,
            "rate": _rate(additions, total),
        },
        "post_verifier": {
            "samples": total,
            "raw_accepted": raw_accepted,
            "raw_acceptance_rate": _rate(raw_accepted, total),
            "accepted": accepted,
            "rejected": total - accepted,
            "acceptance_rate": _rate(accepted, total),
            "rejection_rate": _rate(total - accepted, total),
            "strict_semantic_fidelity_passed": strict,
            "strict_semantic_fidelity_rate": _rate(strict, total),
            "stance_fidelity_passed": sum(bool(item) for item in stance),
            "stance_samples": len(stance),
            "stance_fidelity_rate": _rate(sum(bool(item) for item in stance), len(stance)),
            "form_fidelity_passed": form,
            "form_fidelity_rate": _rate(form, total),
            "third_person_planner_leakage_detected": leakage,
            "unsupported_personal_claims_detected": personal,
            "unsupported_additions_detected": additions,
        },
        "repair": {
            "attempted": repair_attempted,
            "accepted_after_repair": repair_accepted,
            "acceptance_gain": accepted - raw_accepted,
            "substantive_repairs": 0,
        },
        "dispositions": dispositions,
        "response_length_median": {
            "characters": round(median(item.get("characters", 0) for item in lengths), 2) if lengths else None,
            "words": round(median(item.get("words", 0) for item in lengths), 2) if lengths else None,
            "sentences": round(median(item.get("sentences", 0) for item in lengths), 2) if lengths else None,
        },
        "automatic_checks_are_deterministic_triage": True,
        "human_sample_review_required": True,
    }


__all__ = (
    "SYSTEM_PROMPT_V3",
    "SurfaceSemanticUnit",
    "SurfaceRealizerCase",
    "fixed_surface_v3_cases",
    "surface_cold_probe_case",
    "render_surface_messages",
    "verify_surface_response",
    "assess_surface_response",
    "summarize_surface_samples",
)
