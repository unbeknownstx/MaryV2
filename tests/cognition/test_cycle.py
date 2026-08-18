"""
MaryV2 Cognitive Cycle Integration Tests

These tests verify that Mary's cognitive architecture can complete
a full cognitive cycle without requiring a real LLM provider or API key.
"""

from mary.core.mary import Mary

from mary.cognition.intent import IntentType
from mary.cognition.reasoning import ReasoningResult
from mary.cognition.reflection import (
    ReflectionDecision,
    ReflectionResult,
)

from mary.llm.interface import (
    LLMInterface,
    LLMMessage,
    LLMResponse,
)


# ============================================================
# FAKE LLM PROVIDER
# ============================================================


class FakeLLMProvider(LLMInterface):
    """
    Deterministic LLM provider used only for testing.

    No API key.
    No internet.
    No Groq.
    No OpenAI.
    """

    def __init__(self) -> None:

        self.calls: list[
            list[LLMMessage]
        ] = []

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:

        self.calls.append(messages)

        combined = "\n".join(
            message.content
            for message in messages
        )

        # ----------------------------------------------------
        # Reflection response
        # ----------------------------------------------------

        if (
            "Evaluate Mary's proposed response."
            in combined
        ):

            content = (
                "DECISION: ACCEPT\n"
                "CONFIDENCE: 0.95\n"
                "ASSESSMENT: "
                "The response is relevant, clear, and appropriate.\n"
                "ISSUES: NONE\n"
                "SUGGESTIONS: NONE"
            )

        # ----------------------------------------------------
        # Reasoning response
        # ----------------------------------------------------

        else:

            content = (
                "Hello. I am Mary, and I understand "
                "your message."
            )

        return LLMResponse(
            content=content,
            provider="fake",
            model="test-model",
            finish_reason="stop",
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 10,
                "total_tokens": 20,
            },
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake"

    def model_name(self) -> str:
        return "test-model"


# ============================================================
# TEST MARY FACTORY
# ============================================================


def create_test_mary() -> tuple[
    Mary,
    FakeLLMProvider,
]:
    """
    Create Mary using the fake LLM provider.

    The fake provider is registered AND explicitly selected
    so the real Groq/OpenAI providers are never loaded.
    """

    mary = Mary()

    fake_llm = FakeLLMProvider()

    mary.llm.register_provider(
        "fake",
        fake_llm,
    )

    # IMPORTANT:
    # Select the fake provider before cognition runs.
    mary.config.llm.provider = "fake"

    return mary, fake_llm


# ============================================================
# BASIC CYCLE
# ============================================================


def test_cognitive_cycle_returns_result():

    mary, _ = create_test_mary()

    result = mary.cognition.process(
        input_text="Hello Mary",
        intent=None,
    )

    assert result is not None


def test_cognitive_cycle_contains_context():

    mary, _ = create_test_mary()

    result = mary.cognition.process(
        input_text="Hello Mary",
    )

    assert result.context.input_text == "Hello Mary"


# ============================================================
# INTENT
# ============================================================


def test_cognitive_cycle_detects_conversation_intent():

    mary, _ = create_test_mary()

    result = mary.cognition.process(
        input_text="Hello Mary",
    )

    assert result.intent is not None

    assert (
        result.intent.intent_type
        == IntentType.CONVERSATION
    )


# ============================================================
# REASONING
# ============================================================


def test_cognitive_cycle_produces_reasoning():

    mary, _ = create_test_mary()

    result = mary.cognition.process(
        input_text="Hello Mary",
    )

    assert isinstance(
        result.reasoning,
        ReasoningResult,
    )

    assert result.reasoning.response


# ============================================================
# REFLECTION
# ============================================================


def test_cognitive_cycle_produces_reflection():

    mary, _ = create_test_mary()

    result = mary.cognition.process(
        input_text="Hello Mary",
    )

    assert isinstance(
        result.reflection,
        ReflectionResult,
    )

    assert (
        result.reflection.decision
        == ReflectionDecision.ACCEPT
    )


# ============================================================
# FINAL RESPONSE
# ============================================================


def test_cognitive_cycle_produces_final_response():

    mary, _ = create_test_mary()

    result = mary.cognition.process(
        input_text="Hello Mary",
    )

    assert result.final_response

    assert (
        result.final_response
        == result.reasoning.response
    )


# ============================================================
# SERIALIZATION
# ============================================================


def test_cognitive_cycle_serializes():

    mary, _ = create_test_mary()

    result = mary.cognition.process(
        input_text="Hello Mary",
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


# ============================================================
# PROVIDER USAGE
# ============================================================


def test_normal_cycle_uses_one_llm_call_when_character_audit_passes():

    mary, fake_llm = create_test_mary()

    mary.cognition.process(
        input_text="Hello Mary",
    )

    # Reasoning uses one provider call. Reflection is local when the
    # response already passes Mary's character/continuity audit.
    assert len(fake_llm.calls) == 1