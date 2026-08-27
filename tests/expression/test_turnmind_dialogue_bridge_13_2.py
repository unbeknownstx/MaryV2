from __future__ import annotations

import pytest

from mary.core.mary import Mary
from mary.expression.dialogue_plan import DialoguePlanner
from mary.expression.director import ExpressionDirector
from mary.expression.emotion import Emotion, EmotionalState
from mary.expression.response import ResponseType
from mary.llm.interface import LLMResponse


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


class DialogueBridgeRouter:
    def __init__(self):
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        system = str(messages[0].content) if messages else ""
        if "Mary's response editor" in system:
            content = "Yeah, I think this is the right direction. It feels more like one mind instead of a pile of systems taking turns."
        else:
            content = "Yeah, I think this is the right direction. It feels more like one mind instead of a pile of systems taking turns."
        return LLMResponse(content=content, provider="test", model="fake")

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "fake"

    def is_available(self, provider=None):
        return True


def _mary() -> tuple[Mary, DialogueBridgeRouter]:
    mary = Mary()
    router = DialogueBridgeRouter()
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    return mary, router


def test_dialogue_planner_projects_turnmind_without_owning_state():
    planner = DialoguePlanner()
    plan = planner.plan({
        "disposition": {
            "mode": "relational_conversation",
            "warmth": 0.85,
            "playfulness": 0.72,
            "directness": 0.88,
            "independence": 0.76,
            "expressiveness": 0.82,
            "familiarity": "familiar",
            "preferred_length": "brief",
            "allow_opinion": True,
            "allow_teasing": True,
        },
        "performance": {
            "energy": 0.61,
            "spontaneity": 0.70,
            "theatricality": 0.40,
            "intimacy": 0.78,
            "pacing": "natural_conversational",
            "opening_style": "thought_then_position",
            "ending_style": "clean_statement",
            "allow_fragments": True,
            "allow_interjections": True,
            "allow_thinking_aloud": True,
        },
        "continuity": {
            "drive": "opine",
            "allow_follow_up_question": False,
        },
        "emotion": {"turn_primary": "warmth", "turn_intensity": 0.5},
        "relationship": {"familiarity": "familiar"},
        "conversation": {},
    })

    data = plan.to_dict()
    assert data["drive"] == "opine"
    assert data["stance"] == "clear_personal_view"
    assert data["relationship_mode"] == "established_familiarity"
    assert data["allow_question"] is False
    assert data["question_budget"] == 0
    assert data["authority"] == "derived_from_turn_mind"
    assert data["persistence"] == "dialogue_context_only"


def test_turnmind_dialogue_plan_reaches_generation_expression_and_dialogue():
    mary, router = _mary()

    result = mary.process("Tell me what you think about making all of these systems feel like one Mary.")

    mind = result.context.mind_state
    assert "dialogue_plan" in mind
    assert mind["dialogue_plan"]["authority"] == "derived_from_turn_mind"

    combined = "\n".join(str(message.content) for message in router.calls[0][0])
    assert "dialogue_plan" in combined
    assert "TurnMind-to-dialogue contract" in str(router.calls[0][0][0].content)

    assert result.metadata["dialogue_plan"]["drive"] == mind["dialogue_plan"]["drive"]
    assert result.metadata["delivery_plan"]["metadata"]["turn_mind_dialogue_plan"] is True

    trace = mary.dialogue.last_mary_expression()
    assert trace["authority"] == "session_expression_trace"
    assert trace["drive"] == mind["dialogue_plan"]["drive"]
    assert trace["delivery_profile"] == result.metadata["delivery_plan"]["profile"]


def test_previous_dialogue_expression_flows_back_into_next_turnmind():
    mary, _router = _mary()

    first = mary.process("Tell me what you think about this architecture.")
    first_trace = mary.dialogue.last_mary_expression()
    assert first_trace

    second = mary.process("Yeah, that's what I mean.")
    conversation = second.context.mind_state["conversation"]

    assert conversation["last_mary_expression"] == first_trace
    assert second.context.mind_state["dialogue_plan"]["previous_expression"]


def test_expression_director_consumes_turnmind_dialogue_plan():
    director = ExpressionDirector()
    plan = director.plan(
        input_text="I finally got it working",
        response_text="Okay, yeah—that's actually a big one.",
        emotional_state=EmotionalState(primary=Emotion.PRIDE, intensity=0.45),
        conversation_lane="conversation",
        mind_state={
            "dialogue_plan": {
                "drive": "react",
                "stance": "responsive",
                "tone": "bright_alive",
                "energy": 0.80,
                "warmth": 0.78,
                "spontaneity": 0.76,
                "intimacy": 0.72,
                "theatricality": 0.32,
                "expressiveness": 0.84,
                "pacing": "lively",
                "previous_expression": {},
            }
        },
    )

    assert plan.metadata["turn_mind_dialogue_plan"] is True
    assert plan.metadata["dialogue_stance"] == "responsive"
    assert plan.metadata["dialogue_drive"] == "react"
    assert plan.profile in {"bright", "conversational"}
    assert plan.energy > 0.40
    assert plan.warmth > 0.50


def test_dialogue_plan_classifies_structured_response_type():
    planner = DialoguePlanner()

    assert planner.response_type("What part should we tackle first?", {"drive": "ask"}) == ResponseType.QUESTION
    assert planner.response_type("I keep coming back to the same thing.", {"drive": "reflect"}) == ResponseType.REFLECTION
    assert planner.response_type("Yeah. That's the part.", {"drive": "react"}) == ResponseType.STATEMENT
