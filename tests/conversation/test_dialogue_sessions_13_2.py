from __future__ import annotations

from mary.core.mary import Mary
from mary.core.service import MaryCoreService
from mary.expression.dialogue import DialogueManager
from mary.expression.response import ResponseBuilder
from mary.llm.interface import LLMResponse
from mary.protocol.models import TurnRequest
from mary.runtime.application import create_application


class SessionRouter:
    def __init__(self):
        self.calls = 0

    def generate(self, messages, **kwargs):
        self.calls += 1
        system = str(messages[0].content) if messages else ""
        if "Evaluate Mary's proposed response." in system:
            return LLMResponse(
                content=(
                    "DECISION: ACCEPT\n"
                    "CONFIDENCE: 0.95\n"
                    "ASSESSMENT: grounded\n"
                    "ISSUES: NONE\n"
                    "SUGGESTIONS: NONE"
                ),
                provider="test",
                model="session-test",
            )
        return LLMResponse(
            content=f"session reply {self.calls}",
            provider="test",
            model="session-test",
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "session-test"

    def is_available(self, provider=None):
        return True


def _mary(tmp_path, monkeypatch) -> Mary:
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    router = SessionRouter()
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    return mary


def test_dialogue_manager_keeps_bounded_histories_per_conversation():
    dialogue = DialogueManager(
        max_history=8,
        max_sessions=4,
    )
    responses = ResponseBuilder()

    dialogue.select_session("conversation-a")
    dialogue.begin_turn("alpha")
    dialogue.begin_thinking()
    dialogue.add_response(
        responses.build("alpha reply")
    )
    dialogue.finish_turn()

    dialogue.select_session("conversation-b")
    assert dialogue.recent_text() == []

    dialogue.begin_turn("beta")
    dialogue.begin_thinking()
    dialogue.add_response(
        responses.build("beta reply")
    )
    dialogue.finish_turn()

    dialogue.select_session("conversation-a")
    assert dialogue.recent_text() == [
        "alpha",
        "alpha reply",
    ]

    dialogue.select_session("conversation-b")
    assert dialogue.recent_text() == [
        "beta",
        "beta reply",
    ]

    status = dialogue.session_status()
    assert status["session_count"] == 2
    assert status["active_conversation_id"] == "conversation-b"


def test_mary_uses_conversation_id_for_short_term_dialogue_only(
    tmp_path,
    monkeypatch,
):
    mary = _mary(
        tmp_path,
        monkeypatch,
    )

    first = mary.process(
        "Alpha session marker.",
        turn_context={
            "conversation_id": "conversation-a",
            "device_id": "iphone",
        },
    )

    mary.process(
        "Beta session marker.",
        turn_context={
            "conversation_id": "conversation-b",
            "device_id": "mac",
        },
    )

    resumed = mary.process(
        "Alpha resumed marker.",
        turn_context={
            "conversation_id": "conversation-a",
            "device_id": "windows-pc",
        },
    )

    assert first.metadata["conversation_id"] == "conversation-a"
    assert resumed.metadata["conversation_id"] == "conversation-a"
    assert resumed.metadata["dialogue_session_count"] == 2

    mary.dialogue.select_session(
        "conversation-a"
    )
    alpha_history = "\n".join(
        mary.dialogue.recent_text(
            limit=20
        )
    )
    assert "Alpha session marker." in alpha_history
    assert "Alpha resumed marker." in alpha_history
    assert "Beta session marker." not in alpha_history

    mary.dialogue.select_session(
        "conversation-b"
    )
    beta_history = "\n".join(
        mary.dialogue.recent_text(
            limit=20
        )
    )
    assert "Beta session marker." in beta_history
    assert "Alpha session marker." not in beta_history

    # The session switch did not create another character state authority.
    assert mary.relationship is mary.turn_mind.relationship
    assert mary.memory is mary.growth.mary.memory


def test_core_reports_dialogue_sessions_around_one_application(
    tmp_path,
    monkeypatch,
):
    mary = _mary(
        tmp_path,
        monkeypatch,
    )

    app = create_application(
        mary=mary,
        memory_path=(
            tmp_path
            / "memory"
            / "memory.json"
        ),
    )

    core = MaryCoreService(
        app,
        instance_id="session-test-core",
    )

    first = core.process_turn(
        TurnRequest(
            text="First device turn.",
            conversation_id="creator-primary",
            device_id="iphone",
        )
    )
    second = core.process_turn(
        TurnRequest(
            text="Separate project conversation.",
            conversation_id="project-maryv2",
            device_id="windows-pc",
        )
    )

    assert first.conversation_id == "creator-primary"
    assert second.conversation_id == "project-maryv2"

    status = core.conversation_status()
    dialogue = status["dialogue"]

    assert dialogue["session_count"] == 2
    assert (
        dialogue["active_conversation_id"]
        == "project-maryv2"
    )
    assert set(
        dialogue["sessions"]
    ) == {
        "creator-primary",
        "project-maryv2",
    }
