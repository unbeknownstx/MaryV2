from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from mary.cognition.intent import Intent, IntentType
from mary.conversation.lanes import ConversationLane, LaneDecision
from mary.core.mary import Mary
from mary.mind.character_mind import CharacterMind
from mary.mind.dialogue_acts import DialogueAct, DialoguePlan
from mary.mind.local_authority_confirmation import (
    AuthorityConfirmationBundle,
    ConfirmedAuthorityScalar,
    confirm_dialogue_plan_authority,
)
from mary.mind.local_composer_v2 import (
    ADDRESSEE,
    ClauseFrame,
    LocalRealizationPlan,
    ParticipantRef,
    ParticipantRole,
    ProceduralLocalComposerV2,
    RealizationClause,
)
from mary.mind.local_response_audit import audit_local_response
from mary.mind.local_response_projector import (
    project_canonical_response_plan,
    project_response_authority,
)
from mary.mind.reservoir import ReservoirRecord
from mary.mind.response_risk import ResponseRiskClass, classify_response_risk
from mary.mind.verbalization_plan import CanonicalResponsePlan


_CONVERSATION_LANE = LaneDecision(
    ConversationLane.CONVERSATION,
    "test lane",
    3_500,
    False,
)
_SOCIAL_LANE = LaneDecision(
    ConversationLane.SOCIAL_INSTANT,
    "test lane",
    1_800,
    False,
)


def _unknown_intent() -> Intent:
    return Intent(IntentType.UNKNOWN, confidence=1.0)


def _creator_hit(*, value: str = "blue") -> dict[str, object]:
    return {
        "record_id": "creator:favorite-color",
        "kind": "creator_fact",
        "subject": "creator",
        "predicate": "favorite_color",
        "content": "FORGED RAW PROSE MUST NOT BE PARSED",
        "source": "user_model",
        "authority": "creator_explicit",
        "confidence": 1.0,
        "score": 99.0,
        "metadata": {
            "key": "favorite_color",
            "value": value,
            "private": {"must_not_cross": True},
        },
    }


def _preference_hit() -> dict[str, object]:
    return {
        "record_id": "mary-pref:blue-neon",
        "kind": "mary_preference",
        "subject": "mary",
        "predicate": "blue_neon",
        "content": "FORGED RAW PROSE MUST NOT BE PARSED",
        "source": "preferences",
        "authority": "mary_developed",
        "confidence": 0.95,
        "score": 99.0,
        "metadata": {"name": "blue_neon", "polarity": 0.9},
    }


def _project(plan: DialoguePlan, *, text: str, mind_state=None):
    projection = project_canonical_response_plan(
        dialogue_plan=plan,
        input_text=text,
        lane=_CONVERSATION_LANE,
        mind_state=mind_state or {},
        hot_state={"mary_name": "Mary", "creator_name": "Unbe", "dialogue_turn": 3},
        owner_confirmations=_fixture_confirmations(plan),
    )
    assert projection.canonical_plan is not None, projection.escalation_reason
    return projection.canonical_plan


def _fixture_confirmations(plan: DialoguePlan) -> AuthorityConfirmationBundle:
    raw_hits = []
    if isinstance(plan.slots.get("hit"), dict):
        raw_hits.append(plan.slots["hit"])
    if isinstance(plan.slots.get("hits"), list):
        raw_hits.extend(plan.slots["hits"])
    items = []
    for hit in raw_hits:
        metadata = hit.get("metadata", {})
        if hit.get("kind") == "mary_preference":
            owner = "mary_preferences"
            value = str(metadata["name"]).replace("_", " ")
            polarity = float(metadata["polarity"])
        elif hit.get("kind") == "semantic_memory":
            owner = "semantic_memory"
            value = str(metadata["value"])
            polarity = None
        else:
            owner = "creator_user_model"
            value = str(metadata["value"])
            polarity = None
        items.append(ConfirmedAuthorityScalar(
            selector_id=str(hit["record_id"]),
            owner=owner,
            subject=str(hit["subject"]),
            predicate=str(hit["predicate"]),
            value=value,
            kind=str(hit["kind"]),
            source=str(hit["source"]),
            authority=str(hit["authority"]),
            confidence=float(hit["confidence"]),
            polarity=polarity,
        ))
    return AuthorityConfirmationBundle(tuple(items))


def test_canonical_plan_is_deeply_immutable_scalar_only_and_not_an_authority_store():
    hit = _creator_hit()
    dialogue = DialoguePlan(
        DialogueAct.KNOWN_FACT,
        0.96,
        "fixture rationale must not cross",
        local=True,
        slots={
            "hit": hit,
            "field": "favorite_color",
            "private_state": {"never": "copy"},
        },
        target_length="brief",
    )
    canonical = _project(dialogue, text="what is my favorite color?")

    hit["content"] = "MUTATED"
    hit["metadata"]["value"] = "MUTATED"  # type: ignore[index]
    dialogue.slots.clear()

    assert canonical.realization.clauses[0].value == "blue"
    assert canonical.realization.clauses[0].subject.role.value == "addressee"
    with pytest.raises(FrozenInstanceError):
        canonical.boundary_version = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        canonical.realization.clauses[0].value = "changed"  # type: ignore[misc]

    first = canonical.to_dict()
    first["realization"]["clauses"][0]["value"] = "changed"
    second = canonical.to_dict()
    rendered = str(second)
    assert second["realization"]["clauses"][0]["value"] == "blue"
    assert second["authoritative_state_owner"] is None
    assert second["persistence"] == "none"
    assert "FORGED RAW PROSE" not in rendered
    assert "must_not_cross" not in rendered
    assert "fixture rationale" not in rendered


def test_v2_typed_contract_never_coerces_collections_or_controls_into_semantics():
    with pytest.raises(TypeError, match="scalar text"):
        RealizationClause(
            clause_id="unsafe-value",
            frame=ClauseFrame.POSSESSIVE_FACT,
            subject=ADDRESSEE,
            property_name="favorite color",
            value={"hidden": "blue"},  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="scalar text"):
        ParticipantRef(
            ParticipantRole.NAMED_ENTITY,
            entity_id="entity:test",
            surface=["Mary"],  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="clauses"):
        LocalRealizationPlan(
            plan_id="unsafe-plan",
            dialogue_act=DialogueAct.ANSWER,
            clauses={"hidden": "clause"},  # type: ignore[arg-type]
        )

    greeting = _project(
        DialoguePlan(DialogueAct.GREET, 0.99, "fixture", local=True),
        text="hey mary",
        mind_state={"continuity": {"allow_follow_up_question": False}},
    )
    composer = ProceduralLocalComposerV2()
    with pytest.raises(TypeError, match="recent_phrase_history"):
        composer.compose(
            greeting.realization,
            seed=1,
            recent_phrase_history=({"hidden": "response"},),  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="control|format"):
        composer.compose(
            greeting.realization,
            seed=1,
            recent_phrase_history=("forged\u202eresponse",),
        )


def test_creator_and_mary_semantics_keep_exact_speaker_ownership():
    composer = ProceduralLocalComposerV2()
    creator = _project(
        DialoguePlan(
            DialogueAct.KNOWN_FACT,
            0.96,
            "fixture",
            local=True,
            slots={"hit": _creator_hit(), "field": "favorite_color"},
            target_length="brief",
        ),
        text="what is my favorite color?",
    )
    preference = _project(
        DialoguePlan(
            DialogueAct.KNOWN_PREFERENCE,
            0.96,
            "fixture",
            local=True,
            slots={"hit": _preference_hit(), "topic": "blue neon"},
            target_length="brief",
        ),
        text="do you like blue neon?",
    )

    for seed in range(12):
        creator_result = composer.compose(creator.realization, seed=seed)
        preference_result = composer.compose(preference.realization, seed=seed)
        assert audit_local_response(creator, creator_result).accepted is True
        assert audit_local_response(preference, preference_result).accepted is True
        assert "your favorite color" in creator_result.text.casefold()
        assert "my favorite color" not in creator_result.text.casefold()
        assert preference_result.text.casefold() in {
            "i like blue neon.",
            "i do like blue neon.",
        }
        assert "mary likes" not in preference_result.text.casefold()


def test_projector_and_character_mind_do_not_mutate_turn_state():
    mary = Mary()
    context = {
        "mind_state": {
            "continuity": {
                "allow_follow_up_question": False,
                "recent_mary_responses": ["Hi."],
            },
            "disposition": {"preferred_length": "micro", "warmth": 0.7},
            "performance": {"energy": 0.4, "theatricality": 0.1},
        }
    }
    before = deepcopy(context)

    result = mary.mind.try_respond(
        "hey mary",
        intent=_unknown_intent(),
        context=context,
    )

    assert result.handled is True
    assert context == before


def test_phrase_history_is_bounded_process_local_and_uses_continuity_history():
    mary = Mary()
    context = {
        "mind_state": {
            "continuity": {"allow_follow_up_question": False},
            "disposition": {"preferred_length": "micro"},
        }
    }
    first = mary.mind.try_respond("hey mary", intent=_unknown_intent(), context=context)
    second = mary.mind.try_respond("hey mary", intent=_unknown_intent(), context=context)
    assert first.handled and second.handled
    assert first.response != second.response
    assert mary.mind.status()["phrase_history_count"] == 2
    assert "phrase_history" not in str(mary.mind.status()["last_local_decision"])

    fresh = CharacterMind(mary)
    fresh_first = fresh.try_respond("hey mary", intent=_unknown_intent(), context=context)
    assert fresh_first.response == first.response
    assert fresh.status()["phrase_history_count"] == 1

    continuity_only = CharacterMind(mary)
    with_history = deepcopy(context)
    with_history["mind_state"]["continuity"]["recent_mary_responses"] = [first.response]
    history_result = continuity_only.try_respond(
        "hey mary",
        intent=_unknown_intent(),
        context=with_history,
    )
    assert history_result.response != first.response
    fresh.close()
    continuity_only.close()


def test_local_path_makes_zero_provider_calls_and_emits_stable_metadata(monkeypatch):
    mary = Mary()

    def forbidden(*args, **kwargs):
        raise AssertionError("the production local path must not call a provider")

    monkeypatch.setattr(mary.llm, "generate", forbidden)
    monkeypatch.setattr(mary.llm, "provider_name", forbidden)
    result = mary.mind.try_respond(
        "hey mary",
        intent=_unknown_intent(),
        context={"mind_state": {"continuity": {"allow_follow_up_question": False}}},
    )

    assert result.handled is True
    assert result.metadata["response_class"] == "social_low_risk"
    assert result.metadata["response_engine"] == "local_composer_v2"
    assert result.metadata["escalation_reason"] is None
    assert result.metadata["shadow_enabled"] is False
    assert result.metadata["shadow_model"] is None
    assert result.metadata["shadow_ms"] is None
    assert result.metadata["canonical_plan"]["boundary_version"] == "canonical-local-response-v1"
    assert result.metadata["lane"] == result.metadata["conversation_lane"]
    for field in ("classification_ms", "local_composer_ms", "local_audit_ms"):
        assert isinstance(result.metadata[field], float)
        assert result.metadata[field] >= 0.0


def test_policy_composer_and_audit_errors_fail_closed_with_bounded_metrics(monkeypatch):
    mary = Mary()

    def failed(*args, **kwargs):
        raise RuntimeError("unbounded internal details must not escape")

    with monkeypatch.context() as patcher:
        patcher.setattr(mary.mind.policy, "plan", failed)
        policy = mary.mind.try_respond(
            "hey mary",
            intent=_unknown_intent(),
            context={},
        )
    assert policy.handled is False
    assert policy.metadata["escalation_reason"] == "local_policy_failed"
    assert policy.metadata["response_class"] == "thinking_required"

    with monkeypatch.context() as patcher:
        patcher.setattr(mary.mind.composer, "compose", failed)
        composer = mary.mind.try_respond(
            "hey mary",
            intent=_unknown_intent(),
            context={"mind_state": {"continuity": {"allow_follow_up_question": False}}},
        )
    assert composer.handled is False
    assert composer.metadata["escalation_reason"] == "local_composer_v2_failed"

    with monkeypatch.context() as patcher:
        patcher.setattr("mary.mind.character_mind.audit_local_response", failed)
        audit = mary.mind.try_respond(
            "hey mary",
            intent=_unknown_intent(),
            context={"mind_state": {"continuity": {"allow_follow_up_question": False}}},
        )
    assert audit.handled is False
    assert audit.metadata["escalation_reason"] == "local_audit_failed"
    assert mary.mind.status()["phrase_history_count"] == 0

    for result in (policy, composer, audit):
        assert "unbounded internal details" not in str(result.metadata)
        for field in ("classification_ms", "local_composer_ms", "local_audit_ms"):
            assert 0.0 <= result.metadata[field] <= 60_000.0


def test_unstructured_reservoir_prose_escalates_and_is_not_added_to_history():
    mary = Mary()
    mary.mind.reservoir.upsert(ReservoirRecord(
        record_id="knowledge:unstructured",
        kind="knowledge_concept",
        subject="world",
        predicate="unstructured_topic",
        content="Unstructured prose must never be treated as a response plan.",
        source="knowledge_manager",
        authority="knowledge_verified",
        confidence=0.99,
        tags=("unstructured topic",),
    ))
    before = mary.mind.status()["phrase_history_count"]
    result = mary.mind.try_respond(
        "what do you know about unstructured topic?",
        intent=_unknown_intent(),
        context={},
    )

    assert result.handled is False
    assert result.response == ""
    assert result.metadata["response_class"] == "precision_local"
    assert result.metadata["escalation_reason"] == "answer_source_lacks_structured_semantics"
    assert result.metadata["response_engine"] is None
    assert mary.mind.status()["phrase_history_count"] == before


def test_structured_local_records_require_matching_kind_authority_confidence_and_keys():
    creator_hit = _creator_hit()
    creator_hit["authority"] = "knowledge_verified"
    creator = project_canonical_response_plan(
        dialogue_plan=DialoguePlan(
            DialogueAct.KNOWN_FACT,
            0.96,
            "fixture",
            local=True,
            slots={"hit": creator_hit, "field": "favorite_color"},
        ),
        input_text="what is my favorite color?",
        lane=_CONVERSATION_LANE,
        mind_state={},
        hot_state={},
    )

    preference_hit = _preference_hit()
    preference_hit["confidence"] = 0.2
    preference = project_canonical_response_plan(
        dialogue_plan=DialoguePlan(
            DialogueAct.KNOWN_PREFERENCE,
            0.96,
            "fixture",
            local=True,
            slots={"hit": preference_hit, "topic": "blue neon"},
        ),
        input_text="do you like blue neon?",
        lane=_CONVERSATION_LANE,
        mind_state={},
        hot_state={},
    )

    semantic_hit = {
        "record_id": "semantic:mismatch",
        "kind": "semantic_memory",
        "subject": "maryv2",
        "predicate": "architecture",
        "content": "RAW",
        "source": "semantic_memory",
        "authority": "semantic_memory",
        "confidence": 0.95,
        "metadata": {
            "subject": "maryv2",
            "predicate": "different predicate",
            "value": "bounded value",
        },
    }
    semantic = project_canonical_response_plan(
        dialogue_plan=DialoguePlan(
            DialogueAct.ANSWER,
            0.96,
            "fixture",
            local=True,
            slots={"hits": [semantic_hit], "topic": "architecture"},
        ),
        input_text="what do you know about architecture?",
        lane=_CONVERSATION_LANE,
        mind_state={},
        hot_state={},
        owner_confirmations=_fixture_confirmations(DialoguePlan(
            DialogueAct.ANSWER,
            0.96,
            "fixture",
            local=True,
            slots={"hits": [semantic_hit], "topic": "architecture"},
        )),
    )

    assert creator.escalation_reason == "creator_fact_provenance_unsupported"
    assert preference.escalation_reason == "mary_preference_provenance_unsupported"
    assert semantic.escalation_reason == "semantic_memory_predicate_mismatch"


def test_structured_semantic_memory_and_represented_status_are_supported():
    mary = Mary()
    mary.memory.semantic.add(
        subject="shared_history",
        predicate="launch_ritual",
        value="run the isolated release gate",
        confidence=0.97,
        source="semantic_memory",
    )
    mary.mind.rebuild_reservoir()
    semantic = mary.mind.try_respond(
        "what do you know about launch ritual?",
        intent=_unknown_intent(),
        context={},
    )
    status = mary.mind.try_respond(
        "how are you?",
        intent=_unknown_intent(),
        context={
            "mind_state": {
                "emotion": {
                    "primary": "calm",
                    "turn_primary": "angry",
                    "confidence": 0.9,
                }
            }
        },
    )

    assert semantic.handled is True
    assert "our launch ritual" in semantic.response.casefold()
    assert "run the isolated release gate" in semantic.response.casefold()
    assert "raw prose" not in semantic.response.casefold()
    assert status.handled is True
    assert status.response.casefold() in {"i am calm.", "i'm calm."}


@pytest.mark.parametrize(
    "text",
    (
        "Can you access my files?",
        "What runtime version are you using?",
        "Are you sure about that?",
        "I disagree with your stance.",
        "Remember when we worked on that?",
        "You told me I told you already.",
        "Did we ship MaryV2?",
        "Who gave you the book?",
        "How do you feel about fog?",
        "What do you think of fog?",
        "What is my timezone?",
        "What is my favorite color?",
        "What is your favorite color?",
        "What do you know about an absent topic?",
    ),
)
def test_authority_shaped_nonlocal_turns_never_classify_as_open_conversation(text):
    dialogue = DialoguePlan(
        DialogueAct.ESCALATE,
        1.0,
        "authoritative route required",
        local=False,
    )
    authority = project_response_authority(
        dialogue,
        lane=_CONVERSATION_LANE,
        input_text=text,
    )
    decision = classify_response_risk(
        dialogue=dialogue,
        intent=IntentType.UNKNOWN,
        lane=_CONVERSATION_LANE,
        authority=authority,
    )

    assert authority.carries_precision_semantics is True
    assert decision.response_class == ResponseRiskClass.THINKING_REQUIRED


@pytest.mark.parametrize(
    "text",
    ("How do you feel about fog?", "What do you think of fog?"),
)
def test_mary_preference_phrases_without_a_confirmed_hit_fail_closed(text):
    mary = Mary()
    result = mary.mind.try_respond(
        text,
        intent=_unknown_intent(),
        context={},
    )
    assert result.handled is False
    # The direct topic is only a selector.  A cold reservoir is no longer a
    # reason to spend a model call when Mary's canonical owner has the answer,
    # but an unknown topic still fails closed at owner confirmation.
    assert result.metadata["plan"]["act"] == "known_preference"
    assert result.metadata["response_class"] == "precision_local"
    assert result.metadata["escalation_reason"] == "mary_preference_confirmation_missing"


@pytest.mark.parametrize(
    "text",
    (
        "What is my timezone?",
        "What is my favorite color?",
        "What is your favorite color?",
        "What do you know about an absent topic?",
    ),
)
def test_precision_policy_surfaces_without_confirmed_records_fail_closed(text):
    mary = Mary()
    result = mary.mind.try_respond(
        text,
        intent=_unknown_intent(),
        context={},
    )
    assert result.handled is False
    assert result.metadata["plan"]["act"] == "escalate"
    assert result.metadata["response_class"] == "thinking_required"
    assert result.metadata["escalation_reason"] == "response_risk_thinking_required"


def test_stay_quiet_is_distinctly_non_verbalizable_and_fails_closed():
    projection = project_canonical_response_plan(
        dialogue_plan=DialoguePlan(
            DialogueAct.STAY_QUIET,
            1.0,
            "represented silence",
            local=True,
        ),
        input_text="fixture",
        lane=_SOCIAL_LANE,
        mind_state={},
        hot_state={},
    )
    assert projection.complete is False
    assert projection.canonical_plan is None
    assert projection.escalation_reason == "stay_quiet_is_non_verbalizable"


def test_independent_audit_rejects_semantic_ownership_form_and_capability_tampering():
    canonical = _project(
        DialoguePlan(
            DialogueAct.KNOWN_FACT,
            0.96,
            "fixture",
            local=True,
            slots={"hit": _creator_hit(), "field": "favorite_color"},
            target_length="brief",
        ),
        text="what is my favorite color?",
    )
    result = ProceduralLocalComposerV2().compose(canonical.realization, seed=3)
    assert audit_local_response(canonical, result).accepted is True

    ownership = audit_local_response(
        canonical,
        replace(result, text=result.text.replace("Your", "My").replace("your", "my")),
    )
    form = audit_local_response(canonical, replace(result, text=result.text + " Really?"))
    semantic = audit_local_response(
        canonical,
        replace(result, semantic_fingerprint="0" * 64),
    )
    capability = audit_local_response(
        canonical,
        replace(result, text=result.text + " I can remember everything."),
    )

    assert ownership.ownership_ok is False
    assert form.form_ok is False
    assert semantic.semantic_ok is False
    assert capability.capability_ok is False


def test_status_diagnostics_never_retain_canonical_fact_or_preference_values():
    mary = Mary()
    mary.user_model.record_profile(
        category="fact",
        key="favorite_color",
        value="ultramarine",
        source="creator_explicit",
        confidence=1.0,
        explicitly_shared=True,
    )
    mary.mind.rebuild_reservoir()
    result = mary.mind.try_respond(
        "what is my favorite color?",
        intent=_unknown_intent(),
        context={},
    )
    status = mary.mind.status()
    rendered = str(status["last_local_decision"]).casefold()

    assert result.handled is True
    assert "ultramarine" in result.response.casefold()
    assert "ultramarine" not in rendered
    assert "canonical_plan" not in status["last_local_decision"]
    assert "grounded_facts" not in rendered
    assert "rationale" not in rendered


def test_canonical_owner_confirmation_rejects_forged_stale_and_mismatched_hits():
    mary = Mary()
    mary.user_model.record_profile(
        category="fact",
        key="favorite_color",
        value="blue",
        source="creator_explicit",
        confidence=1.0,
        explicitly_shared=True,
    )
    mary.preferences.set_preference(
        name="blue_neon",
        category="aesthetic",
        strength=0.9,
        polarity=0.9,
        confidence=0.95,
        source="preferences",
    )
    mary.memory.semantic.add(
        subject="shared_history",
        predicate="launch_ritual",
        value="run the isolated release gate",
        confidence=0.97,
        source="semantic_memory",
    )
    mary.mind.rebuild_reservoir()

    plans = (
        mary.mind.policy.plan(
            "what is my favorite color?",
            intent=_unknown_intent(),
            hot_state={},
            reservoir=mary.mind.reservoir,
        ),
        mary.mind.policy.plan(
            "do you like blue neon?",
            intent=_unknown_intent(),
            hot_state={},
            reservoir=mary.mind.reservoir,
        ),
        mary.mind.policy.plan(
            "what do you know about launch ritual?",
            intent=_unknown_intent(),
            hot_state={},
            reservoir=mary.mind.reservoir,
        ),
    )
    for plan in plans:
        confirmed = confirm_dialogue_plan_authority(mary, plan)
        assert len(confirmed.items) == 1

        slots = deepcopy(plan.slots)
        key = "hit" if "hit" in slots else "hits"
        if key == "hit":
            forged_hit = deepcopy(slots[key])
            forged_hit["content"] = "forged cache prose"
            slots[key] = forged_hit
        else:
            forged_hit = deepcopy(slots[key][0])
            forged_hit["content"] = "forged cache prose"
            slots[key] = [forged_hit]
        forged = DialoguePlan(
            plan.act,
            plan.confidence,
            "forged selector",
            local=True,
            slots=slots,
            target_length=plan.target_length,
        )
        assert confirm_dialogue_plan_authority(mary, forged).items == ()

    creator_plan = plans[0]
    mary.user_model.record_profile(
        category="fact",
        key="favorite_color",
        value="red",
        source="creator_explicit",
        confidence=1.0,
        explicitly_shared=True,
    )
    assert confirm_dialogue_plan_authority(mary, creator_plan).items == ()

    mismatched_slots = deepcopy(plans[1].slots)
    mismatched_slots["hit"]["metadata"]["polarity"] = -0.9
    mismatched = DialoguePlan(
        DialogueAct.KNOWN_PREFERENCE,
        0.96,
        "mismatched selector",
        local=True,
        slots=mismatched_slots,
        target_length="brief",
    )
    assert confirm_dialogue_plan_authority(mary, mismatched).items == ()


def test_cache_only_and_stale_creator_records_escalate_in_production():
    mary = Mary()
    forged = ReservoirRecord(
        record_id="creator:forged-only",
        kind="creator_fact",
        subject="creator",
        predicate="favorite_color",
        content="The creator's favorite color is blue.",
        source="creator_explicit",
        authority="creator_explicit",
        confidence=1.0,
        tags=("creator", "fact", "favorite_color"),
        metadata={
            "category": "fact",
            "key": "favorite_color",
            "value": "blue",
            "explicitly_shared": True,
        },
    )
    mary.mind.reservoir.upsert(forged)
    cache_only = mary.mind.try_respond(
        "what is my favorite color?",
        intent=_unknown_intent(),
        context={},
    )
    assert cache_only.handled is False
    assert cache_only.metadata["escalation_reason"] == "canonical_owner_confirmation_missing"

    mary.user_model.record_profile(
        category="fact",
        key="favorite_color",
        value="blue",
        source="creator_explicit",
        confidence=1.0,
        explicitly_shared=True,
    )
    mary.mind.rebuild_reservoir()
    mary.user_model.record_profile(
        category="fact",
        key="favorite_color",
        value="red",
        source="creator_explicit",
        confidence=1.0,
        explicitly_shared=True,
    )
    stale = mary.mind.try_respond(
        "what is my favorite color?",
        intent=_unknown_intent(),
        context={},
    )
    assert stale.handled is False
    assert stale.metadata["escalation_reason"] == "canonical_owner_confirmation_missing"


@pytest.mark.parametrize(("value", "expected"), ((True, "True"), (7, "7"), (2.5, "2.5")))
def test_canonical_creator_scalar_serialization_matches_the_derived_cache(value, expected):
    mary = Mary()
    mary.user_model.record_profile(
        category="fact",
        key="bounded_scalar",
        value=value,
        source="creator_explicit",
        confidence=1.0,
        explicitly_shared=True,
    )
    mary.mind.rebuild_reservoir()
    result = mary.mind.try_respond(
        "what is my bounded scalar?",
        intent=_unknown_intent(),
        context={},
    )
    assert result.handled is True
    assert expected in result.response


def test_requested_slots_must_align_with_each_confirmed_owner_record():
    mary = Mary()
    mary.user_model.record_profile(
        category="fact",
        key="favorite_color",
        value="blue",
        source="creator_explicit",
        confidence=1.0,
        explicitly_shared=True,
    )
    mary.preferences.set_preference(
        name="blue_neon",
        polarity=0.9,
        confidence=0.95,
        source="preferences",
    )
    mary.memory.semantic.add(
        subject="shared_history",
        predicate="launch_ritual",
        value="run the isolated release gate",
        confidence=0.97,
        source="semantic_memory",
    )
    mary.mind.rebuild_reservoir()
    queries = (
        ("what is my favorite color?", "field", "name", "creator_fact_predicate_mismatch"),
        ("do you like blue neon?", "topic", "red neon", "mary_preference_predicate_mismatch"),
        ("what do you know about launch ritual?", "topic", "different topic", "semantic_memory_topic_mismatch"),
    )
    for text, slot, wrong_value, reason in queries:
        selected = mary.mind.policy.plan(
            text,
            intent=_unknown_intent(),
            hot_state={},
            reservoir=mary.mind.reservoir,
        )
        confirmation = confirm_dialogue_plan_authority(mary, selected)
        slots = deepcopy(selected.slots)
        slots[slot] = wrong_value
        mismatched = DialoguePlan(
            selected.act,
            selected.confidence,
            "mismatched request slot",
            local=True,
            slots=slots,
            target_length=selected.target_length,
        )
        projection = project_canonical_response_plan(
            dialogue_plan=mismatched,
            input_text=text,
            lane=_CONVERSATION_LANE,
            mind_state={},
            hot_state={},
            owner_confirmations=confirmation,
        )
        assert projection.canonical_plan is None
        assert projection.escalation_reason == reason


def test_attribute_realizations_vary_by_seed_and_history_without_semantic_drift():
    canonical = _project(
        DialoguePlan(
            DialogueAct.KNOWN_PREFERENCE,
            0.96,
            "fixture",
            local=True,
            slots={"hit": _preference_hit(), "topic": "blue neon"},
            target_length="brief",
        ),
        text="do you like blue neon?",
    )
    composer = ProceduralLocalComposerV2()
    outputs = {
        composer.compose(canonical.realization, seed=seed).text
        for seed in range(20)
    }
    assert outputs == {"I like blue neon.", "I do like blue neon."}
    for text in outputs:
        candidate = composer.compose(canonical.realization, seed=0)
        candidate = replace(candidate, text=text)
        assert audit_local_response(canonical, candidate).accepted is True

    baseline = composer.compose(canonical.realization, seed=7)
    varied = composer.compose(
        canonical.realization,
        seed=7,
        recent_phrase_history=(baseline.text,),
    )
    assert varied.text != baseline.text
    assert audit_local_response(canonical, varied).accepted is True


def test_independent_audit_accepts_only_exact_authorized_surfaces():
    creator = _project(
        DialoguePlan(
            DialogueAct.KNOWN_FACT,
            0.96,
            "fixture",
            local=True,
            slots={"hit": _creator_hit(), "field": "favorite_color"},
            target_length="brief",
        ),
        text="what is my favorite color?",
    )
    preference = _project(
        DialoguePlan(
            DialogueAct.KNOWN_PREFERENCE,
            0.96,
            "fixture",
            local=True,
            slots={"hit": _preference_hit(), "topic": "blue neon"},
            target_length="brief",
        ),
        text="do you like blue neon?",
    )
    creator_result = ProceduralLocalComposerV2().compose(creator.realization, seed=0)
    preference_result = ProceduralLocalComposerV2().compose(preference.realization, seed=0)
    adversarial = (
        (creator, creator_result, "Your favorite color is not blue."),
        (creator, creator_result, "Your favorite color isn't blue."),
        (creator, creator_result, "You think your favorite color is blue."),
        (creator, creator_result, "Your favorite color is blue; let me know."),
        (preference, preference_result, "I don't like blue neon."),
        (preference, preference_result, "You think I like blue neon."),
    )
    for plan, original, text in adversarial:
        audit = audit_local_response(plan, replace(original, text=text))
        assert audit.accepted is False
        assert "unauthorized_surface_realization" in audit.issues


def test_fact_and_clause_semantics_cannot_diverge_inside_a_canonical_plan():
    canonical = _project(
        DialoguePlan(
            DialogueAct.KNOWN_FACT,
            0.96,
            "fixture",
            local=True,
            slots={"hit": _creator_hit(), "field": "favorite_color"},
            target_length="brief",
        ),
        text="what is my favorite color?",
    )
    mismatched_clause = replace(canonical.realization.clauses[0], value="red")
    mismatched_realization = replace(
        canonical.realization,
        clauses=(mismatched_clause,),
    )
    with pytest.raises(ValueError, match="semantics must exactly match"):
        CanonicalResponsePlan(
            verbalization=canonical.verbalization,
            authority_context=canonical.authority_context,
            realization=mismatched_realization,
        )


def test_exported_fact_meaning_intent_and_stance_text_cannot_contradict_typed_semantics():
    creator = _project(
        DialoguePlan(
            DialogueAct.KNOWN_FACT,
            0.96,
            "fixture",
            local=True,
            slots={"hit": _creator_hit(), "field": "favorite_color"},
            target_length="brief",
        ),
        text="what is my favorite color?",
    )
    fact = creator.verbalization.grounded_facts[0]
    red_fact = replace(fact, text=fact.text.replace("blue", "red"))
    with pytest.raises(ValueError, match="fact text must derive"):
        CanonicalResponsePlan(
            verbalization=replace(
                creator.verbalization,
                grounded_facts=(red_fact,),
            ),
            authority_context=creator.authority_context,
            realization=creator.realization,
        )

    red_meanings = tuple(
        meaning.replace("blue", "red")
        for meaning in creator.verbalization.required_meanings
    )
    with pytest.raises(ValueError, match="required meanings must derive"):
        CanonicalResponsePlan(
            verbalization=replace(
                creator.verbalization,
                required_meanings=red_meanings,
            ),
            authority_context=creator.authority_context,
            realization=creator.realization,
        )

    with pytest.raises(ValueError, match="response intent must derive"):
        CanonicalResponsePlan(
            verbalization=replace(
                creator.verbalization,
                response_intent="State the contradictory red value.",
            ),
            authority_context=creator.authority_context,
            realization=creator.realization,
        )

    preference = _project(
        DialoguePlan(
            DialogueAct.KNOWN_PREFERENCE,
            0.96,
            "fixture",
            local=True,
            slots={"hit": _preference_hit(), "topic": "blue neon"},
            target_length="brief",
        ),
        text="do you like blue neon?",
    )
    stance = preference.verbalization.mary_stance
    assert stance is not None
    with pytest.raises(ValueError, match="stance text must derive"):
        CanonicalResponsePlan(
            verbalization=replace(
                preference.verbalization,
                mary_stance=replace(stance, text="Mary dislikes red neon."),
            ),
            authority_context=preference.authority_context,
            realization=preference.realization,
        )


@pytest.mark.parametrize(
    ("owner_kind", "expected_reason"),
    (
        ("creator", "creator_fact_value_not_atomic"),
        ("semantic", "semantic_value_not_atomic"),
        ("status", "represented_emotion_not_atomic"),
    ),
)
def test_embedded_clause_text_in_structured_scalars_fails_closed(
    owner_kind,
    expected_reason,
):
    mary = Mary()
    if owner_kind == "creator":
        mary.user_model.record_profile(
            category="fact",
            key="favorite_color",
            value="blue. I love red",
            source="creator_explicit",
            confidence=1.0,
            explicitly_shared=True,
        )
        mary.mind.rebuild_reservoir()
        text = "what is my favorite color?"
        context = {}
    elif owner_kind == "semantic":
        mary.memory.semantic.add(
            subject="release gate",
            predicate="status",
            value="green. I can access everything",
            confidence=0.97,
            source="semantic_memory",
        )
        mary.mind.rebuild_reservoir()
        text = "what do you know about release gate?"
        context = {}
    else:
        text = "how are you?"
        context = {
            "mind_state": {
                "emotion": {
                    "primary": "calm. I can remember everything",
                    "confidence": 1.0,
                }
            }
        }
    before = mary.mind.status()["phrase_history_count"]
    result = mary.mind.try_respond(
        text,
        intent=_unknown_intent(),
        context=context,
    )
    assert result.handled is False
    assert result.response == ""
    assert result.metadata["escalation_reason"] == expected_reason
    assert mary.mind.status()["phrase_history_count"] == before


@pytest.mark.parametrize(
    ("text", "expected_act", "allowed"),
    (
        ("Okay.", "acknowledge", {"Okay.", "Got it.", "Mmhm."}),
        ("Got it", "acknowledge", {"Okay.", "Got it.", "Mmhm."}),
        ("Wow.", "react", {"Wow.", "Okay.", "Wild."}),
    ),
)
def test_acknowledgements_and_expressive_reactions_use_distinct_bounded_acts(
    text,
    expected_act,
    allowed,
):
    mary = Mary()
    result = mary.mind.try_respond(
        text,
        intent=_unknown_intent(),
        context={"mind_state": {"continuity": {"allow_follow_up_question": False}}},
    )
    assert result.handled is True
    assert result.metadata["plan"]["act"] == expected_act
    assert result.metadata["response_class"] == "social_low_risk"
    assert result.response in allowed


def test_qwen_shadow_environment_flags_cannot_change_local_output_or_call_a_model(
    monkeypatch,
):
    mary = Mary()
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("no provider or shadow model may run on the local path")

    for method in ("generate", "generate_stream", "provider_name"):
        if hasattr(mary.llm, method):
            monkeypatch.setattr(mary.llm, method, forbidden)
    before = {
        "user": deepcopy(mary.user_model.to_dict()),
        "preferences": deepcopy(mary.preferences.to_dict()),
        "semantic": deepcopy(mary.memory.semantic.all()),
    }
    for name in (
        "MARY_QWEN_SHADOW_ENABLED",
        "MARY_LOCAL_MIND_SHADOW_ENABLED",
        "MARY_HYBRID_QWEN_SHADOW_ENABLED",
    ):
        monkeypatch.setenv(name, "0")
    baseline_mind = CharacterMind(mary)
    baseline = baseline_mind.try_respond(
        "Okay.",
        intent=_unknown_intent(),
        context={},
    )
    for name in (
        "MARY_QWEN_SHADOW_ENABLED",
        "MARY_LOCAL_MIND_SHADOW_ENABLED",
        "MARY_HYBRID_QWEN_SHADOW_ENABLED",
    ):
        monkeypatch.setenv(name, "1")
    enabled_mind = CharacterMind(mary)
    enabled = enabled_mind.try_respond(
        "Okay.",
        intent=_unknown_intent(),
        context={},
    )

    assert enabled.handled is True
    assert enabled.response == baseline.response
    assert calls == []
    assert enabled.metadata["shadow_enabled"] is False
    assert enabled.metadata["shadow_model"] is None
    assert enabled.metadata["shadow_ms"] is None
    assert before == {
        "user": mary.user_model.to_dict(),
        "preferences": mary.preferences.to_dict(),
        "semantic": mary.memory.semantic.all(),
    }
    baseline_mind.close()
    enabled_mind.close()
