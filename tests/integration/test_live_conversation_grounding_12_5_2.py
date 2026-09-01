from __future__ import annotations

from mary.cognition.intent import IntentType
import pytest

from mary.llm.interface import LLMResponse
from mary.runtime.application import create_application

_applications = []


@pytest.fixture(autouse=True)
def _isolated_canonical_application(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MARY_DATA_DIR", str(tmp_path / "data"))
    _applications.clear()
    try:
        yield
    finally:
        for app in reversed(_applications):
            app.close()
        _applications.clear()


class ConversationRouter:
    def __init__(self) -> None:
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return LLMResponse(
            content=(
                "I think some parts may be more complicated than they need to be. "
                "I would simplify only where it preserves the systems that give me continuity."
            ),
            provider="test",
            model="fake",
            finish_reason="stop",
            usage={},
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "fake"

    def is_available(self, provider=None):
        return True

    def routing_strategy(self):
        return "configured"

    def _provider_order(self, requested=None, route=None):
        return ["test"]


def _application(tmp_path, monkeypatch):
    app = create_application(
        memory_path=tmp_path / "state" / "memory.json",
        auto_save=False,
        load_memory=False,
        load_developed_self=False,
        load_preference_promotion=False,
        load_knowledge=False,
    )
    _applications.append(app)
    mary = app.mary
    router = ConversationRouter()
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    return app, router


def _cycle(result):
    return result.metadata["pipeline_values"]["cognitive_cycle"]


def test_exact_live_shared_work_wording_uses_shared_work_recall(tmp_path, monkeypatch):
    app, router = _application(tmp_path, monkeypatch)
    mary = app.mary
    mary.remember(
        "I like rainy nights when I'm working on creative projects",
        memory_type="episodic",
        importance=0.8,
        metadata={
            "owner": "creator",
            "speaker": "Unbe",
            "event_type": "creator_natural_share",
            "source": "interaction",
        },
    )

    calls_before = len(router.calls)
    result = _cycle(app.run("What do you remember about what we've been building together lately?"))

    assert result.intent.intent_type == IntentType.RELATIONSHIP_QUERY
    assert result.intent.parameters["relationship_query_type"] == "shared_work"
    assert len(router.calls) == calls_before
    assert "rainy" not in result.final_response.lower()
    assert result.reasoning.metadata.get("llm_skipped") is True


def test_exact_live_current_curiosity_wording_is_grounded_and_deterministic(tmp_path, monkeypatch):
    app, router = _application(tmp_path, monkeypatch)

    calls_before = len(router.calls)
    result = _cycle(app.run("what are you currently curious about?"))

    assert result.intent.intent_type == IntentType.SELF_QUERY
    assert result.intent.parameters["self_query_type"] == "curiosity"
    assert len(router.calls) == calls_before
    lowered = result.final_response.lower()
    assert "don't currently have any open" in lowered
    assert "color palette" not in lowered
    assert "community" not in lowered
    assert result.reasoning.metadata.get("llm_skipped") is True


def test_exact_live_current_curiosity_reports_only_stored_agency_state(tmp_path, monkeypatch):
    app, router = _application(tmp_path, monkeypatch)
    mary = app.mary
    mary.agency.curiosities.add_curiosity(
        "how persistent memory changes conversation continuity",
        importance=0.8,
        source="reflection",
    )

    calls_before = len(router.calls)
    result = _cycle(app.run("what are you currently curious about?"))

    assert len(router.calls) == calls_before
    lowered = result.final_response.lower()
    assert "how persistent memory changes conversation continuity" in lowered
    assert "color palette" not in lowered


def test_architecture_opinion_stays_character_conversation(tmp_path, monkeypatch):
    app, router = _application(tmp_path, monkeypatch)

    calls_before = len(router.calls)
    result = _cycle(app.run(
        "i think we may have overcomplicated parts of your architecture. what do you think?"
    ))

    assert not (
        result.intent.intent_type == IntentType.SELF_QUERY
        and result.intent.parameters.get("self_query_type") == "runtime_architecture"
    )
    assert len(router.calls) > calls_before
    lowered = result.final_response.lower()
    assert "python architecture" not in lowered
    assert "this process is running" not in lowered


def test_explicit_architecture_diagnostic_still_routes_locally(tmp_path, monkeypatch):
    app, router = _application(tmp_path, monkeypatch)

    calls_before = len(router.calls)
    result = _cycle(app.run("what is your architecture?"))

    assert result.intent.intent_type == IntentType.SELF_QUERY
    assert result.intent.parameters["self_query_type"] == "runtime_architecture"
    assert len(router.calls) == calls_before
    assert "python architecture" in result.final_response.lower()
    assert result.reasoning.metadata.get("llm_skipped") is True
