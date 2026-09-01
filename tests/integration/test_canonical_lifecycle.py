"""Focused integration coverage for the canonical application turn lifecycle."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from mary.autonomy.actions import ActionPermission
from mary.core.service import MaryCoreService
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.mobile.server import MaryMobileRuntime
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
        raise RuntimeError(
            "PRIVATE_PROVIDER_BODY account=user@example.invalid token=secret-value"
        )


class DispositionAwareLifecycleLLM(LifecycleFakeLLM):
    """Make later output measurably follow the compiled developed-self context."""

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        prompt = "\n".join(str(message.content) for message in messages).casefold()
        if "length=micro" in prompt or "length=brief" in prompt:
            content = "Use staged releases with rollback gates."
        else:
            content = (
                "Organize the release as a sequence of coordinated stages. "
                "Begin with preflight validation, continue through environment "
                "promotion and approval gates, and finish with monitored rollout, "
                "rollback verification, and a documented handoff for every service."
            )
        return LLMResponse(
            content=content,
            provider="lifecycle-fake",
            model="lifecycle-test-model",
        )


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


def test_causal_trace_links_real_turn_objects_and_deduplicates_proposal(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)
    app.mary.set_developed_preference(
        "creator interaction response length",
        category="creator_interaction",
        strength=0.88,
        polarity=1.0,
        confidence=0.96,
        source="experience_promotion",
    )
    app.mary.agency.goals.add_goal(
        "Review the unfinished certification",
        importance=0.95,
    )

    def run_traced(turn_id: str):
        trace = TurnTraceRecorder(
            request_id=f"request-{turn_id}",
            core_instance_id="causal-core",
        )
        trace.set_turn_id(turn_id)
        trace.set_conversation_id("causal-conversation")
        token = bind_turn_trace(trace)
        try:
            result = app.run(
                "What should we work on next?",
                turn_id=turn_id,
            )
            trace.finish(outcome="success")
            return result, trace.snapshot()
        finally:
            reset_turn_trace(token)

    first, first_trace = run_traced("causal-turn-one")
    second, second_trace = run_traced("causal-turn-two")

    assert first.success is second.success is True
    first_stages = first_trace["stages"]
    by_stage = {
        name: [item for item in first_stages if item["stage"] == name]
        for name in {item["stage"] for item in first_stages}
    }
    attention = next(
        item
        for item in by_stage["attention_publication"]
        if item.get("result_ids", {}).get("attention_id")
    )
    experience = next(
        item
        for item in by_stage["experience_growth"]
        if item.get("result_ids", {}).get("experience_id")
    )
    developed = next(
        item
        for item in by_stage["developed_self_projection"]
        if item.get("result_ids", {}).get("developed_preference_id")
    )
    evaluation = by_stage["autonomy_evaluation"][-1]
    proposal = by_stage["autonomy_proposal"][-1]

    assert attention["result_ids"]["attention_id"].startswith("attention_")
    assert experience["result_ids"]["experience_id"].startswith("experience_")
    assert developed["result_ids"]["developed_preference_id"][0].startswith(
        "developed_preference_"
    )
    assert evaluation["result_ids"]["attention_id"] == (
        attention["result_ids"]["attention_id"]
    )
    assert evaluation["result_ids"]["autonomy_cycle_id"].startswith(
        "autonomy_cycle_"
    )
    assert evaluation["result_ids"]["autonomy_evaluation_id"].startswith(
        "evaluation_"
    )
    assert proposal["outcome"] == "proposed_pending_confirmation"
    assert proposal["result_ids"]["autonomy_proposal_id"][0].startswith(
        "proposal_"
    )

    repeated = [
        item
        for item in second_trace["stages"]
        if item["stage"] == "autonomy_proposal"
    ][-1]
    assert repeated["outcome"] == "deduplicated_existing"
    assert repeated["result_ids"]["autonomy_proposal_id"] == (
        proposal["result_ids"]["autonomy_proposal_id"]
    )
    action = app.mary.autonomy.actions.all()[0]
    assert action.metadata["execution_status"] == "not_executed"
    assert action.metadata["confirmation_required"] is True
    assert action.attempts == 0
    serialized = str(first_trace) + str(second_trace)
    assert "What should we work on next?" not in serialized
    assert "A deterministic Mary response." not in serialized
    assert "creator interaction response length" not in serialized


def test_local_mobile_produces_and_queries_canonical_content_free_trace(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)
    runtime = MaryMobileRuntime(application=app)
    private_prompt = "PRIVATE_LOCAL_MOBILE_PROMPT"
    monkeypatch.setattr(
        "mary.mobile.server.build_turn_trace",
        lambda *_args, **_kwargs: {
            "turn_id": "PRIVATE_RAW_TURN",
            "provider": "groq",
            "model": "PRIVATE_MODEL_NAME",
            "finish_reason": "PRIVATE_FINISH_REASON",
            "attempts": [
                {
                    "provider": "groq",
                    "status": "success",
                    "elapsed_ms": 4.5,
                    "error": "PRIVATE_PROVIDER_ERROR",
                },
                {
                    "provider": "PRIVATE_PROVIDER",
                    "status": "PRIVATE_STATUS",
                },
            ],
            "timings": {
                "pipeline_ms": 8.0,
                "private_timing": "PRIVATE_TIMING_VALUE",
            },
            "delivery_plan": {
                "private": "PRIVATE_CREATOR_CONTEXT",
            },
        },
    )

    payload = runtime.chat(
        private_prompt,
        conversation_id="person@example.invalid",
    )
    raw_turn_id = payload["runtime"]["turn_id"]
    trace = runtime.last_turn_trace()
    queried = runtime.query_turn_traces(
        turn_id=raw_turn_id,
        limit=999,
    )

    assert trace["event"] == "mary.turn.complete"
    assert trace["schema"] == 1
    assert trace["status"] == "success"
    assert trace["turn_id"].startswith("turn_")
    assert trace["conversation_id"].startswith("conversation_")
    assert payload["runtime"]["trace"] == trace
    assert trace["model"] == "configured"
    assert trace["finish_reason"] == "unknown"
    assert trace["provider_attempts"] == [
        {
            "provider": "groq",
            "status": "success",
            "elapsed_ms": 4.5,
        },
        {
            "provider": "unknown",
            "status": "unknown",
        },
    ]
    assert trace["timings"] == {"pipeline_ms": 8.0}
    assert queried["traces"] == [trace]
    assert queried["count"] == 1
    serialized = str(trace)
    assert private_prompt not in serialized
    assert "person@example.invalid" not in serialized
    assert "Runtime response from Mary." not in serialized
    assert "PRIVATE_" not in serialized

    monkeypatch.setattr(
        app,
        "run",
        lambda *_args, **_kwargs: PipelineResult(
            status=PipelineStatus.FAILED,
            turn_id="failed-mobile-turn",
            error="PRIVATE_RETURNED_FAILURE",
        ),
    )
    with pytest.raises(RuntimeError, match="PRIVATE_RETURNED_FAILURE"):
        runtime.chat("PRIVATE_FAILED_MOBILE_PROMPT")
    failed = runtime.last_turn_trace()
    assert failed["status"] == "failure"
    assert failed["outcome"] == "failure"
    assert "PRIVATE_RETURNED_FAILURE" not in str(failed)
    assert "PRIVATE_FAILED_MOBILE_PROMPT" not in str(failed)


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

    assert diagnostic["detected"] is True
    assert diagnostic["evidence_class"] == "explicit_preference"
    assert diagnostic["signal"] == "response_length"
    assert diagnostic["candidate_created"] is True
    assert diagnostic["observation_count"] == 1
    assert diagnostic["candidate_state"] == "candidate"
    assert diagnostic["gate_outcome"] == "deferred"
    assert diagnostic["disposition"] == "deferred"
    assert diagnostic["promotion_result"] == "deferred"
    assert diagnostic["developed_preference_id"] is None
    assert diagnostic["evidence_id"].startswith("creator_turn_")
    assert diagnostic["candidate_id"].startswith("preference_candidate_")
    assert growth["experience_id"]
    status_candidate = app.mary.growth.status()["preference_candidates"][0]
    assert status_candidate["candidate_id"] == diagnostic["candidate_id"]
    assert status_candidate["state"] == "candidate"
    assert private_text not in str(diagnostic)
    assert private_text not in str(app.mary.growth.status())
    assert app.mary.preferences.get_preference(
        "creator interaction response length"
    ) is None


def test_common_summary_first_and_compound_creator_language_are_bounded_evidence(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)

    compound = app.run(
        "I prefer concise actionable answers first.",
        turn_id="ordinary-compound-preference",
    )
    compound_diagnostic = _cycle(compound).metadata["growth"][
        "preference_evidence"
    ]
    items = compound_diagnostic["evidence_items"]

    assert [item["signal"] for item in items] == [
        "response_length",
        "directness",
    ]
    assert len({item["evidence_id"] for item in items}) == 2
    assert len({item["candidate_id"] for item in items}) == 2
    assert all(item["observation_count"] == 1 for item in items)
    assert all(item["disposition"] == "deferred" for item in items)

    summary_first = app.run(
        "I prefer technical explanations to start with a short summary "
        "before the detail.",
        turn_id="ordinary-summary-first-preference",
    )
    summary_diagnostic = _cycle(summary_first).metadata["growth"][
        "preference_evidence"
    ]
    assert summary_diagnostic["signal"] == "directness"
    assert summary_diagnostic["observation_count"] == 2

    corrective = app.run(
        "That was too verbose. Give me the actionable answer first in "
        "situations like this.",
        turn_id="ordinary-corrective-preference",
    )
    corrective_items = _cycle(corrective).metadata["growth"][
        "preference_evidence"
    ]["evidence_items"]
    assert [item["signal"] for item in corrective_items] == [
        "response_length",
        "directness",
    ]
    assert all(item["evidence_class"] == "corrective_feedback" for item in corrective_items)
    assert [item["observation_count"] for item in corrective_items] == [2, 3]


def test_non_preferences_and_unbounded_negation_remain_not_applicable(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)

    for index, prompt in enumerate(
        (
            "I prefer tea in the afternoon.",
            "Technical explanations often have summaries.",
            "I do not prefer concise answers.",
            "I prefer answers that are not concise.",
            "I prefer answers without concise summaries.",
            "I prefer non-actionable answers.",
            "I prefer concise answers but detailed responses.",
            "I prefer detailed responses but concise answers.",
            "That was too verbose, but give more detail in your responses.",
            "Give more detail in your responses, but that was too verbose.",
            "That was too long, but your next response should be detailed.",
            "Your response should be detailed, but that was too long.",
            "That response was too brief, but please keep your answers concise.",
            "Please keep your answers concise, but that response was too brief.",
            "For this one response, use the first paragraph from the document.",
        )
    ):
        result = app.run(prompt, turn_id=f"bounded-negative-{index}")
        assert _cycle(result).metadata["growth"]["preference_evidence"] == {
            "detected": False,
            "disposition": "not_applicable",
        }
    assert app.mary.preference_promotion.get_candidates() == []


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
    assert _cycle(result).reasoning.metadata["llm_error"] == "provider_unavailable"
    assert "PRIVATE_PROVIDER_BODY" not in str(_cycle(result).metadata)
    assert "user@example.invalid" not in str(_cycle(result).metadata)
    assert "secret-value" not in str(_cycle(result).metadata)
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
    assert disposition["preferred_length"] in {"brief", "micro"}
    assert disposition["verbosity"] <= 0.34
    assert any(
        "developed interaction preference for concise responses" in item
        for item in disposition["instructions"]
    )


def test_promoted_preference_changes_later_comparable_behavior_without_restatement(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)
    app.mary.llm.register_provider(
        "lifecycle-fake",
        DispositionAwareLifecycleLLM(),
    )
    query = (
        "Explain how a complex multi-stage deployment workflow should be "
        "organized when several services, approval gates, rollback checks, "
        "regional safety constraints, and separate release environments all "
        "need to stay coordinated without losing a clear ownership trail."
    )

    before = app.run(
        query,
        turn_id="behavior-before-promotion",
        metadata={"conversation_id": "behavior-baseline-session"},
    )
    _reinforce_concise_preference(app)
    promotion_diagnostic = app.mary.growth.last_growth["preference_evidence"]
    after = app.run(
        query,
        turn_id="behavior-after-promotion",
        metadata={"conversation_id": "behavior-fresh-session"},
    )
    before_disposition = _cycle(before).context.mind_state["disposition"]
    disposition = _cycle(after).context.mind_state["disposition"]

    assert promotion_diagnostic["disposition"] == "promoted"
    assert promotion_diagnostic["promotion_result"] == "promoted"
    assert promotion_diagnostic["developed_preference_id"].startswith(
        "developed_preference_"
    )
    developed_status = app.mary.growth.status()["developed_preferences"]
    assert developed_status == [
        {
            "developed_preference_id": promotion_diagnostic[
                "developed_preference_id"
            ],
            "state": "active",
        }
    ]
    assert disposition["preferred_length"] in {"brief", "micro"}
    assert disposition["verbosity"] <= 0.34
    assert before_disposition["preferred_length"] == "medium"
    assert len(after.output) < len(before.output) * 0.5
    assert "concise" not in query.casefold()


def test_promoted_interaction_preference_persists_across_application_reconstruction(
    tmp_path,
    monkeypatch,
):
    first = _application(tmp_path, monkeypatch, auto_save=True)
    first.mary.llm.register_provider(
        "lifecycle-fake",
        DispositionAwareLifecycleLLM(),
    )
    query = (
        "Explain how a complex multi-stage deployment workflow should be "
        "organized when several services, approval gates, rollback checks, "
        "regional safety constraints, and separate release environments all "
        "need to stay coordinated without losing a clear ownership trail."
    )
    baseline = first.run(
        query,
        turn_id="reconstruction-behavior-baseline",
        metadata={"conversation_id": "reconstruction-baseline-session"},
    )
    _reinforce_concise_preference(first)
    assert first.close() is True

    second = _application(
        tmp_path,
        monkeypatch,
        auto_save=True,
        load=True,
    )
    second.mary.llm.register_provider(
        "lifecycle-fake",
        DispositionAwareLifecycleLLM(),
    )
    restored = second.mary.preferences.get_preference(
        "creator interaction response length"
    )
    result = second.run(
        query,
        turn_id="reconstruction-behavior-restored",
        metadata={"conversation_id": "post-restart-fresh-session"},
    )

    assert restored is not None
    assert restored["source"] == "experience_promotion"
    assert _cycle(result).context.mind_state["disposition"]["verbosity"] <= 0.34
    assert len(result.output) < len(baseline.output) * 0.5
    assert second.mary.growth.status()["developed_preferences"][0]["state"] == (
        "active"
    )
    second.close()


def test_live_preference_pipeline_never_mutates_character_sourcebook(
    tmp_path,
    monkeypatch,
):
    app = _application(tmp_path, monkeypatch)
    before = app.mary.character_sourcebook.snapshot()

    _reinforce_concise_preference(app)

    assert app.mary.character_sourcebook.snapshot() == before