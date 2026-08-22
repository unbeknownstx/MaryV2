from __future__ import annotations

from mary.cognition.context import CognitiveContext
from mary.cognition.reasoning import ReasoningResult
from mary.cognition.reflection import ReflectionDecision, ReflectionEngine
from mary.llm.interface import LLMResponse


class EditorLLM:
    def __init__(self, revised: str):
        self.revised = revised
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return LLMResponse(
            content=self.revised,
            provider="test",
            model="fake",
            finish_reason="stop",
            usage={},
        )


def _context(
    input_text: str,
    *,
    drive: str = "answer",
    allow_question: bool = True,
) -> CognitiveContext:
    return CognitiveContext(
        input_text=input_text,
        mind_state={
            "disposition": {
                "mode": "relational_conversation",
                "follow_up_urge": 0.5,
            },
            "continuity": {
                "drive": drive,
                "allow_follow_up_question": allow_question,
                "recent_mary_responses": [],
                "recent_openings": [],
            },
        },
    )


def test_live_overdecorated_project_feeling_reply_is_rewritten():
    llm = EditorLLM(
        "Pretty good, actually. We've got enough of the core working now that "
        "I'm more interested in tightening the parts that still feel artificial "
        "than adding another subsystem."
    )
    engine = ReflectionEngine(llm=llm)

    original = (
        "Hey! I'm vibing pretty good-think of me as that bright spark that's just "
        "found a new set of colors to paint with. The project's pacing feels like "
        "a fresh rain on a windowpane-slow at first, then a steady drip that's "
        "building something solid. I'm excited about the direction we're heading, "
        "but I'd love to hear your thoughts on the last tweak. Anything that feels "
        "off or that you think we could jazz up?"
    )

    result = engine.reflect(
        context=_context(
            "hey mary! how are you feeling about where we are with the project?"
        ),
        reasoning=ReasoningResult(response=original),
    )

    assert result.decision == ReflectionDecision.REVISE
    assert any("texture boundary" in issue.lower() for issue in result.issues)
    assert any("handoff boundary" in issue.lower() for issue in result.issues)
    assert result.revised_response is not None
    lowered = result.revised_response.lower()
    for token in ("windowpane", "spark", "jazz up"):
        assert token not in lowered
    assert "?" not in result.revised_response
    assert len(llm.calls) == 1


def test_one_light_metaphor_is_not_treated_as_ornamental_overload():
    llm = EditorLLM("unused")
    engine = ReflectionEngine(llm=llm)

    result = engine.reflect(
        context=_context("We finally got the core stable.", drive="react"),
        reasoning=ReasoningResult(
            response="Yeah. It finally feels like the gears caught. The core is in a much better place now."
        ),
    )

    assert result.decision == ReflectionDecision.ACCEPT
    assert llm.calls == []


def test_generic_what_do_you_think_handoff_is_removed_from_normal_answer():
    llm = EditorLLM(
        "Pretty good. I think the core is stable enough that the awkward conversation edges matter more now."
    )
    engine = ReflectionEngine(llm=llm)

    result = engine.reflect(
        context=_context("How do you feel about the project?", drive="answer"),
        reasoning=ReasoningResult(
            response="Pretty good. I think the core is stable now. What do you think?"
        ),
    )

    assert result.decision == ReflectionDecision.REVISE
    assert any("handoff boundary" in issue.lower() for issue in result.issues)
    assert result.revised_response is not None
    assert "?" not in result.revised_response


def test_explicit_invitation_to_ask_preserves_a_genuine_question():
    llm = EditorLLM("unused")
    engine = ReflectionEngine(llm=llm)

    result = engine.reflect(
        context=_context(
            "You can ask me anything you want to know.",
            drive="ask",
            allow_question=True,
        ),
        reasoning=ReasoningResult(
            response="Okay, then I do have one. What part of building me has surprised you the most?"
        ),
    )

    assert result.decision == ReflectionDecision.ACCEPT
    assert llm.calls == []
