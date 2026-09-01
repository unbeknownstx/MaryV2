"""
MaryV2 Full-System Integration Tests

These tests verify that the major V2 subsystems are not merely present,
but share the correct objects and cooperate across subsystem boundaries.

No internet, real LLM provider, microphone, speaker, or avatar engine is used.
"""

import pytest

from mary.core.lifecycle import LifecycleState
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.expression.emotion import Emotion
from mary.autonomy.runtime import AutonomyRuntimeStatus
from mary.runtime.application import create_application

_applications = []


@pytest.fixture(autouse=True)
def _close_canonical_applications(tmp_path, monkeypatch):
    monkeypatch.setenv("MARY_DATA_DIR", str(tmp_path / "data"))
    _applications.clear()
    try:
        yield
    finally:
        for app in reversed(_applications):
            app.close()
        _applications.clear()


class FakeLLMProvider(LLMInterface):
    """Deterministic provider for full-system tests."""

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        combined = "\n".join(
            message.content
            for message in messages
        )

        if "Evaluate Mary's proposed response." in combined:
            content = (
                "DECISION: ACCEPT\n"
                "CONFIDENCE: 0.95\n"
                "ASSESSMENT: The response is appropriate.\n"
                "ISSUES: NONE\n"
                "SUGGESTIONS: NONE"
            )
        else:
            content = "Hello. I am Mary."

        return LLMResponse(
            content=content,
            provider="fake",
            model="test-model",
            finish_reason="stop",
            usage={},
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "test-model"


def _mary(tmp_path):
    app = create_application(
        memory_path=tmp_path / "state" / "memory.json",
        developed_self_path=tmp_path / "state" / "developed_self.json",
        preference_promotion_path=tmp_path / "state" / "preference_promotion.json",
        knowledge_path=tmp_path / "state" / "knowledge.json",
        auto_save=False,
        load_memory=False,
        load_developed_self=False,
        load_preference_promotion=False,
        load_knowledge=False,
    )
    _applications.append(app)
    return app.mary


def configure_fake_llm(mary) -> FakeLLMProvider:
    provider = FakeLLMProvider()
    mary.llm.register_provider("fake", provider)
    mary.config.llm.provider = "fake"
    return provider


def test_shared_subsystem_identity(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = _mary(tmp_path)

    assert mary.self_model.personality is mary.personality
    assert mary.self_model.character is mary.character

    assert (
        mary.agency.decisions.priority_system
        is mary.agency.priorities
    )

    assert mary.conversation.router is mary.llm
    assert mary.evaluator.llm is mary.llm

    assert mary.expression.emotion is mary.emotion
    assert mary.expression.response is mary.response
    assert mary.expression.dialogue is mary.dialogue

    assert mary.avatar.emotion_manager is mary.emotion


def test_identity_biography_character_consistency(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = _mary(tmp_path)

    assert mary.self_model.name == "Mary"
    assert mary.personality.name == "Mary"

    identity = mary.self_model.identity()
    assert identity["name"] == "Mary"

    biography_name = mary.biography.get(
        "identity",
        "Name",
    )
    assert biography_name is not None
    assert biography_name.content == "Mary"

    description = mary.describe_self()
    assert "Mary" in description


def test_memory_persists_across_fresh_mary_instances(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory_path = tmp_path / "memory" / "memory.json"

    first_app = create_application(
        memory_path=memory_path,
        auto_save=True,
        load_memory=True,
        load_developed_self=False,
        load_preference_promotion=False,
        load_knowledge=False,
    )
    _applications.append(first_app)
    first = first_app.mary
    configure_fake_llm(first)

    stored = first_app.run(
        "remember that my favorite color is blue"
    )

    assert (
        "your favorite color is blue"
        in stored.output.lower()
    )
    assert memory_path.exists()

    stored_memory = first.memory.episodic.all()[0]
    assert stored_memory.content == "my favorite color is blue"
    assert stored_memory.metadata["owner"] == "creator"
    assert stored_memory.metadata["speaker"] == "Unbe"

    second_app = create_application(
        memory_path=memory_path,
        auto_save=True,
        load_memory=True,
        load_developed_self=False,
        load_preference_promotion=False,
        load_knowledge=False,
    )
    _applications.append(second_app)
    second = second_app.mary
    configure_fake_llm(second)

    recalled = second_app.run(
        "what is my favorite color?"
    )

    assert (
        "your favorite color is blue"
        in recalled.output.lower()
    )
    assert second.memory.episodic.count() >= 1

    reloaded_memory = second.memory.episodic.all()[0]
    assert reloaded_memory.content == "my favorite color is blue"
    assert reloaded_memory.metadata["owner"] == "creator"


def test_knowledge_learning_evaluation_and_research_boundary(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    mary = _mary(tmp_path)

    concept = mary.knowledge.learn(
        name="MaryV2 integration",
        statement="MaryV2 connects its major subsystems.",
        confidence=0.9,
        importance=0.8,
    )

    results = mary.knowledge.search("MaryV2 subsystems")
    assert results
    assert results[0].concept.id == concept.id

    event = mary.learn(
        event_type="integration",
        subject="full-system verification",
        content="The connected subsystems cooperated successfully.",
        confidence=0.9,
        usefulness=0.9,
    )
    assert mary.learner.get(event.id) is event

    evaluation = mary.evaluator.evaluate(
        subject="integration",
        statement="The connected subsystems cooperated successfully.",
        context="MaryV2 full-system verification",
    )
    assert evaluation is not None
    assert 0.0 <= evaluation.confidence <= 1.0

    request = mary.researcher.create_request(
        "MaryV2 test research",
        purpose="verify safe no-web behavior",
    )
    result = mary.researcher.research(request)

    assert mary.researcher.web_tool is None
    assert result.sources == []
    assert request.status == "completed"


def test_agency_to_decision_does_not_auto_execute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = _mary(tmp_path)

    goal = mary.agency.goals.add_goal(
        "Finish MaryV2 integration verification",
        importance=0.95,
    )
    assert goal is not None

    intention = mary.agency.intentions.add_intention(
        "Run the full integration suite",
        priority=0.8,
        goal_id=goal["id"],
    )
    assert intention is not None

    curiosity = mary.agency.curiosities.add_curiosity(
        "Understand any remaining integration gaps",
        importance=0.6,
        source="integration_test",
    )
    assert curiosity is not None

    priorities = mary.agency.rebuild_priorities()
    assert priorities

    decision = mary.agency.evaluate(
        context={"phase": "integration"},
        rebuild=False,
    )
    assert decision is not None
    assert decision.status == "proposed"

    assert mary.autonomy.status == AutonomyRuntimeStatus.STOPPED
    assert mary.autonomy.stopped is True
    assert mary.autonomy.snapshot().action_count == 0


def test_expression_dialogue_avatar_and_audio_are_coherent(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    mary = _mary(tmp_path)

    mary.dialogue.begin_turn("Hello Mary")

    mary.emotion.signal(
        Emotion.JOY,
        0.7,
        source="integration_test",
        reason="successful verification",
    )

    response = mary.expression.build_response(
        "Hello from the expression system."
    )

    mary.expression.record_response(response)

    recent = mary.dialogue.recent_text(limit=2)
    assert recent == [
        "Hello Mary",
        "Hello from the expression system.",
    ]

    avatar_state = mary.avatar.present_response(response)
    assert avatar_state.text == response.text
    assert avatar_state.emotion == response.emotion.value

    audio_state = mary.audio.state
    assert audio_state.status.value == "inactive"
    assert audio_state.input_active is False
    assert audio_state.output_active is False
    assert mary.audio.input_service.is_active is False
    assert mary.audio.output_service.is_active is False


def test_conversation_uses_shared_router(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = _mary(tmp_path)
    configure_fake_llm(mary)

    response = mary.conversation.respond("Hello Mary")

    assert response.content == "Hello. I am Mary."
    assert response.provider == "fake"
    assert mary.conversation.router is mary.llm


def test_lifecycle_transitions_are_explicit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = _mary(tmp_path)

    assert mary.lifecycle.state == LifecycleState.READY
    assert mary.lifecycle.is_awake is False
    assert mary.lifecycle.is_running is False

    mary.lifecycle.wake()
    assert mary.lifecycle.state == LifecycleState.AWAKE
    assert mary.lifecycle.is_awake is True

    mary.lifecycle.start()
    assert mary.lifecycle.state == LifecycleState.RUNNING
    assert mary.lifecycle.is_running is True

    mary.lifecycle.shutdown()
    assert mary.lifecycle.state == LifecycleState.SHUTTING_DOWN

    mary.lifecycle.stop()
    assert mary.lifecycle.state == LifecycleState.STOPPED
    assert mary.lifecycle.is_running is False
