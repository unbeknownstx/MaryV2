"""Focused integration coverage for the canonical application turn lifecycle."""

from __future__ import annotations

from typing import Any

from mary.autonomy.actions import ActionPermission
from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.runtime.application import create_application
from mary.runtime.pipeline import PipelineResult, PipelineStatus
from mary.runtime.turn_observability import (
    TurnTraceRecorder,
    bind_turn_trace,
    reset_turn_trace,
)


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


def _application(tmp_path, monkeypatch, *, response: str = "A deterministic Mary response."):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MARY_DATA_DIR", str(tmp_path / "mary-data"))
    mary = Mary()
    mary.llm.register_provider("lifecycle-fake", LifecycleFakeLLM(response))
    mary.config.llm.provider = "lifecycle-fake"
    return create_application(
        mary=mary,
        memory_path=tmp_path / "state" / "memory" / "memory.json",
        developed_self_path=tmp_path / "state" / "personality" / "developed_self.json",
        preference_promotion_path=tmp_path / "state" / "personality" / "preference_promotion.json",
        knowledge_path=tmp_path / "state" / "knowledge" / "knowledge.json",
        auto_save=False,
        load_memory=False,
        load_developed_self=False,
        load_preference_promotion=False,
        load_knowledge=False,
        name="canonical-lifecycle-integration",
    )


def _authoritative_state(mary: Mary) -> dict[str, Any]:
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