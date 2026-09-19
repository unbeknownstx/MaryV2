from mary.cognition.intent import IntentType
from mary.cognition.orchestrator import CognitiveOrchestrator


def _intent(text: str):
    return CognitiveOrchestrator(None, None).detect_intent(text)


def test_concrete_capability_questions_route_to_self_capability_evidence():
    for query in (
        "can you see my screen right now?",
        "can you look at an image?",
        "can you hear me through my microphone?",
        "can you browse the web?",
        "can you use local knowledge search?",
        "what can your nodes actually do?",
    ):
        intent = _intent(query)
        assert intent.intent_type == IntentType.SELF_QUERY
        assert intent.parameters["self_query_type"] == "capabilities"


def test_figurative_see_question_does_not_become_sensor_capability_query():
    intent = _intent("can you see why that idea bothers me?")
    assert not (
        intent.intent_type == IntentType.SELF_QUERY
        and intent.parameters.get("self_query_type") == "capabilities"
    )
