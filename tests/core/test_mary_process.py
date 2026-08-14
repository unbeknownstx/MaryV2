"""
MaryV2 Mary.process() Integration Tests

Tests Mary's public cognitive entry point without requiring
a real LLM provider or API key.
"""

from mary.core.mary import Mary
from mary.cognition.orchestrator import CognitiveCycleResult
from mary.cognition.intent import IntentType


class FakeLLMResponse:
    """Minimal fake LLM response."""

    def __init__(self, content: str):
        self.content = content
        self.provider = "test"
        self.model = "fake-model"
        self.finish_reason = "stop"
        self.usage = {}


class FakeLLM:
    """Fake language model for integration tests."""

    def generate(
        self,
        messages,
        provider=None,
        temperature=None,
        max_tokens=None,
    ):
        # Reflection request
        if any(
            "Evaluate Mary's proposed response."
            in message.content
            for message in messages
        ):
            return FakeLLMResponse(
                """
DECISION: ACCEPT
CONFIDENCE: 0.95
ASSESSMENT: The response is relevant and appropriate.
ISSUES: NONE
SUGGESTIONS: NONE
"""
            )

        # Reasoning request
        return FakeLLMResponse(
            "Hello! I'm Mary."
        )

    def provider_name(self):
        return "test"

    def model_name(self):
        return "fake-model"

    def is_available(self):
        return True


class FakeRouter:
    """Router-compatible fake LLM."""

    def __init__(self):
        self.llm = FakeLLM()

    def generate(
        self,
        messages,
        provider=None,
        temperature=None,
        max_tokens=None,
    ):
        return self.llm.generate(
            messages=messages,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def provider_name(self, provider=None):
        return self.llm.provider_name()

    def model_name(self, provider=None):
        return self.llm.model_name()

    def is_available(self, provider=None):
        return self.llm.is_available()


def create_test_mary():
    """
    Create Mary and replace her LLM router with a fake router.
    """

    mary = Mary()

    fake_router = FakeRouter()

    mary.llm = fake_router

    mary.reasoning.llm = fake_router
    mary.reflection.llm = fake_router

    return mary


def test_mary_process_returns_cycle_result():
    mary = create_test_mary()

    result = mary.process(
        "Hello Mary"
    )

    assert isinstance(
        result,
        CognitiveCycleResult,
    )


def test_mary_process_preserves_input():
    mary = create_test_mary()

    result = mary.process(
        "Hello Mary"
    )

    assert (
        result.context.input_text
        == "Hello Mary"
    )


def test_mary_process_detects_conversation():
    mary = create_test_mary()

    result = mary.process(
        "Hello Mary"
    )

    assert result.intent is not None

    assert (
        result.intent.intent_type
        == IntentType.CONVERSATION
    )


def test_mary_process_detects_question():
    mary = create_test_mary()

    result = mary.process(
        "How are you?"
    )

    assert result.intent is not None

    assert (
        result.intent.intent_type
        == IntentType.QUESTION
    )


def test_mary_process_includes_user_context():
    mary = create_test_mary()

    result = mary.process(
        "Who am I?"
    )

    assert isinstance(
        result.context.user_context,
        dict,
    )


def test_mary_process_includes_personality_context():
    mary = create_test_mary()

    result = mary.process(
        "Tell me about yourself."
    )

    assert isinstance(
        result.context.personality_context,
        dict,
    )


def test_mary_process_includes_memory_context():
    mary = create_test_mary()

    result = mary.process(
        "Hello Mary"
    )

    assert isinstance(
        result.context.memories,
        list,
    )


def test_mary_process_produces_reasoning():
    mary = create_test_mary()

    result = mary.process(
        "Hello Mary"
    )

    assert result.reasoning is not None
    assert result.reasoning.response


def test_mary_process_produces_reflection():
    mary = create_test_mary()

    result = mary.process(
        "Hello Mary"
    )

    assert result.reflection is not None
    assert result.reflection.decision.value == "accept"


def test_mary_process_produces_final_response():
    mary = create_test_mary()

    result = mary.process(
        "Hello Mary"
    )

    assert result.final_response
    assert (
        result.final_response
        == result.reasoning.response
    )


def test_mary_process_serializes_result():
    mary = create_test_mary()

    result = mary.process(
        "Hello Mary"
    )

    data = result.to_dict()

    assert isinstance(
        data,
        dict,
    )

    assert "context" in data
    assert "intent" in data
    assert "reasoning" in data
    assert "reflection" in data
    assert "final_response" in data
    assert "metadata" in data


def test_mary_process_rejects_empty_input():
    mary = create_test_mary()

    try:
        mary.process("")
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_mary_process_rejects_whitespace_input():
    mary = create_test_mary()

    try:
        mary.process("   ")
        assert False, "Expected ValueError"
    except ValueError:
        pass