"""
MaryV2 Cognitive Orchestrator Tests

Tests the complete cognitive orchestration layer without requiring
a real LLM provider or API connection.
"""

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import IntentType
from mary.cognition.orchestrator import (
    CognitiveOrchestrator,
    CognitiveCycleResult,
)
from mary.cognition.reasoning import (
    ReasoningEngine,
    ReasoningResult,
)
from mary.cognition.reflection import (
    ReflectionDecision,
    ReflectionEngine,
    ReflectionResult,
)


class FakeLLMResponse:
    """Minimal fake LLM response."""

    def __init__(
        self,
        content: str,
    ):
        self.content = content
        self.provider = "test"
        self.model = "fake-model"
        self.finish_reason = "stop"
        self.usage = {}


class FakeLLM:
    """
    Fake LLM used to test cognition without an API.
    """

    def __init__(self):
        self.calls = []

    def generate(
        self,
        messages,
        provider=None,
        temperature=None,
        max_tokens=None,
    ):
        self.calls.append(messages)

        # Reflection requests contain "Evaluate Mary's proposed response."
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
    """
    Router-shaped wrapper around the fake LLM.
    """

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


def create_orchestrator():
    """
    Create a cognitive orchestrator using the fake LLM.
    """

    router = FakeRouter()

    reasoning = ReasoningEngine(
        llm=router,
    )

    reflection = ReflectionEngine(
        llm=router,
    )

    orchestrator = CognitiveOrchestrator(
        reasoning_engine=reasoning,
        reflection_engine=reflection,
    )

    return orchestrator


def test_orchestrator_returns_cycle_result():
    orchestrator = create_orchestrator()

    result = orchestrator.process(
        input_text="Hello Mary",
    )

    assert isinstance(
        result,
        CognitiveCycleResult,
    )


def test_orchestrator_creates_context():
    orchestrator = create_orchestrator()

    result = orchestrator.process(
        input_text="Hello Mary",
    )

    assert isinstance(
        result.context,
        CognitiveContext,
    )

    assert result.context.input_text == "Hello Mary"


def test_orchestrator_detects_conversation_intent():
    orchestrator = create_orchestrator()

    result = orchestrator.process(
        input_text="Hello Mary",
    )

    assert result.intent is not None

    assert (
        result.intent.intent_type
        == IntentType.CONVERSATION
    )


def test_orchestrator_detects_question_intent():
    orchestrator = create_orchestrator()

    result = orchestrator.process(
        input_text="How are you?",
    )

    assert result.intent is not None

    assert (
        result.intent.intent_type
        == IntentType.QUESTION
    )


def test_orchestrator_detects_request_intent():
    orchestrator = create_orchestrator()

    result = orchestrator.process(
        input_text="Please help me.",
    )

    assert result.intent is not None

    assert (
        result.intent.intent_type
        == IntentType.REQUEST
    )


def test_orchestrator_detects_goal_intent():
    orchestrator = create_orchestrator()

    result = orchestrator.process(
        input_text="I have a goal to learn Python.",
    )

    assert result.intent is not None

    assert (
        result.intent.intent_type
        == IntentType.GOAL
    )


def test_orchestrator_propagates_conversation_context():
    orchestrator = create_orchestrator()

    conversation = [
        {
            "role": "user",
            "content": "Hello",
        },
        {
            "role": "assistant",
            "content": "Hi!",
        },
    ]

    result = orchestrator.process(
        input_text="How are you?",
        conversation=conversation,
    )

    assert result.context.conversation == conversation


def test_orchestrator_propagates_memory_context():
    orchestrator = create_orchestrator()

    memories = [
        {
            "content": "Mary remembers a previous conversation.",
        }
    ]

    result = orchestrator.process(
        input_text="Do you remember?",
        memories=memories,
    )

    assert result.context.memories == memories


def test_orchestrator_propagates_user_context():
    orchestrator = create_orchestrator()

    user_context = {
        "name": "Unbe",
        "relationship": "creator",
    }

    result = orchestrator.process(
        input_text="Who am I?",
        user_context=user_context,
    )

    assert (
        result.context.user_context
        == user_context
    )


def test_orchestrator_propagates_personality_context():
    orchestrator = create_orchestrator()

    personality_context = {
        "warmth": 0.8,
        "curiosity": 0.9,
    }

    result = orchestrator.process(
        input_text="Tell me something.",
        personality_context=personality_context,
    )

    assert (
        result.context.personality_context
        == personality_context
    )


def test_orchestrator_produces_reasoning():
    orchestrator = create_orchestrator()

    result = orchestrator.process(
        input_text="Hello Mary",
    )

    assert isinstance(
        result.reasoning,
        ReasoningResult,
    )

    assert result.reasoning.response

    assert (
        result.reasoning.intent
        == result.intent
    )


def test_orchestrator_produces_reflection():
    orchestrator = create_orchestrator()

    result = orchestrator.process(
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


def test_orchestrator_produces_final_response():
    orchestrator = create_orchestrator()

    result = orchestrator.process(
        input_text="Hello Mary",
    )

    assert result.final_response

    assert (
        result.final_response
        == result.reasoning.response
    )


def test_orchestrator_serializes_result():
    orchestrator = create_orchestrator()

    result = orchestrator.process(
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


def test_orchestrator_rejects_empty_input():
    orchestrator = create_orchestrator()

    result = orchestrator.process(
        input_text="",
    )

    assert result.intent is not None

    assert (
        result.intent.intent_type
        == IntentType.UNKNOWN
    )


def test_orchestrator_accepts_explicit_intent():
    orchestrator = create_orchestrator()

    from mary.cognition.intent import Intent

    intent = Intent(
        intent_type=IntentType.QUESTION,
        confidence=1.0,
        description="Explicit test intent.",
        source="test",
    )

    result = orchestrator.process(
        input_text="Hello Mary",
        intent=intent,
    )

    assert result.intent is intent

    assert (
        result.intent.intent_type
        == IntentType.QUESTION
    )