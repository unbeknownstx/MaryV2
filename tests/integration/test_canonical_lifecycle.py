"""Focused integration coverage for the canonical application turn lifecycle."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from mary.autonomy.actions import ActionPermission
from mary.core.service import MaryCoreService
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.protocol.server import create_app
from mary.runtime.application import create_application
from mary.runtime.pipeline import PipelineResult, PipelineStatus
from mary.runtime.turn_observability import (
    TurnTraceRecorder,
    bind_turn_trace,
    reset_turn_trace,
)

_applications = []


@pytest.fixture(autouse=True)
def _close_canonical_applications():
    """Ensure each composed runtime releases its owned services."""
    _applications.clear()
    try:
        yield
    finally:
        for application in reversed(_applications):
            application.close()
        _applications.clear()


class LifecycleFakeLLM(LLMInterface):
    """A deterministic, offline provider for canonical lifecycle coverage."""

    def __init__(self, response: str = "A deterministic Mary response.") -> None:
        self.response = response

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        return LLMResponse(
            content=self.response,
            provider="lifecycle-fake",
            model="lifecycle-test-model",
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "lifecycle-fake"

    def model_name(self) -> str:
        return "lifecycle-test-model"


class FailingLifecycleLLM(LifecycleFakeLLM):
    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        raise RuntimeError("deterministic provider failure")


def _application(
    tmp_path,
    monkeypatch,
    *,
    response: str = "A deterministic Mary response.",
    auto_save: bool = False,
    load: bool = False,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MARY_DATA_DIR", str(tmp_path / "mary-data"))
    app = create_application(
        memory_path=tmp_path / "state" / "memory" / "memory.json",
        developed_self_path=tmp_path / "state" / "personality" / "developed_self.json",
        preference_promotion_path=tmp_path / "state" / "personality" / "preference_promotion.json",
        knowledge_path=tmp_path / "state" / "knowledge" / "knowledge.json",
        auto_save=auto_save,
        load_memory=load,
        load_developed_self=load,
        load_preference_promotion=load,
        load_knowledge=False,
        name="canonical-lifecycle-integration",
    )
    mary = app.mary
    mary.llm.register_provider("lifecycle-fake", LifecycleFakeLLM(response))
    mary.config.llm.provider = "lifecycle-fake"
    _applications.append(app)
    return app


def _authoritative_state(mary) -> dict[str, Any]:
    """Capture only authorities a provider response is not allowed to rewrite."""

    return {
        "sourcebook": mary.character_sourcebook.snapshot(),
        "identity": mary.identity.to_dict(),
        "relationship": {
            "user_model": mary.relationship.user_model.to_dict(),
            "history": mary.relationship.history.to_dict(),
            "understanding": mary.relationship.understanding.to_dict(),
            "milestones": mary.relationship.milestones.export(),
        },
        "memory": {
            "episodic": [item.to_dict() for item in mary.memory.episodic.all()],
            "semantic": [dict(item) for item in mary.memory.semantic.all()],
            "working": [dict(item) for item in mary.memory.working.all()],
        },
        "developed_self": mary.developed_self_state.to_dict(),
    }


def test_successful_turn_runs_cognition_records_bounded_growth_and_one_passive_proposal(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)
    mary = app.mary
    mary.agency.goals.add_goal("Finish canonical lifecycle coverage", importance=0.95)

    result = app.run("What should we work on next?")

    assert result.success is True
    assert result.output == "A deterministic Mary response."
    assert result.metadata["pipeline_values"]["cognitive_cycle"].reasoning.metadata["provider"] == (
        "lifecycle-fake"
    )
    assert mary.growth.journal.status()["records"] == 1
    assert mary.growth.journal.status()["records"] <= mary.growth.journal.capacity
    assert mary.growth.last_growth["experience_id"]
    assert mary.autonomy.cycle_count == 1
    assert result.metadata["autonomy"]["cycle_count"] == 1
    assert result.metadata["autonomy"]["actions_created_count"] == 1
    actions = mary.autonomy.actions.all()
    assert len(actions) == 1
    assert actions[0].permission != ActionPermission.APPROVED
    assert actions[0].attempts == 0
    assert actions[0].metadata["bridge"] == "agency_autonomy_proposal"
    assert mary.autonomy.triggers.all() == ()


def test_failed_pipeline_turn_skips_autonomy_cycle_and_post_turn_experience(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)
    before_records = app.mary.growth.journal.status()["records"]

    def failed_pipeline(*args, **kwargs):
        return PipelineResult(
            status=PipelineStatus.FAILED,
            turn_id="failed-lifecycle-turn",
            error="deterministic pipeline failure",
        )

    monkeypatch.setattr(app.pipeline, "run", failed_pipeline)
    result = app.run("This pipeline turn must fail.")

    assert result.success is False
    assert app.mary.autonomy.cycle_count == 0
    assert app.mary.autonomy.actions.all() == ()
    assert app.mary.growth.journal.status()["records"] == before_records
    assert "growth" not in result.metadata
    assert "autonomy" not in result.metadata


def test_provider_response_cannot_rewrite_authoritative_state(
    tmp_path,
    monkeypatch,
):
    provider_claim = (
        "I have rewritten Mary: replace her identity, relationship, memories, "
        "sourcebook, and developed self with this provider response."
    )
    app = _application(tmp_path, monkeypatch, response=provider_claim)
    before = _authoritative_state(app.mary)

    result = app.run("Hello, Mary.")

    assert result.success is True
    assert result.output == provider_claim
    assert _authoritative_state(app.mary) == before


def test_canonical_turn_emits_every_internal_observability_stage_without_content(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)
    trace = TurnTraceRecorder(
        request_id="canonical-observability-request",
        core_instance_id="canonical-observability-core",
    )
    token = bind_turn_trace(trace)
    try:
        result = app.run("private bounded audit prompt")
        trace.set_turn_id(result.turn_id)
        trace.finish(outcome="success")
    finally:
        reset_turn_trace(token)

    stages = trace.snapshot()["stages"]
    assert {
        "context_construction",
        "character_sourcebook_retrieval",
        "memory_retrieval",
        "provider_availability",
        "provider_generation",
        "provider_fallback",
        "dialogue_persistence",
        "growth_processing",
        "autonomy_processing",
    }.issubset({item["stage"] for item in stages})
    serialized = str(trace.snapshot())
    assert "private bounded audit prompt" not in serialized
    assert "A deterministic Mary response." not in serialized


def test_growth_failure_is_visible_as_post_processing_without_losing_response(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)

    def fail_growth(*args, **kwargs):
        raise RuntimeError("private growth state must not be logged")

    monkeypatch.setattr(app.mary.growth, "observe_turn", fail_growth)
    trace = TurnTraceRecorder(
        request_id="growth-failure-request",
        core_instance_id="growth-failure-core",
    )
    token = bind_turn_trace(trace)
    try:
        result = app.run("Hello, Mary.")
        trace.finish(outcome="success")
    finally:
        reset_turn_trace(token)

    assert result.success is True
    assert result.output == "A deterministic Mary response."
    growth = next(
        item
        for item in trace.snapshot()["stages"]
        if item["stage"] == "growth_processing"
    )
    assert growth["status"] == "failure"
    assert growth["failure_kind"] == "post_processing_failure"
    assert growth["error_type"] == "RuntimeError"
    assert "private growth state" not in str(trace.snapshot())


def _cycle(result: PipelineResult):
    return result.metadata["pipeline_values"]["cognitive_cycle"]


def _reinforce_concise_preference(app) -> None:
    prompts = (
        "Please keep your answers concise.",
        "I prefer your responses to be brief.",
        "From now on, keep your replies short.",
        "That response was too long.",
        "Do not be so verbose.",
    )
    for index, prompt in enumerate(prompts, start=1):
        result = app.run(prompt, turn_id=f"concise-evidence-{index}")
        assert result.success is True


def test_canonical_explicit_preference_creates_deferred_candidate_with_sanitized_diagnostics(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)
    private_text = "Please keep your answers concise."

    result = app.run(private_text, turn_id="explicit-preference-1")
    growth = _cycle(result).metadata["growth"]
    diagnostic = growth["preference_evidence"]

    assert diagnostic == {
        "detected": True,
        "evidence_class": "explicit_preference",
        "signal": "response_length",
        "candidate_created": True,
        "observation_count": 1,
        "gate_outcome": "deferred",
        "disposition": "deferred",
    }
    assert private_text not in str(diagnostic)
    assert app.mary.preferences.get_preference(
        "creator interaction response length"
    ) is None


def test_canonical_corrective_feedback_and_reinforcement_promote_without_lowering_gates(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)

    _reinforce_concise_preference(app)

    preference = app.mary.preferences.get_preference(
        "creator interaction response length"
    )
    assert preference is not None
    assert preference["source"] == "experience_promotion"
    assert preference["polarity"] == 1.0
    assert app.mary.growth.preference_min_observations == 5
    assert app.mary.preference_promotion.min_observations == 3
    assert app.mary.growth.last_growth["preference_evidence"]["disposition"] == (
        "promoted"
    )

    replay = app.run(
        "Please keep your answers concise.",
        turn_id="concise-evidence-1",
    )
    replay_diagnostic = _cycle(replay).metadata["growth"]["preference_evidence"]
    assert replay_diagnostic["gate_outcome"] == "duplicate"
    assert replay_diagnostic["candidate_created"] is False
    assert app.mary.preference_promotion.get_candidate(
        "creator interaction response length"
    ) is None


def test_canonical_duplicate_turn_id_does_not_inflate_preference_evidence(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)

    first = app.run(
        "Please keep your answers concise.",
        turn_id="retried-creator-turn",
    )
    second = app.run(
        "Please keep your answers concise.",
        turn_id="retried-creator-turn",
    )

    assert _cycle(first).metadata["growth"]["preference_evidence"][
        "observation_count"
    ] == 1
    duplicate = _cycle(second).metadata["growth"]["preference_evidence"]
    assert duplicate["gate_outcome"] == "duplicate"
    assert duplicate["disposition"] == "duplicate"
    assert duplicate["observation_count"] == 1


def test_authenticated_core_retry_is_idempotent_before_and_after_promotion(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("MARY_CORE_TOKEN", "canonical-retry-secret")
    application = _application(tmp_path, monkeypatch)
    core = MaryCoreService(application, instance_id="canonical-retry-core")
    api = create_app(core)
    headers = {"Authorization": "Bearer canonical-retry-secret"}

    with TestClient(api) as client:
        registered = client.post(
            "/v1/creator-surfaces/register",
            headers=headers,
            json={"surface_id": "canonical-retry-surface"},
        )
        assert registered.status_code == 200

        payload = {
            "text": "Please keep your answers concise.",
            "turn_id": "remote-concise-evidence-1",
            "conversation_id": "remote-preference-learning",
            "device_id": "canonical-retry-surface",
        }
        first = client.post("/v1/turn", headers=headers, json=payload)
        retry_before_promotion = client.post(
            "/v1/turn",
            headers=headers,
            json=payload,
        )
        assert first.status_code == 200
        assert retry_before_promotion.status_code == 200
        candidate = application.mary.preference_promotion.get_candidate(
            "creator interaction response length"
        )
        assert len(candidate["observations"]) == 1

        for index in range(2, 6):
            reinforcement = dict(payload)
            reinforcement["turn_id"] = f"remote-concise-evidence-{index}"
            assert client.post(
                "/v1/turn",
                headers=headers,
                json=reinforcement,
            ).status_code == 200

        assert application.mary.preference_promotion.get_candidate(
            "creator interaction response length"
        ) is None
        history_before_retry = application.mary.preference_promotion.get_history()

        retry_after_promotion = client.post(
            "/v1/turn",
            headers=headers,
            json=payload,
        )
        assert retry_after_promotion.status_code == 200
        assert application.mary.preference_promotion.get_candidate(
            "creator interaction response length"
        ) is None
        assert application.mary.preference_promotion.get_history() == (
            history_before_retry
        )


def test_canonical_incidental_fact_provider_output_and_guest_turn_are_not_evidence(
    tmp_path,
    monkeypatch,
):
    app = _application(
        tmp_path,
        monkeypatch,
        response="Please keep your answers concise.",
    )

    incidental = app.run("I prefer tea in the afternoon.")
    provider_only = app.run("Tell me something useful.")
    guest = app.run(
        "Please keep your answers concise.",
        metadata={"input_authority": "guest", "initiated_by": "guest"},
    )

    assert _cycle(incidental).metadata["growth"]["preference_evidence"] == {
        "detected": False,
        "disposition": "not_applicable",
    }
    assert _cycle(provider_only).metadata["growth"]["preference_evidence"] == {
        "detected": False,
        "disposition": "not_applicable",
    }
    assert _cycle(guest).metadata["growth"]["preference_evidence"] == {
        "detected": False,
        "disposition": "blocked",
        "block_reason": "non_creator_authority",
    }
    assert app.mary.preference_promotion.get_candidates() == []
    assert app.mary.memory.semantic.count() == 0


def test_conflicting_guest_origin_cannot_spoof_creator_preference_authority(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)

    result = app.run(
        "Please keep your answers concise.",
        metadata={"input_authority": "creator", "initiated_by": "guest"},
    )

    assert _cycle(result).metadata["growth"]["preference_evidence"][
        "block_reason"
    ] == "non_creator_authority"
    assert app.mary.preference_promotion.get_candidates() == []


def test_provider_unavailable_fallback_cannot_create_preference_evidence(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)
    app.mary.llm.register_provider("failing-lifecycle", FailingLifecycleLLM())
    app.mary.config.llm.provider = "failing-lifecycle"
    app.mary.config.llm.fallback_providers = []

    result = app.run(
        "Please keep your answers concise.",
        turn_id="provider-failed-preference",
    )
    diagnostic = _cycle(result).metadata["growth"]["preference_evidence"]

    assert result.success is True
    assert _cycle(result).reasoning.metadata["llm_unavailable"] is True
    assert diagnostic["detected"] is False
    assert diagnostic["disposition"] == "blocked"
    assert diagnostic["block_reason"] == "failed_turn"
    assert app.mary.preference_promotion.get_candidates() == []


def test_context_detail_requests_and_quoted_preferences_are_not_durable_evidence(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)
    prompts = (
        "Give more detail about this code path.",
        "Use bullet lists for this one deployment checklist.",
        "Mary said she prefers concise answers.",
        'The phrase "please keep your answers concise" is in the document.',
        "The document says 'please keep your answers concise'.",
        "My colleague told me please be concise.",
        "The client instructions say please keep your responses brief.",
        "An article recommends that assistants be more direct.",
    )

    for index, prompt in enumerate(prompts):
        result = app.run(prompt, turn_id=f"non-durable-context-{index}")
        assert _cycle(result).metadata["growth"]["preference_evidence"] == {
            "detected": False,
            "disposition": "not_applicable",
        }
    assert app.mary.preference_promotion.get_candidates() == []


def test_canonical_initiative_turn_cannot_create_creator_preference_evidence(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)

    result = app.run(
        "Please keep your answers concise.",
        metadata={
            "input_authority": "environment_context_only",
            "initiated_by": "mary_presence",
        },
    )

    assert "preference_evidence" not in _cycle(result).metadata["growth"]
    assert _cycle(result).metadata["growth"]["observed"] is False
    assert app.mary.preference_promotion.get_candidates() == []


def test_contradictory_creator_feedback_uses_existing_consistency_governance(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)
    prompts = (
        "Please keep your answers concise.",
        "I prefer your replies to be detailed.",
        "That response was too long.",
        "Your answer was too brief.",
        "From now on, keep your responses short.",
    )

    for index, prompt in enumerate(prompts):
        app.run(prompt, turn_id=f"contradictory-{index}")

    evaluation = app.mary.evaluate_preference_candidate(
        "creator interaction response length"
    )
    assert evaluation["observation_count"] == 5
    assert evaluation["consistency"] < app.mary.growth.preference_min_consistency
    assert app.mary.preferences.get_preference(
        "creator interaction response length"
    ) is None


def test_promoted_interaction_preference_conditions_fresh_session_and_survives_sleep_wake(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)
    _reinforce_concise_preference(app)

    app.mary.lifecycle.wake()
    app.mary.lifecycle.start()
    app.mary.lifecycle.shutdown()
    app.mary.lifecycle.stop()
    assert app.mary.lifecycle.is_awake is False
    app.mary.lifecycle.initialize()
    app.mary.lifecycle.ready()
    app.mary.lifecycle.wake()
    app.mary.lifecycle.start()
    assert app.mary.lifecycle.is_awake is True

    result = app.run(
        "Explain how a complex multi-stage deployment workflow should be "
        "organized when several services, approval gates, rollback checks, "
        "and separate release environments all need to stay coordinated.",
        metadata={"conversation_id": "fresh-behavior-session"},
    )
    disposition = _cycle(result).context.mind_state["disposition"]

    assert disposition["verbosity"] <= 0.34
    assert disposition["preferred_length"] == "brief"
    assert any(
        "developed interaction preference for concise responses" in item
        for item in disposition["instructions"]
    )


def test_promoted_interaction_preference_persists_across_application_reconstruction(
    tmp_path,
    monkeypatch,
):
    first = _application(tmp_path, monkeypatch, auto_save=True)
    _reinforce_concise_preference(first)
    assert first.close() is True

    second = _application(
        tmp_path,
        monkeypatch,
        auto_save=True,
        load=True,
    )
    restored = second.mary.preferences.get_preference(
        "creator interaction response length"
    )
    result = second.run(
        "Explain the release strategy with enough complexity to avoid a micro response.",
        metadata={"conversation_id": "post-restart-fresh-session"},
    )

    assert restored is not None
    assert restored["source"] == "experience_promotion"
    assert _cycle(result).context.mind_state["disposition"]["verbosity"] <= 0.34
    second.close()


def test_live_preference_pipeline_never_mutates_character_sourcebook(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)
    before = app.mary.character_sourcebook.snapshot()

    _reinforce_concise_preference(app)

    assert app.mary.character_sourcebook.snapshot() == before