from mary.character import MaryEvalCase, MaryEvaluationSet


def test_character_eval_flags_generic_assistant_voice():
    case = MaryEvalCase(case_id="voice", prompt="hey mary")
    suite = MaryEvaluationSet([case])
    result = suite.evaluate(case, "How can I assist you today?")
    assert result.passed is False


def test_character_eval_supports_explicit_creator_constraints():
    case = MaryEvalCase(
        case_id="boundary",
        prompt="Who are you?",
        required_phrases=("Mary",),
        forbidden_phrases=("I am Unbe",),
    )
    suite = MaryEvaluationSet([case])
    assert suite.evaluate(case, "I'm Mary.").passed is True
