from __future__ import annotations

from mary.cognition.intent import IntentType
from mary.core.mary import Mary
from mary.llm.interface import LLMResponse


class SequenceRouter:
    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or [])
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        system = str(messages[0].content) if messages else ""
        if "Mary's response editor" in system:
            content = (
                self.responses.pop(0)
                if self.responses
                else "I can remember through my memory and creator-model systems; I just don't have that specific fact stored yet."
            )
        else:
            content = self.responses.pop(0) if self.responses else "Yeah. I'm with you."
        return LLMResponse(
            content=content,
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


def _mary(router: SequenceRouter | None = None) -> Mary:
    mary = Mary()
    router = router or SequenceRouter()
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    return mary


def test_current_self_feeling_routes_local_before_dynamic_web_marker():
    mary = _mary()
    intent = mary.cognition.detect_intent(
        "Hey Mary, we've been working on you for quite a while today. How are you feeling about yourself right now?"
    )
    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == "current_state"


def test_creator_memory_overview_routes_to_relationship_model_before_generic_memory():
    mary = _mary()
    intent = mary.cognition.detect_intent("Do you remember anything about me?")
    assert intent.intent_type == IntentType.RELATIONSHIP_QUERY
    assert intent.parameters["relationship_query_type"] == "memory_overview"


def test_creator_memory_overview_knows_creator_and_recent_session_without_llm():
    router = SequenceRouter([
        "Yeah, that makes sense.",
        "Quick updates sound good to me.",
    ])
    mary = _mary(router)
    mary.process("I work best when I'm trusted to do the job without someone over my shoulder.")
    mary.process("I prefer quick updates or checking the work when it's done.")
    calls_before = len(router.calls)

    result = mary.process("Do you remember anything about me?")

    assert result.intent.intent_type == IntentType.RELATIONSHIP_QUERY
    assert len(router.calls) == calls_before
    lowered = result.final_response.lower()
    assert "my creator" in lowered
    assert "current session" in lowered
    assert "quick updates" in lowered
    assert "blank" not in lowered


def test_recent_conversation_recall_is_bounded_instead_of_dumping_full_reply():
    mary = _mary()
    long_reply = "painting and sketching " * 80
    recent = [
        {"role": "user", "content": "What do you like about yourself?"},
        {"role": "assistant", "content": "Tiny details make me happy."},
        {"role": "user", "content": "What would you do all day by yourself?"},
        {"role": "assistant", "content": long_reply},
    ]

    response = mary._handle_conversation_recall(recent)

    assert len(response) < 650
    assert "what would you do all day" in response.lower()
    assert response.count("painting and sketching") < 10
    assert "…" in response


def test_false_blank_page_memory_claim_is_revised():
    router = SequenceRouter([
        "Because I don't store a permanent diary of you. I'm basically a blank page until you give me a cue.",
        "I do have episodic and semantic memory plus a structured model of you; I just may not have that specific detail stored yet.",
    ])
    mary = _mary(router)

    result = mary.process("Why don't you remember every detail I tell you?")

    assert result.reflection.decision.value == "revise"
    assert "blank page" not in result.final_response.lower()
    assert "memory" in result.final_response.lower()


def test_unsupported_background_ping_promise_is_revised():
    router = SequenceRouter([
        "Got it. I'll keep the line open and ping you when I'm done.",
        "Got it. Quick updates when we're actively working, or a check once the work is done—that fits you better.",
    ])
    mary = _mary(router)

    result = mary.process("I prefer quick updates or just check it when you're done.")

    assert result.reflection.decision.value == "revise"
    lowered = result.final_response.lower()
    assert "ping you when" not in lowered
    assert "quick updates" in lowered
