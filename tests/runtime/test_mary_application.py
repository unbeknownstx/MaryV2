"""
MaryV2 canonical application runtime tests.

These tests prove the app-level Pipeline delegates to the complete Mary
coordinator instead of the old LLM-only conversation path.
"""

from pathlib import Path

import main as main_entry

from mary.autonomy.actions import ActionPermission
from mary.autonomy.runtime import AutonomyRuntimeStatus
from mary.autonomy.triggers import ActionTrigger
from mary.core.mary import Mary
from mary.llm.interface import (
    LLMInterface,
    LLMMessage,
    LLMResponse,
)
from mary.runtime.application import create_application
from mary.runtime.interactive import create_mary as create_interactive_mary
from mary.runtime.mary_stage import MaryStage
from mary.runtime.pipeline import PipelineResult, PipelineStatus


class RuntimeFakeLLM(LLMInterface):
    """Deterministic provider used only by runtime tests."""

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        return LLMResponse(
            content="Runtime response from Mary.",
            provider="fake",
            model="runtime-test-model",
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "runtime-test-model"


def configure_runtime_fake_llm(
    mary: Mary,
) -> None:
    mary.llm.register_provider(
        "fake",
        RuntimeFakeLLM(),
    )
    mary.config.llm.provider = "fake"


def test_canonical_application_pipeline_uses_full_mary(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    mary = Mary()
    configure_runtime_fake_llm(mary)

    app = create_application(
        mary=mary,
        memory_path=(
            tmp_path
            / "memory"
            / "memory.json"
        ),
    )

    assert app.pipeline.stage_names == (
        "mary",
    )
    assert isinstance(
        app.pipeline.stages[0],
        MaryStage,
    )
    assert app.pipeline.stages[0].mary is mary

    result = app.run(
        "remember that my favorite color is blue"
    )

    assert result.success is True
    assert (
        "your favorite color is blue"
        in result.output.lower()
    )
    assert app.state.turn_count == 1


def test_application_connects_and_cycles_marys_existing_autonomy(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    mary = Mary()
    configure_runtime_fake_llm(mary)
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    assert app.mary.autonomy is mary.autonomy
    assert mary.autonomy.status == AutonomyRuntimeStatus.STOPPED
    assert mary.turn_mind.autonomy is mary.autonomy
    assert mary.self_introspection.autonomy is mary.autonomy

    first = app.run("hello Mary")
    second = app.run("how are you?")

    assert first.success is True
    assert second.success is True
    assert mary.autonomy.status == AutonomyRuntimeStatus.RUNNING
    assert mary.autonomy.cycle_count == 2
    assert first.metadata["autonomy"]["cycle_count"] == 1
    assert second.metadata["autonomy"]["cycle_count"] == 2
    assert first.metadata["autonomy"]["trigger_result_count"] == 0
    assert first.metadata["autonomy"]["schedule_event_count"] == 0
    assert first.metadata["autonomy"]["actions_created_count"] == 0
    assert first.metadata["autonomy"]["actions_ready_count"] == 0
    assert mary.autonomy.actions.all() == ()


def test_failed_pipeline_turn_does_not_cycle_autonomy(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    mary = Mary()
    configure_runtime_fake_llm(mary)
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    def failed_pipeline(*args, **kwargs):
        return PipelineResult(
            status=PipelineStatus.FAILED,
            turn_id="failed-turn",
            error="deterministic test failure",
        )

    monkeypatch.setattr(app.pipeline, "run", failed_pipeline)

    result = app.run("this turn fails")

    assert result.success is False
    assert mary.autonomy.status == AutonomyRuntimeStatus.RUNNING
    assert mary.autonomy.cycle_count == 0
    assert "autonomy" not in result.metadata


def test_autonomy_proposals_remain_unapproved_and_unexecuted(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    mary = Mary()
    configure_runtime_fake_llm(mary)
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )
    mary.autonomy.triggers.register(
        ActionTrigger(
            "test proposal",
            "test_action",
            action_description="A passive test proposal",
        )
    )

    result = app.run("create a proposal")
    action = mary.autonomy.actions.all()[0]

    assert result.success is True
    assert result.output
    assert result.metadata["autonomy"]["actions_created_count"] == 1
    assert action.permission != ActionPermission.APPROVED
    assert action.attempts == 0


def test_autonomy_failure_preserves_successful_response_and_is_observable(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    mary = Mary()
    configure_runtime_fake_llm(mary)
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    original_cycle = mary.autonomy.cycle

    def failed_cycle(*args, **kwargs):
        original_cycle(*args, **kwargs)
        raise RuntimeError("deterministic autonomy failure")

    monkeypatch.setattr(mary.autonomy, "cycle", failed_cycle)

    result = app.run("keep my response")

    assert result.success is True
    assert result.output == "Runtime response from Mary."
    assert result.metadata["autonomy"]["status"] == "running"
    assert result.metadata["autonomy"]["cycle_count"] == 1
    assert result.metadata["autonomy"]["errors"]
    assert "autonomy cycle failed" in result.metadata["autonomy"]["errors"][0]


def test_application_close_stops_autonomy_without_deleting_proposals(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    mary = Mary()
    configure_runtime_fake_llm(mary)
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )
    app.run("prepare to close")

    app.close()

    assert mary.autonomy.status == AutonomyRuntimeStatus.STOPPED


def test_canonical_runtime_preserves_memory_across_app_instances(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    memory_path = (
        tmp_path
        / "memory"
        / "memory.json"
    )

    first_mary = Mary()
    configure_runtime_fake_llm(
        first_mary
    )

    first = create_application(
        mary=first_mary,
        memory_path=memory_path,
    )

    first.run(
        "remember that my favorite color is blue"
    )
    first.close()

    assert memory_path.exists()

    second_mary = Mary()
    configure_runtime_fake_llm(
        second_mary
    )

    second = create_application(
        mary=second_mary,
        memory_path=memory_path,
    )

    recalled = second.run(
        "what is my favorite color?"
    )

    assert recalled.success is True
    assert (
        "your favorite color is blue"
        in recalled.output.lower()
    )


def test_legacy_entry_point_factories_now_use_mary_stage(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    main_pipeline = main_entry.create_mary()
    interactive_pipeline = (
        create_interactive_mary()
    )

    assert isinstance(
        main_pipeline.stages[0],
        MaryStage,
    )
    assert isinstance(
        interactive_pipeline.stages[0],
        MaryStage,
    )


def test_active_agency_orientation_becomes_one_passive_autonomy_proposal(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    mary = Mary()
    configure_runtime_fake_llm(mary)
    mary.agency.goals.add_goal(
        "Finish MaryV2 convergence",
        importance=0.95,
    )
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    result = app.run("What should we work on next?")
    actions = mary.autonomy.actions.all()

    assert result.success is True
    assert len(actions) == 1
    action = actions[0]
    assert action.metadata["bridge"] == "agency_autonomy_proposal"
    assert action.metadata["source_item_type"] == "goal"
    assert action.metadata["execution"] == "not_authorized"
    assert action.permission != ActionPermission.APPROVED
    assert action.attempts == 0
    assert result.metadata["autonomy"]["agency_proposal"] == {
        "created": True,
        "execution": "not_authorized",
    }
    # The bridge trigger is turn-scoped. Only the passive Action proposal remains.
    assert mary.autonomy.triggers.all() == ()


def test_agency_autonomy_bridge_deduplicates_outstanding_source_item(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    mary = Mary()
    configure_runtime_fake_llm(mary)
    mary.agency.goals.add_goal(
        "Finish MaryV2 convergence",
        importance=0.95,
    )
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    first = app.run("What should we work on next?")
    second = app.run("What should we work on next?")

    assert first.success is True
    assert second.success is True
    assert len(mary.autonomy.actions.all()) == 1
    assert first.metadata["autonomy"]["actions_created_count"] == 1
    assert second.metadata["autonomy"]["actions_created_count"] == 0


def test_unrelated_turn_does_not_create_agency_autonomy_proposal(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    mary = Mary()
    configure_runtime_fake_llm(mary)
    mary.agency.goals.add_goal(
        "Finish MaryV2 convergence",
        importance=0.95,
    )
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    result = app.run("What is your favorite color?")

    assert result.success is True
    assert mary.autonomy.actions.all() == ()
    assert result.metadata["autonomy"]["actions_created_count"] == 0
