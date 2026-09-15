from mary.core.mary import Mary
from mary.cognition.runtime_coordination import CharacterRuntimeCoordinator


def _plan(text: str):
    mary = Mary()
    intent = mary.cognition.detect_intent(text)
    state = mary.turn_mind.build(
        input_text=text,
        intent=intent,
        recent_conversation=[],
    )
    return CharacterRuntimeCoordinator().plan_from_turn_state(state)


def test_deliberate_runtime_plan_adds_bounded_deliberation_and_realtime_policy():
    plan = _plan(
        "Research and compare the latest academic papers about persistent agent memory."
    )
    payload = plan.to_dict()
    assert payload["cognition"]["cognitive_mode"] == "deliberate"
    assert payload["knowledge"]["recommended"] is True
    assert payload["deliberation"]["strategy"] in {"verify_once", "branch_verify"}
    assert payload["deliberation"]["expose_private_reasoning"] is False
    assert payload["realtime"]["partial_answer_allowed"] is False
    assert payload["authority"] == "coordination_projection_only"


def test_relational_runtime_keeps_deliberation_lightweight():
    plan = _plan("Mary, what do you think about what we were talking about yesterday?")
    assert plan.cognition["cognitive_mode"] == "relational"
    assert plan.deliberation["strategy"] == "single_pass"
    assert plan.realtime["allow_barge_in"] is True
