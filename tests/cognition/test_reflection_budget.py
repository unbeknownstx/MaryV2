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


def test_normal_reflection_uses_small_completion_budget():
    llm = CaptureLLM()
    engine = ReflectionEngine(llm=llm)

    result = engine.reflect(
        context=CognitiveContext(input_text="hello"),
        reasoning=ReasoningResult(response="Hi."),
    )

    assert result.decision == ReflectionDecision.ACCEPT
    assert llm.calls[0][1]["max_tokens"] == 512


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
