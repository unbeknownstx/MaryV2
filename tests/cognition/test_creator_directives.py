from __future__ import annotations

from mary.cognition.intent import IntentType
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
        raise Fake429Error("Error code: 429 - rate limit reached")

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "rate-limited-directive-test"


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


def test_creator_curiosity_directive_routes_before_llm_or_web(tmp_path, monkeypatch):
    mary, provider, app = _rate_limited_app(tmp_path, monkeypatch)

    intent = mary.cognition.detect_intent(
        "you should be curious about me top priority"
    )

    assert intent.intent_type == IntentType.CREATOR_DIRECTIVE
    assert intent.parameters["directive_type"] == "creator_curiosity"
    assert intent.parameters["top_priority"] is True

    result = app.run("you should be curious about me top priority")

    assert result.success is True
    assert "creator-directed curiosity" in result.output.lower()
    assert "top internal priority" in result.output.lower()
    assert provider.calls == 0
    assert mary.tools.pending_requests() == []


def test_creator_directive_persists_and_populates_curiosity_priority(tmp_path, monkeypatch):
    mary, provider, app = _rate_limited_app(tmp_path, monkeypatch)

    result = app.run("make learning about me a top priority")
    assert result.success is True
    assert provider.calls == 0

    active = mary.creator_directives.get_active()
    assert len(active) == 1
    assert active[0]["category"] == "relationship_curiosity"
    assert active[0]["target"] == "unbe"
    assert active[0]["priority"] == 1.0

    curiosities = mary.agency.curiosities.get_open_curiosities()
    parents = [
        item for item in curiosities
        if item["description"].lower() == "learn more about unbe"
    ]
    assert len(parents) == 1
    assert parents[0]["importance"] == 1.0
    assert parents[0]["relevance"] == 1.0
    assert parents[0]["creator_directed"] is True
    assert any(item.get("relationship_gap") for item in curiosities)

    ranked = mary.agency.rebuild_priorities()
    assert ranked
    top = max(ranked, key=lambda item: item.score)
    assert top.description.lower() == "learn more about unbe"


def test_repeating_same_creator_directive_does_not_duplicate_curiosity(tmp_path, monkeypatch):
    mary, provider, app = _rate_limited_app(tmp_path, monkeypatch)

    app.run("you should be curious about me top priority")
    app.run("make learning about me a top priority")

    assert provider.calls == 0
    assert len(mary.creator_directives.get_active()) == 1
    parents = [
        item for item in mary.agency.curiosities.get_curiosities()
        if item.get("status") in {"open", "exploring"}
        and item.get("description", "").lower() == "learn more about unbe"
    ]
    assert len(parents) == 1
    gap_categories = [
        item.get("gap_category")
        for item in mary.agency.curiosities.get_curiosities()
        if item.get("relationship_gap")
    ]
    assert len(gap_categories) == len(set(gap_categories))


def test_creator_directive_survives_restart(tmp_path, monkeypatch):
    mary, provider, app = _rate_limited_app(tmp_path, monkeypatch)
    app.run("you should be curious about me top priority")
    assert provider.calls == 0

    restarted = Mary()

    active = restarted.creator_directives.get_active()
    assert len(active) == 1
    assert active[0]["target"] == "unbe"

    curiosities = restarted.agency.curiosities.get_open_curiosities()
    parents = [
        item for item in curiosities
        if item["description"].lower() == "learn more about unbe"
    ]
    assert len(parents) == 1
    assert any(item.get("relationship_gap") for item in curiosities)


def test_self_curiosity_reports_creator_directive_during_429(tmp_path, monkeypatch):
    mary, provider, app = _rate_limited_app(tmp_path, monkeypatch)
    app.run("you should be curious about me top priority")
    assert provider.calls == 0

    curiosity = app.run("What are you curious about right now?")
    priorities = app.run("What is your top priority?")

    assert curiosity.success is True
    assert "learn more about unbe" in curiosity.output.lower()
    assert priorities.success is True
    assert "learn more about unbe" in priorities.output.lower()
    assert provider.calls == 2
    assert mary.tools.pending_requests() == []


def test_remember_this_stays_memory_not_creator_directive(tmp_path, monkeypatch):
    mary, provider, app = _rate_limited_app(tmp_path, monkeypatch)

    intent = mary.cognition.detect_intent(
        "remember this: unbe is your top priority"
    )

    assert intent.intent_type == IntentType.MEMORY_STORE

    result = app.run("remember this: unbe is your top priority")
    assert result.success is True
    assert provider.calls == 0
    assert mary.creator_directives.get_active() == []

class InventedDateProvider(LLMInterface):
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            content="I'm Mary. I was created by Unbe on 2026-08-17.",
            provider="fake",
            model="invented-date-test",
            finish_reason="stop",
            usage={},
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "invented-date-test"


def test_unsupported_self_biography_date_falls_back_to_local_grounding(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    provider = InventedDateProvider()
    mary.llm.register_provider("fake", provider)
    mary.config.llm.provider = "fake"
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    result = app.run(
        "Who are you, and what makes you different from a generic AI assistant?"
    )

    assert result.success is True
    assert "2026-08-17" not in result.output
    assert "persistent identity" in result.output.lower()
    assert provider.calls == 1

    cycle = result.metadata["pipeline_values"]["cognitive_cycle"]
    assert cycle.reasoning.metadata["self_grounding_rejected"] is True
    assert "unsupported" in cycle.reasoning.metadata["self_grounding_issue"].lower()
    assert "creation date" in cycle.reasoning.metadata["self_grounding_issue"].lower()
