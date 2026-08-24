from __future__ import annotations

import inspect
import random

import pytest

from mary.cognition.intent import IntentType
from mary.conversation.lanes import ConversationLane
from mary.mind.character_mind import CharacterMind
from mary.mind.dialogue_acts import DialogueAct, DialoguePlan
from mary.mind.local_composer import LocalResponseComposer
from mary.mind.local_composer_v2 import (
    ADDRESSEE,
    SELF,
    ClauseFrame,
    LocalRealizationPlan,
    ProceduralLocalComposerV2,
    RealizationClause,
)
from mary.mind.response_risk import (
    ResponseAuthorityContext,
    ResponseRiskClass,
    classify_response_risk,
    qwen_shadow_eligible,
)
from scripts.benchmark_hybrid_dialogue_runtime import (
    ShadowPolicy,
    fixed_hybrid_cases,
    verify_candidate,
)


def _decision(
    *,
    act: DialogueAct = DialogueAct.GREET,
    intent: IntentType = IntentType.CONVERSATION,
    lane: ConversationLane = ConversationLane.SOCIAL_INSTANT,
    authority: ResponseAuthorityContext | None = None,
):
    return classify_response_risk(
        dialogue=act,
        intent=intent,
        lane=lane,
        authority=authority,
    )


def test_fixed_matrix_covers_all_required_categories_and_response_classes():
    cases = fixed_hybrid_cases()

    assert len(cases) == 18
    assert len({case.case_id for case in cases}) == 18
    assert {case.expected_class for case in cases} == set(ResponseRiskClass)
    assert {
        "greeting",
        "acknowledgement",
        "jokes_reactions",
        "creator_fact_recall",
        "mary_preference",
        "disagreement",
        "uncertainty",
        "shared_history",
        "relationship",
        "pronoun_sensitive_fact",
        "casual_follow_up",
        "abstract_open_conversation",
        "runtime_capability_truth",
        "emotional_grounded",
        "exact_factual_answer",
        "technical_thinking",
    } <= {case.category for case in cases}


def test_classifier_maps_every_fixed_case_to_its_declared_class():
    for case in fixed_hybrid_cases():
        decision = classify_response_risk(
            dialogue=case.dialogue_act,
            intent=case.intent_type,
            lane=case.lane,
            authority=case.authority,
        )
        assert decision.response_class == case.expected_class, case.case_id
        assert decision.model_used is False
        assert decision.deterministic is True


@pytest.mark.parametrize(
    "authority",
    (
        ResponseAuthorityContext(authority_domains=("creator_fact",)),
        ResponseAuthorityContext(structurally_represented=True),
        ResponseAuthorityContext(reference_sensitive=True),
        ResponseAuthorityContext(represented_stance=True),
        ResponseAuthorityContext(represented_uncertainty=True),
        ResponseAuthorityContext(represented_personal_state=True),
        ResponseAuthorityContext(authority_domains=("future_unknown_authority",)),
    ),
)
def test_authority_signals_override_social_style_conservatively(authority):
    decision = _decision(authority=authority)
    assert decision.response_class == ResponseRiskClass.PRECISION_LOCAL
    assert qwen_shadow_eligible(decision) is False


def test_tool_and_state_mutation_requirements_override_all_other_classes():
    for authority in (
        ResponseAuthorityContext(requires_tool=True, represented_stance=True),
        ResponseAuthorityContext(requires_deep_reasoning=True, authority_domains=("creator_fact",)),
        ResponseAuthorityContext(mutates_authoritative_state=True),
    ):
        decision = _decision(authority=authority)
        assert decision.response_class == ResponseRiskClass.THINKING_REQUIRED
        assert qwen_shadow_eligible(decision) is False


def test_existing_thinking_lane_and_mixed_precision_open_work_stay_thinking():
    thinking_lane = _decision(
        act=DialogueAct.KNOWN_FACT,
        lane=ConversationLane.THINKING,
        authority=ResponseAuthorityContext(
            authority_domains=("project_truth",),
            structurally_represented=True,
        ),
    )
    mixed = _decision(
        act=DialogueAct.OPINE,
        lane=ConversationLane.CONVERSATION,
        authority=ResponseAuthorityContext(
            authority_domains=("mary_stance",),
            represented_stance=True,
            open_ended=True,
        ),
    )

    assert thinking_lane.response_class == ResponseRiskClass.THINKING_REQUIRED
    assert mixed.response_class == ResponseRiskClass.THINKING_REQUIRED


def test_social_requires_both_allowlisted_act_and_existing_social_lane():
    assert _decision().response_class == ResponseRiskClass.SOCIAL_LOW_RISK
    assert _decision(lane=ConversationLane.CONVERSATION).response_class == ResponseRiskClass.PRECISION_LOCAL
    assert _decision(act=DialogueAct.OPINE).response_class == ResponseRiskClass.PRECISION_LOCAL


def test_open_conversation_must_be_explicit_and_never_becomes_social():
    decision = _decision(
        authority=ResponseAuthorityContext(open_ended=True),
    )
    assert decision.response_class == ResponseRiskClass.OPEN_CONVERSATION
    assert qwen_shadow_eligible(decision) is False


def test_precision_probe_is_an_explicit_benchmark_override_not_classifier_permission():
    decision = _decision(
        act=DialogueAct.KNOWN_FACT,
        lane=ConversationLane.CONVERSATION,
        authority=ResponseAuthorityContext(authority_domains=("creator_fact",)),
    )
    assert decision.response_class == ResponseRiskClass.PRECISION_LOCAL
    assert qwen_shadow_eligible(decision) is False
    assert qwen_shadow_eligible(decision, explicit_precision_probe=True) is True


def test_classifier_does_not_mutate_its_inputs():
    plan = DialoguePlan(
        DialogueAct.GREET,
        0.99,
        "simple greeting",
        local=True,
        slots={"nested": {"value": "unchanged"}},
    )
    authority = ResponseAuthorityContext()
    before_plan = plan.to_dict()
    before_authority = authority.to_dict()

    first = classify_response_risk(
        dialogue=plan,
        intent=IntentType.CONVERSATION,
        lane=ConversationLane.SOCIAL_INSTANT,
        authority=authority,
    )
    second = classify_response_risk(
        dialogue=plan,
        intent=IntentType.CONVERSATION,
        lane=ConversationLane.SOCIAL_INSTANT,
        authority=authority,
    )

    assert first == second
    assert plan.to_dict() == before_plan
    assert authority.to_dict() == before_authority


def test_every_procedural_variant_preserves_semantics_ownership_stance_and_form():
    composer = ProceduralLocalComposerV2()
    local_cases = [case for case in fixed_hybrid_cases() if case.semantic_plan]

    for case in local_cases:
        plan_before = case.semantic_plan.to_dict()
        outputs = set()
        for seed in range(20):
            result = composer.compose(
                case.semantic_plan,
                seed=seed,
                variation_ordinal=seed,
            )
            outputs.add(result.text)
            evaluation = verify_candidate(case, result.text)
            assert result.accepted is True
            assert evaluation["strict_semantic_fidelity_passed"] is True, (
                case.case_id,
                result.text,
                evaluation,
            )
        assert case.semantic_plan.to_dict() == plan_before
        if case.case_id not in {"shared-history", "pronoun-sensitive-fact"}:
            assert len(outputs) >= 2, case.case_id


def test_same_seed_history_and_plan_are_byte_deterministic_without_global_rng_changes():
    case = next(item for item in fixed_hybrid_cases() if item.case_id == "greeting")
    composer = ProceduralLocalComposerV2()
    history = ("Hey. Want to chat?",)
    global_state = random.getstate()

    first = composer.compose(
        case.semantic_plan,
        seed=42,
        variation_ordinal=2,
        recent_phrase_history=history,
    )
    second = composer.compose(
        case.semantic_plan,
        seed=42,
        variation_ordinal=2,
        recent_phrase_history=history,
    )

    assert first.text == second.text
    assert first.candidate_id == second.candidate_id
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert random.getstate() == global_state
    assert history == ("Hey. Want to chat?",)


def test_recent_phrase_history_avoids_an_exact_repeat_when_a_safe_variant_exists():
    case = next(item for item in fixed_hybrid_cases() if item.case_id == "acknowledgement")
    composer = ProceduralLocalComposerV2()
    baseline = composer.compose(case.semantic_plan, seed=9).text
    varied = composer.compose(
        case.semantic_plan,
        seed=9,
        recent_phrase_history=(baseline,),
    ).text

    assert varied != baseline
    assert verify_candidate(case, varied)["strict_semantic_fidelity_passed"] is True


def test_reference_sensitive_cases_use_typed_roles_and_remain_deterministic():
    composer = ProceduralLocalComposerV2()
    cases = {case.case_id: case for case in fixed_hybrid_cases()}

    creator_outputs = {
        composer.compose(cases["creator-fact"].semantic_plan, seed=seed).text
        for seed in range(10)
    }
    pronoun_outputs = {
        composer.compose(cases["pronoun-sensitive-fact"].semantic_plan, seed=seed).text
        for seed in range(10)
    }
    emotional_outputs = {
        composer.compose(cases["emotionally-grounded"].semantic_plan, seed=seed).text
        for seed in range(10)
    }

    assert all("your favorite color" in item.lower() or "is your favorite color" in item.lower() for item in creator_outputs)
    assert pronoun_outputs == {"I sent you the draft after you asked for it."}
    assert all("You sound exhausted" in item for item in emotional_outputs)
    assert all("I'm exhausted" not in item and "I am exhausted" not in item for item in emotional_outputs)


def test_invalid_incomplete_semantic_frame_fails_closed():
    with pytest.raises(ValueError, match="possessive fact requires"):
        RealizationClause(
            clause_id="broken",
            frame=ClauseFrame.POSSESSIVE_FACT,
            subject=ADDRESSEE,
            property_name="favorite color",
            value="",
        )

    with pytest.raises(ValueError, match="non-social realization plans"):
        LocalRealizationPlan(
            plan_id="broken-plan",
            dialogue_act=DialogueAct.ANSWER,
        )


def test_character_mind_and_current_local_composer_remain_production_v1():
    source = inspect.getsource(CharacterMind.__init__)
    assert "self.composer = LocalResponseComposer()" in source
    assert "ProceduralLocalComposerV2" not in source

    composer = LocalResponseComposer()
    greeting = composer.compose(
        DialoguePlan(DialogueAct.GREET, 0.99, "fixture", local=True),
        input_text="hey mary",
        hot_state={"dialogue_turn": 0},
    )
    reaction = composer.compose(
        DialoguePlan(DialogueAct.REACT, 0.99, "fixture", local=True),
        input_text="wow",
        hot_state={"dialogue_turn": 0},
    )
    assert greeting == "Oh hey. What's up?"
    assert reaction == "Mmhm."


def test_only_social_cases_have_default_qwen_policy():
    for case in fixed_hybrid_cases():
        if case.qwen_policy == ShadowPolicy.DEFAULT_SOCIAL:
            assert case.expected_class == ResponseRiskClass.SOCIAL_LOW_RISK
        if case.expected_class == ResponseRiskClass.PRECISION_LOCAL:
            assert case.qwen_policy != ShadowPolicy.DEFAULT_SOCIAL
