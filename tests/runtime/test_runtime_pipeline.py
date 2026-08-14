"""
MaryV2 - Runtime Pipeline Tests

Tests execution of a complete runtime turn.
"""

from mary.runtime.manager import RuntimeManager
from mary.runtime.pipeline import PipelineStage, StageResult


def test_runtime_pipeline_can_execute_stage():
    runtime = RuntimeManager()

    def receive_input(context):
        return StageResult(
            output="Hello Mary",
            values={
                "input_text": "Hello Mary",
            },
        )

    runtime.pipeline.add_stage(
        PipelineStage(
            name="input",
            handler=receive_input,
        )
    )

    result = runtime.pipeline.run(
        input_data="Hello Mary",
        turn_id="test-turn-1",
    )

    assert result is not None
    assert result.success is True


def test_runtime_pipeline_preserves_context_values():
    runtime = RuntimeManager()

    def first_stage(context):
        return StageResult(
            values={
                "message": "Hello Mary",
            }
        )

    def second_stage(context):
        message = context.require("message")

        return StageResult(
            output=message,
        )

    runtime.pipeline.add_stage(
        PipelineStage(
            name="first",
            handler=first_stage,
        )
    )

    runtime.pipeline.add_stage(
        PipelineStage(
            name="second",
            handler=second_stage,
        )
    )

    result = runtime.pipeline.run(
        input_data="test",
        turn_id="test-turn-2",
    )

    assert result.success is True
    assert result.output == "Hello Mary"


def test_runtime_manager_reports_pipeline():
    runtime = RuntimeManager()

    snapshot = runtime.snapshot()

    assert snapshot is not None
    assert snapshot.status.value == "created"
    assert snapshot.turn_count == 0
