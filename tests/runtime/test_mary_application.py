"""
MaryV2 canonical application runtime tests.

These tests prove the app-level Pipeline delegates to the complete Mary
coordinator instead of the old LLM-only conversation path.
"""

from pathlib import Path

import main as main_entry

from mary.core.mary import Mary
from mary.llm.interface import (
    LLMInterface,
    LLMMessage,
    LLMResponse,
)
from mary.runtime.application import create_application
from mary.runtime.interactive import create_mary as create_interactive_mary
from mary.runtime.mary_stage import MaryStage


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
    assert app.mary is mary
    assert app.ecosystem.mary is mary
    assert app.pipeline.runtime_state is app.state

    result = app.run(
        "remember that my favorite color is blue"
    )

    assert result.success is True
    assert (
        "your favorite color is blue"
        in result.output.lower()
    )
    assert app.state.turn_count == 1


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
