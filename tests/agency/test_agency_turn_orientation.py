from __future__ import annotations

from mary.agency.agency import Agency
from mary.agency.decisions import DecisionSystem
from mary.agency.priorities import PrioritySystem
from mary.core.mary import Mary
from mary.llm.interface import LLMResponse


class AgencyAwareFakeRouter:
    def __init__(self) -> None:
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return LLMResponse(
            content="We should keep the MaryV2 integration coherent and finish the current connection first.",
            provider="test",
            model="agency-test",
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "agency-test"

    def is_available(self, provider=None):
        return True


def test_decision_preview_is_ephemeral_and_evaluate_still_records():
    priorities = PrioritySystem()
    item = priorities.add(
        item_id="goal_1",
        item_type="goal",
        description="Finish MaryV2 integration",
        importance=0.95,
        urgency=0.7,
        relevance=0.9,
    )

    decisions = DecisionSystem(
        priority_system=priorities,
    )

    preview = decisions.preview(
        priorities=[item],
        context={"intent": "question"},
    )

    assert preview is not None
    assert preview.id == "preview"
    assert preview.status == "proposed"
    assert preview.action == "pursue_goal"
    assert decisions.get_all() == []

    stored = decisions.evaluate(
        priorities=[item],
        context={"intent": "question"},
    )

    assert stored is not None
    assert stored.id != "preview"
    assert len(decisions.get_all()) == 1


def test_agency_turn_orientation_only_activates_for_relevant_or_explicit_turns(
    tmp_path,
):
    agency = Agency(
        storage_root=tmp_path / "agency",
    )

    agency.goals.add_goal(
        "Finish MaryV2 cloud integration",
        importance=0.95,
    )
    agency.intentions.add_intention(
        "Verify the desktop uses the canonical Mary Core",
        priority=0.8,
    )

    before = len(
        agency.decisions.get_all()
    )

    unrelated = agency.turn_orientation(
        input_text="What's your favorite color?",
        intent_name="question",
    )

    assert unrelated["active"] is False
    assert unrelated["decision"] is None

    relevant = agency.turn_orientation(
        input_text="Let's continue the MaryV2 cloud integration.",
        intent_name="request",
    )

    assert relevant["active"] is True
    assert relevant["priority"]["type"] == "goal"
    assert "MaryV2" in relevant["priority"]["description"]
    assert relevant["decision"]["suggested_action"] == "pursue_goal"
    assert relevant["execution"] == "not_authorized"

    explicit = agency.turn_orientation(
        input_text="What should we work on next?",
        intent_name="question",
    )

    assert explicit["active"] is True
    assert explicit["explicit_request"] is True
    assert explicit["decision"] is not None

    assert len(
        agency.decisions.get_all()
    ) == before


def test_turn_mind_exposes_active_agency_orientation_without_execution(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(
        tmp_path
    )

    mary = Mary()

    mary.agency.goals.add_goal(
        "Finish MaryV2 integration",
        importance=0.95,
    )

    intent = mary._detect_intent(
        "What should we work on next?"
    )

    mind = mary.turn_mind.build(
        input_text="What should we work on next?",
        intent=intent,
    ).to_dict()

    orientation = mind[
        "agency"
    ][
        "orientation"
    ]

    assert orientation["active"] is True
    assert orientation["decision"] is not None
    assert orientation["execution"] == "not_authorized"
    assert mary.agency.decisions.get_all() == []


def test_agency_orientation_reaches_cognition_and_engaged_initiative(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(
        tmp_path
    )

    mary = Mary()
    router = AgencyAwareFakeRouter()

    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router

    mary.agency.goals.add_goal(
        "Finish MaryV2 integration",
        importance=0.95,
    )

    mary.relationship_curiosity.unresolved_gaps = lambda: []
    mary.engagement.begin_session(
        "engaged",
        turns=4,
        reason="agency-integration-test",
    )

    result = mary.process(
        "What should we work on next?"
    )

    mind = result.context.mind_state

    assert mind["agency"]["orientation"]["active"] is True
    assert (
        mind["conversation_initiative"]["permission"]
        == "agency_relevant_thought_within_current_thread"
    )

    # The LLM-facing prompt receives the agency orientation, but it remains
    # clearly non-executing internal context.
    assert router.calls
    user_prompt = str(
        router.calls[0][0][1].content
    )
    system_prompt = str(
        router.calls[0][0][0].content
    )

    assert "orientation" in user_prompt
    assert "not an execution authorization" in system_prompt
    assert mary.autonomy.stopped is True
