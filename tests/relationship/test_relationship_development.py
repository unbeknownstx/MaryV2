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
        raise AssertionError("relationship-local paths must not call the LLM")

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "no-llm-relationship-test"


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


def test_what_do_you_know_about_me_routes_to_relationship_model(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)

    intent = mary.cognition.detect_intent("What do you know about me?")

    assert intent.intent_type == IntentType.RELATIONSHIP_QUERY
    result = app.run("What do you know about me?")
    assert result.success is True
    assert "my creator" in result.output.lower()
    assert provider.calls == 0


def test_remember_explicit_preference_updates_structured_model(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)

    result = app.run("remember this: my favorite color is green")

    assert result.success is True
    assert mary.user_model.preferences["favorite_color"] == "green"
    records = mary.user_model.get_profile_records(category="preference")
    assert len(records) == 1
    assert records[0]["explicitly_shared"] is True
    assert records[0]["source"] == "explicit_memory"
    assert provider.calls == 0


def test_new_preference_supersedes_current_but_preserves_history(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)

    app.run("remember this: my favorite color is blue")
    app.run("remember this: my favorite color is green")

    assert mary.user_model.preferences["favorite_color"] == "green"
    history = mary.user_model.get_profile_records(
        category="preference",
        current_only=False,
    )
    assert [item["status"] for item in history] == ["historical", "current"]
    assert [item["value"] for item in history] == ["blue", "green"]
    assert provider.calls == 0


def test_explicit_interest_and_goal_are_structured_and_queryable(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)

    app.run("remember this: I love creating stories")
    app.run("learn this about me: my goal is finish MaryV2")

    assert "creating stories" in [item.lower() for item in mary.user_model.interests]
    assert "finish MaryV2" in mary.user_model.goals

    interests = app.run("What do you know about my interests?")
    goals = app.run("What do you know about my goals?")

    assert "creating stories" in interests.output.lower()
    assert "finish maryv2" in goals.output.lower()
    assert provider.calls == 0



def test_explicit_generic_my_fact_is_structured(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)

    app.run("remember this: my test animal is a red panda")

    assert mary.user_model.facts["test_animal"] == "a red panda"
    assert provider.calls == 0

def test_unstructured_philosophical_memory_is_not_silently_profiled(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)

    app.run("remember this: existence is always precious")

    assert mary.user_model.get_profile_records(current_only=False) == []
    assert provider.calls == 0


def test_explicit_general_relationship_share_is_source_aware(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)

    result = app.run("learn this about me: I tend to create in quiet moments")

    assert result.success is True
    records = mary.user_model.get_profile_records(category="general")
    assert len(records) == 1
    assert records[0]["explicitly_shared"] is True
    assert records[0]["confidence"] == 1.0
    assert records[0]["source"] == "creator_explicit"
    assert provider.calls == 0


def test_relationship_model_survives_restart(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)
    app.run("remember this: I love creating stories")
    app.run("remember this: my favorite color is green")
    app.close()

    restarted = Mary()
    restarted_provider = NoLLMProvider()
    restarted.llm.register_provider("fake", restarted_provider)
    restarted.config.llm.provider = "fake"
    restarted_app = create_application(
        mary=restarted,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    result = restarted_app.run("What do you know about me?")

    assert result.success is True
    assert "creating stories" in result.output.lower()
    assert "favorite color = green" in result.output.lower()
    assert restarted_provider.calls == 0


def test_creator_curiosity_tracks_relationship_learning_progress(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)

    app.run("you should be curious about me top priority")
    app.run("remember this: I love creating stories")

    curiosities = mary.agency.curiosities.get_exploring_curiosities()
    assert len(curiosities) == 1
    curiosity = curiosities[0]
    assert curiosity["description"].lower() == "learn more about unbe"
    assert curiosity["progress_count"] == 1
    assert curiosity["last_learned_category"] == "interest"
    assert curiosity["last_learned_value"].lower() == "creating stories"
    assert provider.calls == 0


def test_creator_values_do_not_modify_marys_own_values(tmp_path, monkeypatch):
    mary, provider, app = _app(tmp_path, monkeypatch)
    mary_value_names_before = [item["name"] for item in mary.values.get_priorities()]

    app.run("remember this: I value patience")

    assert "patience" in [item.lower() for item in mary.user_model.values]
    mary_value_names_after = [item["name"] for item in mary.values.get_priorities()]
    assert mary_value_names_after == mary_value_names_before
    assert provider.calls == 0


def test_existing_explicit_memories_bootstrap_structured_relationship_model(tmp_path, monkeypatch):
    from mary.memory.manager import MemoryManager

    monkeypatch.chdir(tmp_path)
    memory_path = tmp_path / "memory" / "memory.json"
    memory = MemoryManager(storage_path=memory_path, auto_save=True)
    memory.remember("my favorite color is blue", metadata={"owner": "creator"})
    memory.remember("my favorite color is green", metadata={"owner": "creator"})
    memory.remember("my test animal is a red panda", metadata={"owner": "creator"})
    memory.remember("existence is always precious", metadata={"owner": "creator"})
    memory.save()

    mary = Mary()
    provider = NoLLMProvider()
    mary.llm.register_provider("fake", provider)
    mary.config.llm.provider = "fake"
    app = create_application(
        mary=mary,
        memory_path=memory_path,
    )

    result = app.run("What do you know about me?")

    assert mary.user_model.preferences["favorite_color"] == "green"
    assert mary.user_model.facts["test_animal"] == "a red panda"
    assert "favorite color = green" in result.output.lower()
    assert "test animal = a red panda" in result.output.lower()
    assert "existence is always precious" not in result.output.lower()
    assert provider.calls == 0
