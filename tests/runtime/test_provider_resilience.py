from __future__ import annotations

from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.runtime.application import create_application


class Fake429Error(Exception):
    status_code = 429


class RateLimitedProvider(LLMInterface):
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        self.calls += 1
        raise Fake429Error(
            "Error code: 429 - rate limit reached on tokens per day (TPD)"
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "rate-limited-test-model"


def configure_rate_limited_mary(mary: Mary) -> RateLimitedProvider:
    provider = RateLimitedProvider()
    mary.llm.register_provider("fake", provider)
    mary.config.llm.provider = "fake"
    mary.config.llm.fallback_providers = []
    return provider


def test_natural_remember_this_payload_is_stored_without_llm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    mary = Mary()
    provider = configure_rate_limited_mary(mary)
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    result = app.run(
        "want to know something about me remember this : "
        "existence is always precious"
    )

    assert result.success is True
    assert "existence is always precious" in result.output.lower()
    assert provider.calls == 0

    memories = mary.memory.episodic.all()
    assert memories
    assert memories[-1].content == "existence is always precious"
    assert memories[-1].metadata["owner"] == "creator"
    assert memories[-1].metadata["speaker"] == "Unbe"


def test_memory_recall_still_works_when_llm_is_rate_limited(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    mary = Mary()
    provider = configure_rate_limited_mary(mary)
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    stored = app.run("remember this: my test phrase is starlight")
    recalled = app.run("what do you remember about my test phrase?")

    assert stored.success is True
    assert recalled.success is True
    assert "your test phrase is starlight" in recalled.output.lower()
    assert provider.calls == 0


def test_rate_limit_degrades_to_response_instead_of_pipeline_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    mary = Mary()
    provider = configure_rate_limited_mary(mary)
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    result = app.run("i will always let you know about my deepest thoughts")

    assert result.success is True
    assert "language engines" in result.output.lower()
    assert "still here" in result.output.lower()
    assert "pipeline" not in result.output.lower()
    assert provider.calls == 1

    cycle = result.metadata["pipeline_values"]["cognitive_cycle"]
    assert cycle.reasoning.metadata["llm_unavailable"] is True
    assert cycle.reasoning.metadata["llm_rate_limited"] is True
    assert cycle.reflection.metadata["mode"] == "llm_unavailable_fallback"


def test_rate_limit_fixture_does_not_inherit_environment_fallbacks(tmp_path, monkeypatch):
    """Deterministic 429 tests must not escape into developer cloud providers."""

    monkeypatch.setenv(
        "MARY_LLM_FALLBACKS",
        "groq,gemini,openrouter,ollama",
    )
    monkeypatch.chdir(tmp_path)

    mary = Mary()
    assert mary.config.llm.fallback_providers == [
        "groq",
        "gemini",
        "openrouter",
        "ollama",
    ]

    provider = configure_rate_limited_mary(mary)
    assert mary.config.llm.provider == "fake"
    assert mary.config.llm.fallback_providers == []

    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    result = app.run("i will always let you know about my deepest thoughts")

    assert result.success is True
    assert provider.calls == 1
    assert mary.llm.last_generation_attempts
    assert [item["provider"] for item in mary.llm.last_generation_attempts] == ["fake"]

    cycle = result.metadata["pipeline_values"]["cognitive_cycle"]
    assert cycle.reasoning.metadata["llm_unavailable"] is True
    assert cycle.reasoning.metadata["llm_rate_limited"] is True