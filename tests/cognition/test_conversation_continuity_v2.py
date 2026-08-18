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
            return LLMResponse(
                content="Maybe a little. I think the bigger problem was integration, not the architecture itself.",
                provider="test",
                model="fake",
            )
        content = self.responses.pop(0) if self.responses else "Yeah. I'm with you."
        return LLMResponse(content=content, provider="test", model="fake")

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "fake"

    def is_available(self, provider=None):
        return True


def _mary(router: SequenceRouter | None = None) -> Mary:
    mary = Mary()
    router = router or SequenceRouter()
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    return mary


def test_recent_dialogue_recall_is_detected_before_long_term_memory():
    mary = _mary()
    intent = mary.cognition.detect_intent(
        "What do you remember from what we were just talking about?"
    )
    assert intent.intent_type == IntentType.CONVERSATION_RECALL


def test_recent_dialogue_recall_uses_dialogue_and_zero_llm_calls():
    router = SequenceRouter([
        "Maybe. I think some of it is more architecture than we needed.",
        "I know. I won't agree just to agree.",
    ])
    mary = _mary(router)
    mary.process("I think we might have overengineered some of this.")
    mary.process("You can disagree with me, you know.")
    calls_before = len(router.calls)

    result = mary.process("What do you remember from what we were just talking about?")

    assert result.intent.intent_type == IntentType.CONVERSATION_RECALL
    assert len(router.calls) == calls_before
    assert "overengineered" in result.final_response.lower()
    assert "disagree" in result.final_response.lower()


def test_turn_mind_contains_conversational_drive_and_question_budget():
    router = SequenceRouter(["What part of it felt overbuilt to you?"])
    mary = _mary(router)
    mary.process("We've built a lot today.")

    result = mary.process("I think we might have overengineered some of this.")
    continuity = result.context.mind_state["continuity"]

    assert continuity["drive"] == "opine"
    assert continuity["allow_follow_up_question"] is False
    assert result.context.mind_state["disposition"]["follow_up_urge"] == 0.0


def test_second_consecutive_question_is_rewritten_to_statement():
    router = SequenceRouter([
        "What part of the build gave you the most satisfaction?",
        "Which parts do you feel are the most over-engineered?",
    ])
    mary = _mary(router)

    mary.process("We've spent all day building you.")
    result = mary.process("I think we might have overengineered some of this.")

    assert result.reflection.decision.value == "revise"
    assert "?" not in result.final_response
    assert "integration" in result.final_response.lower()


def test_repeated_opening_pattern_is_rewritten():
    router = SequenceRouter([
        "Sounds like a classic too-many-knobs scenario.",
        "Sounds like a classic feature-fatigue moment.",
    ])
    mary = _mary(router)

    mary.process("We may have overbuilt this.")
    result = mary.process("Some of it still feels too complicated.")

    assert result.reflection.decision.value == "revise"
    assert not result.final_response.lower().startswith("sounds like a classic")


def test_disagreement_prompt_selects_disagree_drive_without_forcing_question():
    mary = _mary(SequenceRouter(["I do disagree a little. I think the integration was the real problem."]))
    result = mary.process("You can disagree with me, you know.")

    continuity = result.context.mind_state["continuity"]
    assert continuity["drive"] == "disagree"
    assert "question" not in result.final_response.lower()


def test_curiosity_does_not_force_ask_drive():
    mary = _mary()
    mary.agency.curiosities.add_curiosity(
        "Learn more about Unbe",
        importance=1.0,
        source="test",
    )
    result = mary.process("I finally got everything working.")
    continuity = result.context.mind_state["continuity"]
    assert continuity["drive"] != "ask"
