from __future__ import annotations

from mary.core.mary import Mary
from mary.llm.interface import LLMResponse


class CharacterAwareFakeRouter:
    def __init__(self, *, generic_first: bool = False):
        self.calls = []
        self.generic_first = generic_first

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        system = str(messages[0].content) if messages else ""
        if "Mary's response editor" in system:
            return LLMResponse(
                content="Finally. That one fought us way harder than it should have.",
                provider="test",
                model="fake",
            )
        return LLMResponse(
            content=(
                "Great to hear that! Anything else you'd like to tackle next?"
                if self.generic_first
                else "Hey. I'm here."
            ),
            provider="test",
            model="fake",
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "fake"

    def is_available(self, provider=None):
        return True


def _mary(router: CharacterAwareFakeRouter | None = None) -> Mary:
    mary = Mary()
    router = router or CharacterAwareFakeRouter()
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    return mary


def test_turn_mind_state_unifies_existing_mary_subsystems():
    mary = _mary()

    result = mary.process("Hello Mary")
    mind = result.context.mind_state

    assert mind["identity"]["name"] == "Mary"
    assert "canonical_entries" in mind["biography"]
    assert mind["relationship"]["role"] == "creator"
    assert "traits" in mind["personality"]
    assert "tendencies" in mind["character"]
    assert mind["values"]
    assert "top_priorities" in mind["agency"]
    assert "relevant_concepts" in mind["knowledge"]
    assert "summary" in mind["learning"]
    assert "status" in mind["autonomy"]
    assert "registered" in mind["tools"]
    assert "primary" in mind["emotion"]
    assert mind["disposition"]["mode"] == "relational_conversation"


def test_completed_turn_becomes_context_for_next_turn():
    mary = _mary()

    first = mary.process("Hello Mary")
    assert first.metadata["dialogue_recorded"] is True

    second = mary.process("That was interesting.")
    conversation = second.context.conversation

    assert {"role": "user", "content": "Hello Mary"} in conversation
    assert {"role": "assistant", "content": "Hey. I'm here."} in conversation
    assert all(item["content"] != "That was interesting." for item in conversation)


def test_reasoning_prompt_is_character_first_and_uses_turn_mind_state():
    router = CharacterAwareFakeRouter()
    mary = _mary(router)

    mary.process("Tell me what you think.")

    messages = router.calls[0][0]
    system = messages[0].content
    user_prompt = messages[1].content

    assert "You are Mary" in system
    assert "not a generic customer-service assistant" in system
    assert "TurnMindState" in user_prompt
    assert "customer-service assistant" in system.lower()


def test_generic_assistant_reply_is_actually_revised_and_used():
    router = CharacterAwareFakeRouter(generic_first=True)
    mary = _mary(router)

    result = mary.process("I finally got it working and all the tests passed.")

    assert result.reflection.decision.value == "revise"
    assert result.final_response == "Finally. That one fought us way harder than it should have."
    assert result.reflection.revised_response == result.final_response
    assert len(router.calls) == 2


def test_natural_reply_does_not_spend_second_reflection_call():
    router = CharacterAwareFakeRouter()
    mary = _mary(router)

    result = mary.process("Hello Mary")

    assert result.reflection.metadata["mode"] == "local_character_audit"
    assert len(router.calls) == 1


def test_explicit_creator_communication_preference_shapes_disposition():
    mary = _mary()
    mary.relationship.learn_explicit("I prefer you to be direct and concise")

    result = mary.process("Tell me what you think.")
    disposition = result.context.mind_state["disposition"]

    assert disposition["directness"] >= 0.85
    assert disposition["verbosity"] <= 0.34
    assert disposition["preferred_length"] == "brief"
