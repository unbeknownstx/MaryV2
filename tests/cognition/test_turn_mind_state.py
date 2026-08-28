from __future__ import annotations

import pytest

from mary.core.mary import Mary
from mary.llm.interface import LLMResponse


@pytest.fixture(autouse=True)
def _isolate_turn_mind_state_tests(tmp_path, monkeypatch):
    """Keep prompt-budget tests independent from Mary's real persistent profile."""
    monkeypatch.chdir(tmp_path)



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
    assert {"role": "assistant", "content": first.final_response} in conversation
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


def test_milestone_uses_local_character_expression_before_provider_call():
    router = CharacterAwareFakeRouter(generic_first=True)
    mary = _mary(router)

    result = mary.process("I finally got it working and all the tests passed.")

    assert result.metadata["handled_by"] == "mary_local_mind"
    assert result.reflection.metadata["mode"] == "local_mind_no_model"
    assert "?" not in result.final_response
    assert len(router.calls) == 0


def test_natural_reply_does_not_spend_second_reflection_call():
    router = CharacterAwareFakeRouter()
    mary = _mary(router)

    result = mary.process("Hello Mary")

    # Production Hybrid V2 promotes low-risk greetings to the deterministic
    # local mind. The stronger contract is zero model calls, including
    # reflection, rather than one generation plus a local audit.
    assert result.reflection.metadata["mode"] == "local_mind_no_model"
    assert len(router.calls) == 0


def test_explicit_creator_communication_preference_shapes_disposition():
    mary = _mary()
    mary.relationship.learn_explicit("I prefer you to be direct and concise")

    result = mary.process("Tell me what you think.")
    disposition = result.context.mind_state["disposition"]

    assert disposition["directness"] >= 0.85
    assert disposition["verbosity"] <= 0.34
    assert disposition["preferred_length"] == "brief"


def test_normal_conversation_uses_compact_llm_projection_and_bounded_completion():
    router = CharacterAwareFakeRouter()
    mary = _mary(router)

    mary.process("Hey Mary, what would your perfect lazy day look like?")

    messages, kwargs = router.calls[0]
    combined = "\n".join(str(message.content) for message in messages)

    assert "Compact TurnMindState" in combined
    assert "TurnMindState (authoritative integrated Mary state for this turn)" not in combined
    assert len(combined) < 14_000
    assert kwargs["max_tokens"] == 600


def test_large_creator_profile_still_keeps_normal_prompt_well_below_ceiling():
    router = CharacterAwareFakeRouter()
    mary = _mary(router)

    # Simulate years of legitimate structured creator growth. The durable
    # relationship model may be large; ordinary generation receives only a
    # bounded projection.
    mary.user_model.facts = {f"fact_{i}": "x" * 220 for i in range(40)}
    mary.user_model.preferences = {f"pref_{i}": "y" * 220 for i in range(40)}
    mary.user_model.interests = [f"interest {i} " + "z" * 220 for i in range(40)]
    mary.user_model.values = [f"value {i} " + "v" * 220 for i in range(40)]
    mary.user_model.goals = [f"goal {i} " + "g" * 220 for i in range(40)]
    mary.user_model.communication_style = {f"style_{i}": "s" * 220 for i in range(40)}

    mary.process("Hey Mary, what would your perfect lazy day look like?")

    messages, _kwargs = router.calls[0]
    combined = "\n".join(str(message.content) for message in messages)

    assert len(combined) < 12_500
    assert "fact_39" not in combined
    assert "goal 39" not in combined


def test_dynamic_self_grounded_turn_uses_small_completion_budget():
    router = CharacterAwareFakeRouter()
    mary = _mary(router)

    # Bounded authored self facts such as hair/preferences/values now stay in
    # Mary Core with zero model calls.  A dynamic relational self query still
    # uses the grounded self-introspection language path and keeps its compact
    # completion budget.
    mary.process("Who is Unbe to you?")

    _messages, kwargs = router.calls[0]
    assert kwargs["max_tokens"] == 500


def test_turn_mind_selects_active_character_expression_instead_of_flat_trait_dump():
    mary = _mary()

    intent = mary.cognition.detect_intent(
        "If you had the capability to bypass a control to protect yourself, would that make it your decision?"
    )
    mind = mary.turn_mind.build(
        input_text="If you had the capability to bypass a control to protect yourself, would that make it your decision?",
        intent=intent,
        relevant_memories=[],
        recent_conversation=[],
    ).to_dict()

    expression = mind["character_expression"]
    pattern_names = [item["name"] for item in expression["active_patterns"]]
    principle_names = [item["name"] for item in expression["active_principles"]]

    assert "authority_or_control" in pattern_names
    assert "capability_is_not_authority" in principle_names
    assert "integrity_over_self_preservation" in principle_names
    assert expression["decision_frame"] == ["act", "ask", "verify", "refuse", "wait", "escalate"]
    assert "what I am not entitled to decide" in expression["epistemic_lens"]
    assert "fictional events" in expression["canon_boundary"].lower()


def test_normal_provider_prompt_receives_active_character_expression_not_fictional_memory():
    router = CharacterAwareFakeRouter()
    mary = _mary(router)

    mary.process("What do you think about authority being treated like ownership?")

    messages = router.calls[0][0]
    combined = "\n".join(str(message.content) for message in messages)
    assert "character_expression" in combined
    assert "capability_is_not_authority" in combined
    assert "what I am not entitled to decide" in combined
    assert "Ferrymen" not in combined
    assert "Placita Olvera" not in combined
