from __future__ import annotations

from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.runtime.application import create_application


class NoLLMAllowed(LLMInterface):
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        self.calls += 1
        raise AssertionError("memory retrieval should not call the LLM")

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "no-llm"

    def model_name(self) -> str:
        return "no-llm"


def make_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    provider = NoLLMAllowed()
    mary.llm.register_provider("no-llm", provider)
    mary.config.llm.provider = "no-llm"
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )
    return mary, provider, app


def test_specific_what_do_you_remember_query_does_not_dump_everything(
    tmp_path,
    monkeypatch,
):
    _, provider, app = make_app(tmp_path, monkeypatch)

    app.run("remember that my favorite color is blue")
    app.run("remember that my test animal is a red panda")
    app.run(
        "remember this: creating in the spaces of silence is beautiful "
        "and existence is always precious"
    )

    recalled = app.run(
        "what do you remember about creation and existence?"
    )

    text = recalled.output.lower()
    assert recalled.success is True
    assert "existence is always precious" in text
    assert "favorite color" not in text
    assert "red panda" not in text
    assert provider.calls == 0


def test_broad_memory_query_still_returns_multiple_memories(
    tmp_path,
    monkeypatch,
):
    _, provider, app = make_app(tmp_path, monkeypatch)

    app.run("remember that my favorite color is blue")
    app.run("remember that my test animal is a red panda")

    recalled = app.run("what do you remember about me?")

    text = recalled.output.lower()
    assert "favorite color" in text
    assert "red panda" in text
    assert provider.calls == 0


def test_current_fact_query_prefers_newest_value_but_keeps_history(
    tmp_path,
    monkeypatch,
):
    mary, provider, app = make_app(tmp_path, monkeypatch)

    app.run("remember that my favorite color is blue")
    app.run("remember that my favorite color is green")

    current = app.run("what is my favorite color?")
    current_text = current.output.lower()

    assert "favorite color is green" in current_text
    assert "favorite color is blue" not in current_text

    historical = app.run("what do you remember about my favorite color?")
    historical_text = historical.output.lower()

    assert "favorite color is green" in historical_text
    assert "favorite color is blue" in historical_text
    assert mary.memory.episodic.count() == 2
    assert provider.calls == 0


def test_current_fact_resolution_survives_restart(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    memory_path = tmp_path / "memory" / "memory.json"

    first_mary = Mary()
    first_provider = NoLLMAllowed()
    first_mary.llm.register_provider("no-llm", first_provider)
    first_mary.config.llm.provider = "no-llm"
    first = create_application(
        mary=first_mary,
        memory_path=memory_path,
    )

    first.run("remember that my favorite color is blue")
    first.run("remember that my favorite color is green")
    first.close()

    second_mary = Mary()
    second_provider = NoLLMAllowed()
    second_mary.llm.register_provider("no-llm", second_provider)
    second_mary.config.llm.provider = "no-llm"
    second = create_application(
        mary=second_mary,
        memory_path=memory_path,
    )

    recalled = second.run("what is my favorite color?")
    text = recalled.output.lower()

    assert "favorite color is green" in text
    assert "favorite color is blue" not in text
    assert second_mary.memory.episodic.count() == 2
    assert second_provider.calls == 0
