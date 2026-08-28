from mary.cognition.context import CognitiveContext
from mary.cognition.reasoning import ReasoningResult
from mary.cognition.reflection import ReflectionDecision, ReflectionEngine
from mary.llm.interface import LLMResponse


class CaptureLLM:
    def __init__(self):
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return LLMResponse(
            content=(
                "DECISION: ACCEPT\n"
                "CONFIDENCE: 0.9\n"
                "ASSESSMENT: Fine.\n"
                "ISSUES: NONE\n"
                "SUGGESTIONS: NONE"
            ),
            provider="test",
            model="fake",
        )


def test_normal_reflection_is_local_when_character_audit_passes():
    llm = CaptureLLM()
    engine = ReflectionEngine(llm=llm)

    result = engine.reflect(
        context=CognitiveContext(
            input_text="hello",
            mind_state={
                "disposition": {"mode": "relational_conversation"},
            },
        ),
        reasoning=ReasoningResult(response="Hey. Good to see you."),
    )

    assert result.decision == ReflectionDecision.ACCEPT
    assert result.metadata["mode"] == "local_character_audit"
    assert llm.calls == []


def test_generic_assistant_reflection_uses_targeted_revision_budget():
    llm = CaptureLLM()
    engine = ReflectionEngine(llm=llm)

    result = engine.reflect(
        context=CognitiveContext(
            input_text="I finally fixed it",
            mind_state={
                "disposition": {"mode": "relational_conversation"},
            },
        ),
        reasoning=ReasoningResult(
            response="Great to hear that! Anything else you'd like to tackle next?"
        ),
    )

    assert result.decision == ReflectionDecision.REVISE
    assert llm.calls[0][1]["max_tokens"] == 700


def test_research_reflection_reuses_evidence_result_without_llm_call():
    llm = CaptureLLM()
    engine = ReflectionEngine(llm=llm)

    result = engine.reflect(
        context=CognitiveContext(input_text="latest Python news"),
        reasoning=ReasoningResult(
            response="Grounded answer",
            metadata={
                "evidence_validation": {
                    "validated": True,
                    "failure": None,
                }
            },
        ),
    )

    assert result.decision == ReflectionDecision.ACCEPT
    assert result.metadata["mode"] == "evidence_validation_reuse"
    assert llm.calls == []


def test_generic_milestone_interview_is_rejected_as_provider_style_leakage():
    llm = CaptureLLM()
    engine = ReflectionEngine(llm=llm)

    result = engine.reflect(
        context=CognitiveContext(
            input_text="I finally solved that bug.",
            mind_state={
                "disposition": {"mode": "relational_conversation"},
                "dialogue_plan": {
                    "drive": "acknowledge",
                    "ending_style": "clean_statement",
                    "allow_question": False,
                    "question_budget": 0,
                },
            },
        ),
        reasoning=ReasoningResult(
            response="Great to hear you finally cracked it! What was the key insight that led to the fix?",
            metadata={"conversation_lane": {"lane": "conversation"}},
        ),
    )

    assert result.decision == ReflectionDecision.REVISE
    assert any("generic validation/interview formula" in issue.lower() for issue in result.issues)
