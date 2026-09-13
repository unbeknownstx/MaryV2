from mary.core.mary import Mary
from mary.cognition.runtime_coordination import CharacterRuntimeCoordinator


def _plan(text: str):
    mary = Mary()
    intent = mary.cognition.detect_intent(text)
    state = mary.turn_mind.build(input_text=text, intent=intent, recent_conversation=[])
    return CharacterRuntimeCoordinator().plan_from_turn_state(state)


def test_real_turn_state_produces_cohesive_runtime_plan():
    plan = _plan("Mary, what do you think about what we were discussing yesterday?")
    payload = plan.to_dict()
    assert payload["authority"] == "coordination_projection_only"
    assert payload["cognition"]["cognitive_mode"] == "relational"
    assert payload["compute"]["realtime"] is True
    assert payload["compute"]["local_preferred"] is True
    assert payload["presentation"]["authority"] == "presentation_hint_only"


def test_research_turn_recommends_external_evidence_without_granting_it_authority():
    plan = _plan("Research and compare the latest academic papers about persistent agent memory.")
    assert plan.cognition["cognitive_mode"] == "deliberate"
    assert plan.knowledge["recommended"] is True
    assert "academic" in plan.knowledge["categories"]
    assert plan.knowledge["authority"] == "external_evidence_only"
    assert plan.compute["operation"] == "deep_reasoning"
