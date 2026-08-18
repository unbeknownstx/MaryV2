from __future__ import annotations

import pytest

from mary.cognition.intent import IntentType
from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.runtime.application import create_application


class SelfCoreProvider(LLMInterface):
    def __init__(self, response: str) -> None:
        self.response = response
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
            content=self.response,
            provider="fake",
            model="character-core-test",
            finish_reason="stop",
            usage={},
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "character-core-test"


def _app(tmp_path, monkeypatch, response: str):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    provider = SelfCoreProvider(response)
    mary.llm.register_provider("fake", provider)
    mary.config.llm.provider = "fake"
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )
    return mary, provider, app


@pytest.mark.parametrize(
    "query,subtype",
    [
        ("What are you afraid of?", "vulnerabilities"),
        ("What are you like romantically?", "romance"),
        ("How do you act when you're angry?", "reactions"),
        ("How do you behave around strangers vs close friends?", "social_behavior"),
        ("What do you do when you're alone?", "private_life"),
        ("What kind of slang do you use?", "speech"),
        ("What are your long-term goals?", "goals"),
        ("What do you do for fun?", "preferences"),
        ("What food do you hate?", "preferences"),
        ("What color are your eyes?", "appearance"),
    ],
)
def test_character_core_questions_route_to_local_self_grounding(
    query,
    subtype,
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    intent = mary.cognition.detect_intent(query)

    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == subtype
    assert mary.tools.pending_requests() == []


def test_wrong_eye_color_is_rejected_and_falls_back_to_blue(tmp_path, monkeypatch):
    _, provider, app = _app(
        tmp_path,
        monkeypatch,
        "My eyes are green.",
    )

    result = app.run("What color are your eyes?")

    assert result.success is True
    assert result.output == "My eyes are blue."
    assert provider.calls == 1
    cycle = result.metadata["pipeline_values"]["cognitive_cycle"]
    assert cycle.reasoning.metadata["self_grounding_rejected"] is True
    assert "eye color" in cycle.reasoning.metadata["self_grounding_issue"].lower()


def test_provider_cannot_invent_unrepresented_fear(tmp_path, monkeypatch):
    _, provider, app = _app(
        tmp_path,
        monkeypatch,
        "I'm mostly afraid of spiders.",
    )

    result = app.run("What are you afraid of?")

    assert result.success is True
    lowered = result.output.lower()
    assert "abandon" in lowered
    assert "spider" not in lowered
    assert provider.calls == 1
    cycle = result.metadata["pipeline_values"]["cognitive_cycle"]
    assert cycle.reasoning.metadata["self_grounding_rejected"] is True


def test_food_dislike_query_grounds_shrimp_and_liver(tmp_path, monkeypatch):
    _, provider, app = _app(
        tmp_path,
        monkeypatch,
        "I hate pizza.",
    )

    result = app.run("What food do you hate?")

    assert result.success is True
    lowered = result.output.lower()
    assert "shrimp" in lowered
    assert "liver" in lowered
    assert "pizza" not in lowered
    assert provider.calls == 1
    assert "shrimp" in provider.prompts[0].lower()
    assert "liver" in provider.prompts[0].lower()


def test_character_self_prompts_stay_compact(tmp_path, monkeypatch):
    _, provider, app = _app(
        tmp_path,
        monkeypatch,
        "I'm a hopeless romantic who likes thoughtful gifts and quality time.",
    )

    result = app.run("What are you like romantically?")

    assert result.success is True
    assert provider.calls == 1
    assert len(provider.prompts[0]) < 4000
    assert "TurnMindState (authoritative integrated Mary state for this turn)" not in provider.prompts[0]
