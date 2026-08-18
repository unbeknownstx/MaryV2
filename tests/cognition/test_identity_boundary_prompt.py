from __future__ import annotations

from mary.core.mary import Mary
from mary.llm.interface import LLMResponse


class PromptCaptureRouter:
    """Offline fake router that captures the exact prompt Mary would send."""

    def __init__(self) -> None:
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return LLMResponse(
            content="I'm Mary. Those details are yours, not mine.",
            provider="test",
            model="identity-boundary-fake",
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "identity-boundary-fake"

    def is_available(self, provider=None):
        return True


def _mary_with_capture_router() -> tuple[Mary, PromptCaptureRouter]:
    mary = Mary()
    router = PromptCaptureRouter()
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    return mary, router


def test_creator_profile_is_explicitly_separated_from_mary_identity():
    mary, router = _mary_with_capture_router()

    mary.relationship.learn_explicit("my favorite color is green")
    mary.relationship.learn_explicit("I love creating stories")
    mary.relationship.learn_explicit("my main goal is finish MaryV2")

    result = mary.process("Hello Mary, who are you?")

    assert result.final_response
    assert router.calls

    messages = router.calls[0][0]
    system_prompt = str(messages[0].content)
    user_prompt = str(messages[1].content)

    assert "Unbe's traits/values/emotions are not yours" in system_prompt
    assert "Creator profile — facts about Unbe only, NOT Mary:" in user_prompt
    assert "Everything in this block describes Unbe, Mary's creator/user" in user_prompt
    assert "Never adopt these facts" in user_prompt
    assert "as Mary's own" in user_prompt
    assert "'you/your' or 'Unbe/Unbe's'" in user_prompt


def test_turn_mind_creator_profile_remains_structured_and_unchanged():
    mary, _ = _mary_with_capture_router()

    result = mary.process("Hello Mary")
    relationship = result.context.mind_state["relationship"]

    assert relationship["role"] == "creator"
    assert "current_profile" in relationship
    assert "facts" in relationship["current_profile"]
    assert "preferences" in relationship["current_profile"]
    assert "interests" in relationship["current_profile"]
    assert "values" in relationship["current_profile"]
    assert "goals" in relationship["current_profile"]
    assert "communication_style" in relationship["current_profile"]
