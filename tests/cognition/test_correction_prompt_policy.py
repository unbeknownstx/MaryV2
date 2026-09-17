from mary.cognition.context import CognitiveContext
from mary.cognition.reasoning import ReasoningEngine


def test_system_prompt_handles_evidence_backed_creator_corrections_plainly():
    engine = ReasoningEngine(llm=object())
    context = CognitiveContext(input_text="No, the evidence we already have shows that was wrong.")

    prompt = engine._system_prompt(context)

    assert "earlier claim was wrong" in prompt
    assert "give the correction" in prompt
    assert "Don't hedge a settled claim for balance" in prompt
    assert "genuinely mixed" in prompt
