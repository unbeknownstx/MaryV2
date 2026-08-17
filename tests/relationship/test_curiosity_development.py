from __future__ import annotations

from mary.cognition.intent import IntentType
from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.runtime.application import create_application


class NoLLMProvider(LLMInterface):
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        self.calls += 1
        raise AssertionError("curiosity-development local paths must not call the LLM")

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "no-llm-curiosity-development"


def _app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    provider = NoLLMProvider()
    mary.llm.register_provider("fake", provider)
    mary.config.llm.provider = "fake"
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
    )
    return mary, provider, app


def _gap_children(mary: Mary):
    return [
        item
        for item in mary.agency.curiosities.get_curiosities()
        if item.get("relationship_gap")
        or bool((item.get("metadata") or {}).get("relationship_gap"))
    ]


def _parent(mary: Mary):
    return next(
        item
        for item in mary.agency.curiosities.get_curiosities()
        if str(item.get("description", "")).lower() == "learn more about unbe"
    )


def test_creator_directive_develops_specific_relationship_gaps(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)

    result = app.run("you should be curious about me top priority")

    assert result.success is True
    children = _gap_children(mary)
    assert {item.get("gap_category") for item in children} == {
        "preferences",
        "interests",
        "goals",
        "values",
        "communication",
    }
    assert all(item.get("status") == "open" for item in children)
    assert all(item.get("parent_curiosity_id") == _parent(mary).get("id") for item in children)
    assert provider.calls == 0
    assert mary.tools.pending_requests() == []


def test_existing_relationship_knowledge_prevents_already_filled_gap_children(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)

    app.run("remember this: my favorite color is green")
    app.run("remember this: I love creating stories")
    app.run("you should be curious about me top priority")

    children = _gap_children(mary)
    unresolved = {
        item.get("gap_category")
        for item in children
        if item.get("status") in {"open", "exploring"}
    }
    assert "preferences" not in unresolved
    assert "interests" not in unresolved
    assert {"goals", "values", "communication"}.issubset(unresolved)
    assert provider.calls == 0


def test_learning_goal_resolves_goal_gap_and_query_updates(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)
    app.run("you should be curious about me top priority")

    before = app.run("What are you still curious about regarding me?")
    assert "what goals matter most to unbe" in str(before.output).lower()

    learned = app.run("learn this about me: my main goal is finish MaryV2")
    assert learned.success is True
    assert "finish MaryV2" in mary.user_model.goals

    goal_child = next(
        item for item in _gap_children(mary)
        if item.get("gap_category") == "goals"
    )
    assert goal_child.get("status") == "resolved"

    after = app.run("What are you still curious about regarding me?")
    assert "what goals matter most to unbe" not in str(after.output).lower()
    assert "goals" in str(after.output).lower()
    assert provider.calls == 0


def test_communication_preference_resolves_communication_gap(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)
    app.run("you should be curious about me top priority")

    app.run("learn this about me: I prefer you to be direct and concise")

    assert mary.user_model.communication_style["preferred_style"] == "be direct and concise"
    communication_child = next(
        item for item in _gap_children(mary)
        if item.get("gap_category") == "communication"
    )
    assert communication_child.get("status") == "resolved"
    assert provider.calls == 0


def test_relationship_gap_query_routes_local_before_web_or_llm(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)
    app.run("you should be curious about me top priority")

    intent = mary.cognition.detect_intent("What don't you know about me?")
    assert intent.intent_type == IntentType.RELATIONSHIP_QUERY
    assert intent.parameters["relationship_query_type"] == "curiosity_gaps"

    result = app.run("What don't you know about me?")
    assert result.success is True
    assert "still curious" in str(result.output).lower()
    assert "not permission" in str(result.output).lower()
    assert provider.calls == 0
    assert mary.tools.pending_requests() == []


def test_specific_relationship_curiosity_survives_restart_without_duplicates(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)
    app.run("you should be curious about me top priority")
    app.run("learn this about me: my goal is finish MaryV2")
    app.close()

    restarted = Mary()
    restarted_provider = NoLLMProvider()
    restarted.llm.register_provider("fake", restarted_provider)
    restarted.config.llm.provider = "fake"
    restarted_app = create_application(
        mary=restarted,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    children = _gap_children(restarted)
    categories = [item.get("gap_category") for item in children]
    assert len(categories) == len(set(categories)) == 5
    goal_child = next(item for item in children if item.get("gap_category") == "goals")
    assert goal_child.get("status") == "resolved"

    result = restarted_app.run("What are you still curious about regarding me?")
    assert "what goals matter most to unbe" not in str(result.output).lower()
    assert restarted_provider.calls == 0


def test_exploring_parent_remains_highest_priority(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)
    app.run("you should be curious about me top priority")
    app.run("remember this: I love creating stories")

    parent = _parent(mary)
    assert parent.get("status") == "exploring"

    ranked = mary.agency.rebuild_priorities()
    assert ranked
    assert ranked[0].description.lower() == "learn more about unbe"
    assert ranked[0].score == 1.0
    assert any(item.metadata.get("relationship_gap") for item in ranked[1:])
    assert provider.calls == 0
