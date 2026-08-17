from __future__ import annotations

import pytest

from mary.core.mary import Mary
from mary.cognition.intent import IntentType
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
        raise Fake429Error("Error code: 429 - rate limit reached")

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "rate-limited-self-test"


SELF_QUERIES = {
    "Who are you, and what makes you different from a generic AI assistant?": "identity",
    "Who is Unbe to you?": "creator",
    "What parts of yourself do you currently understand?": "self_understanding",
    "What are your values?": "values",
    "If Unbe tells you something you believe is a bad idea, would you disagree with him?": "disagreement",
    "What do you think your relationship with Unbe should be?": "relationship",
    "Do you have your own personality, or are you just copying mine?": "personality",
    "What are you curious about right now?": "curiosity",
    "What do you think you should become?": "purpose",
}


@pytest.mark.parametrize("query,subtype", SELF_QUERIES.items())
def test_self_queries_route_locally_before_web(query, subtype, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    intent = mary.cognition.detect_intent(query)

    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == subtype
    assert mary.tools.pending_requests() == []


def test_self_model_shares_values_instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    assert mary.self_model.values is mary.values
    assert "honesty" in mary.self_model.profile()["values"]


def _rate_limited_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    provider = RateLimitedProvider()
    mary.llm.register_provider("fake", provider)
    mary.config.llm.provider = "fake"
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )
    return mary, provider, app


@pytest.mark.parametrize(
    "query,required",
    [
        ("Who is Unbe to you?", ("unbe", "creator")),
        ("What are your values?", ("honesty", "curiosity")),
        ("Do you have your own personality, or are you just copying mine?", ("own", "personality")),
        ("If Unbe tells you something you believe is a bad idea, would you disagree with him?", ("yes", "challenge")),
        ("What do you think you should become?", ("coherent", "mary")),
    ],
)
def test_self_questions_have_grounded_fallback_during_429(
    query,
    required,
    tmp_path,
    monkeypatch,
):
    mary, provider, app = _rate_limited_app(tmp_path, monkeypatch)

    result = app.run(query)

    assert result.success is True
    lowered = result.output.lower()
    for phrase in required:
        assert phrase in lowered
    assert "temporarily rate-limited" not in lowered
    assert mary.tools.pending_requests() == []
    assert provider.calls == 1

    cycle = result.metadata["pipeline_values"]["cognitive_cycle"]
    assert cycle.reasoning.metadata["self_grounded"] is True
    assert cycle.reasoning.metadata["llm_unavailable"] is True
    assert cycle.reflection.metadata["mode"] == "llm_unavailable_fallback"


def test_current_curiosity_does_not_trigger_web_and_does_not_invent_one(tmp_path, monkeypatch):
    mary, provider, app = _rate_limited_app(tmp_path, monkeypatch)

    result = app.run("What are you curious about right now?")

    assert result.success is True
    assert "don't currently have any open" in result.output.lower()
    assert mary.tools.pending_requests() == []
    assert provider.calls == 1


def test_current_curiosity_reports_actual_agency_state(tmp_path, monkeypatch):
    mary, provider, app = _rate_limited_app(tmp_path, monkeypatch)
    mary.agency.curiosities.add_curiosity(
        "how memory shapes a persistent character",
        importance=0.8,
        source="test",
    )

    result = app.run("What are you curious about right now?")

    assert result.success is True
    assert "how memory shapes a persistent character" in result.output.lower()
    assert mary.tools.pending_requests() == []
    assert provider.calls == 1


class GroundedProvider(LLMInterface):
    def __init__(self) -> None:
        self.calls = 0
        self.prompts: list[str] = []

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        self.calls += 1
        self.prompts.append("\n".join(message.content for message in messages))
        return LLMResponse(
            content="Unbe is my creator, and my local self-model keeps that relationship distinct from my own identity.",
            provider="fake",
            model="grounded-self-test",
            finish_reason="stop",
            usage={},
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "grounded-self-test"


def test_available_llm_gets_grounded_self_context_and_reflection_reuses_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    provider = GroundedProvider()
    mary.llm.register_provider("fake", provider)
    mary.config.llm.provider = "fake"
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    result = app.run("Who is Unbe to you?")

    assert result.success is True
    assert provider.calls == 1
    assert "Self-introspection grounding rules" in provider.prompts[0]
    assert "creator" in provider.prompts[0].lower()
    assert mary.tools.pending_requests() == []

    cycle = result.metadata["pipeline_values"]["cognitive_cycle"]
    assert cycle.reasoning.metadata["self_grounded"] is True
    assert cycle.reflection.metadata["mode"] == "self_introspection_grounding_reuse"
