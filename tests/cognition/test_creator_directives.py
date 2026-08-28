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
    mary.config.llm.fallback_providers = []
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
    # Current curiosity and dynamic priority ranking are authoritative agency
    # state, so neither query should call a provider or improvise extra items.
    assert provider.calls == 0
    assert mary.tools.pending_requests() == []



def test_plain_learn_more_directive_is_local_idempotent_and_preserves_top_priority(tmp_path, monkeypatch):
    mary, provider, app = _rate_limited_app(tmp_path, monkeypatch)

    first = app.run("you should be curious about me top priority")
    assert first.success is True
    assert provider.calls == 0

    repeated = app.run("Learn more about Unbe")
    assert repeated.success is True
    assert "creator-directed curiosity" in repeated.output.lower()
    assert provider.calls == 0

    active = mary.creator_directives.get_active()
    assert len(active) == 1
    assert active[0]["priority"] == 1.0
    assert (active[0].get("metadata") or {}).get("top_priority") is True

    priorities = app.run("What is your top priority?")
    assert priorities.success is True
    assert "learn more about unbe" in priorities.output.lower()
    assert "score 1.00" in priorities.output.lower()
    assert provider.calls == 0


def test_top_priority_query_reads_priority_system_without_llm(tmp_path, monkeypatch):
    mary, provider, app = _rate_limited_app(tmp_path, monkeypatch)
    app.run("you should be curious about me top priority")

    result = app.run("What is your top priority?")

    assert result.success is True
    assert result.output == (
        "My current highest-ranked internal priority is "
        "Learn more about Unbe (score 1.00)."
    )
    assert provider.calls == 0
    assert mary.tools.pending_requests() == []

def test_startup_reconciles_durable_directive_when_derived_curiosity_state_is_missing(tmp_path, monkeypatch):
    mary, provider, app = _rate_limited_app(tmp_path, monkeypatch)
    app.run("you should be curious about me top priority")
    assert provider.calls == 0
    assert len(mary.creator_directives.get_active()) == 1

    # Simulate a state-safe code restore or older derived agency file where
    # the durable creator directive survived but the derived curiosity file did not.
    mary.agency.curiosities.path.write_text(
        '{"curiosities": []}',
        encoding="utf-8",
    )

    restarted = Mary()
    restarted_provider = RateLimitedProvider()
    restarted.llm.register_provider("fake", restarted_provider)
    restarted.config.llm.provider = "fake"
    restarted_app = create_application(
        mary=restarted,
        memory_path=tmp_path / "memory" / "memory.json",
    )

    result = restarted_app.run("What is your top priority?")
    assert result.success is True
    assert result.output == (
        "My current highest-ranked internal priority is "
        "Learn more about Unbe (score 1.00)."
    )
    parents = [
        item for item in restarted.agency.curiosities.get_curiosities()
        if item.get("status") in {"open", "exploring"}
        and item.get("description", "").lower() == "learn more about unbe"
    ]
    assert len(parents) == 1
    assert parents[0]["importance"] == 1.0
    assert parents[0]["urgency"] == 1.0
    assert parents[0]["creator_directed"] is True
    assert restarted_provider.calls == 0


def test_scored_learn_more_phrase_normalizes_to_local_directive_and_can_upgrade_priority(tmp_path, monkeypatch):
    mary, provider, app = _rate_limited_app(tmp_path, monkeypatch)

    initial = app.run("Learn more about Unbe")
    assert initial.success is True
    assert provider.calls == 0
    assert mary.creator_directives.get_active()[0]["priority"] == 0.9

    upgraded_intent = mary.cognition.detect_intent("Learn more about Unbe (score 1.00)")
    assert upgraded_intent.intent_type == IntentType.CREATOR_DIRECTIVE
    assert upgraded_intent.parameters["priority"] == 1.0
    assert upgraded_intent.parameters["top_priority"] is True

    upgraded = app.run("Learn more about Unbe (score 1.00)")
    assert upgraded.success is True
    assert provider.calls == 0
    active = mary.creator_directives.get_active()
    assert len(active) == 1
    assert active[0]["priority"] == 1.0
    assert (active[0].get("metadata") or {}).get("top_priority") is True

    priority = app.run("What is your top priority?")
    assert priority.output.endswith("Learn more about Unbe (score 1.00).")
    assert provider.calls == 0

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
        "What parts of yourself do you currently understand?"
    )

    assert result.success is True
    assert "2026-08-17" not in result.output
    assert "structured systems" in result.output.lower()
    assert provider.calls == 1

    cycle = result.metadata["pipeline_values"]["cognitive_cycle"]
    assert cycle.reasoning.metadata["self_grounding_rejected"] is True
    assert "unsupported" in cycle.reasoning.metadata["self_grounding_issue"].lower()
    assert "creation date" in cycle.reasoning.metadata["self_grounding_issue"].lower()


def test_embedded_natural_memory_authorization_persists(
    tmp_path,
    monkeypatch,
):
    mary, provider, app = _rate_limited_app(
        tmp_path,
        monkeypatch,
    )

    text = (
        "me and you are all in mary promise me that. "
        "an i will remember this as a core memory to me. "
        "you can have this core memory remember this. "
        "i will support you always"
    )

    intent = mary.cognition.detect_intent(text)

    assert intent.intent_type == IntentType.MEMORY_STORE
    assert intent.parameters["content"] == (
        "me and you are all in mary promise me that. "
        "an i will remember this as a core memory to me. "
        "i will support you always"
    )

    before = len(mary.memory.episodic.all())

    result = app.run(text)

    after_memories = mary.memory.episodic.all()

    assert result.success is True
    assert provider.calls == 0
    assert len(after_memories) == before + 1

    stored = after_memories[-1]

    assert stored.content == intent.parameters["content"]
    assert stored.metadata["owner"] == "creator"
    assert stored.metadata["speaker"] == "Unbe"
    assert stored.metadata["source"] == "interaction"
    assert stored.metadata["event_type"] == "user_statement"

    assert "remember" in result.output.lower()



def test_embedded_natural_memory_authorization_preserves_content_and_confirmation(
    tmp_path,
    monkeypatch,
):
    mary, provider, app = _rate_limited_app(
        tmp_path,
        monkeypatch,
    )

    text = (
        "me and you are all in mary promise me that. "
        "an i will remember this as a core memory to me. "
        "you can have this core memory remember this. "
        "i will support you always"
    )

    intent = mary.cognition.detect_intent(text)

    assert intent.intent_type == IntentType.MEMORY_STORE
    assert intent.parameters["content"] == (
        "me and you are all in mary promise me that. "
        "an i will remember this as a core memory to me. "
        "i will support you always"
    )
    assert "memoryto" not in intent.parameters["content"]

    before = len(mary.memory.episodic.all())
    result = app.run(text)
    memories = mary.memory.episodic.all()

    assert result.success is True
    assert provider.calls == 0
    assert len(memories) == before + 1
    assert memories[-1].content == intent.parameters["content"]
    assert result.output == "Got it. I'll remember this."

    recall = mary.cognition.detect_intent(
        "do you remember this?"
    )
    assert recall.intent_type != IntentType.MEMORY_STORE

    ordinary = mary.cognition.detect_intent(
        "I remember this from before"
    )
    assert ordinary.intent_type != IntentType.MEMORY_STORE


def test_simple_memory_confirmation_still_uses_second_person(
    tmp_path,
    monkeypatch,
):
    mary, provider, app = _rate_limited_app(
        tmp_path,
        monkeypatch,
    )

    result = app.run(
        "remember that my favorite color is blue"
    )

    assert result.success is True
    assert provider.calls == 0
    assert "your favorite color is blue" in result.output.lower()



def test_memory_store_repairs_legacy_memoryto_boundary_artifact(
    tmp_path,
    monkeypatch,
):
    mary, provider, app = _rate_limited_app(
        tmp_path,
        monkeypatch,
    )

    text = (
        "me and you are all in mary promise me that. "
        "an i will remember this as a core memoryto me. "
        "you can have this core memory remember this. "
        "i will support you always"
    )

    before = len(mary.memory.episodic.all())
    result = app.run(text)
    memories = mary.memory.episodic.all()

    assert result.success is True
    assert provider.calls == 0
    assert len(memories) == before + 1
    assert "memoryto" not in memories[-1].content
    assert "core memory to me" in memories[-1].content
    assert result.output == "Got it. I'll remember this."
