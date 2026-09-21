from mary.protocol.models import RuntimeActionRequest
from mary.runtime.system_fabric import build_improvement_proposal


def _agenda():
    return {
        "version": "13.83",
        "items": [
            {
                "kind": "capability",
                "subject": "knowledge.search",
                "state": "advertised_untested",
                "attention": "evidence",
                "evidence_needed": [
                    "a bounded typed task with a terminal outcome on a connected node"
                ],
                "automatic_action": False,
            },
            {
                "kind": "procedure_revision",
                "subject": "skill-revision-2",
                "state": "comparison_review_ready",
                "attention": "review",
                "evidence_needed": [],
                "automatic_action": False,
            },
            {
                "kind": "model_experiment",
                "subject": "exp-1",
                "state": "benchmarked",
                "attention": "trial",
                "evidence_needed": ["bounded explicit trial outcomes"],
                "automatic_action": False,
            },
        ],
    }


def test_runtime_protocol_accepts_proposal_only_improvement_action():
    parsed = RuntimeActionRequest.from_dict({
        "action": "continuity.improvement.propose",
        "args": {"kind": "capability", "subject": "knowledge.search"},
        "device_id": "iphone",
    })
    assert parsed.action == "continuity.improvement.propose"
    assert parsed.args["subject"] == "knowledge.search"


def test_capability_gap_becomes_typed_plan_draft_without_creating_or_executing():
    proposal = build_improvement_proposal(
        _agenda(),
        kind="capability",
        subject="knowledge.search",
    )

    assert proposal["proposal_type"] == "plan_draft"
    assert proposal["next_explicit_action"] == "continuity.plan.create"
    assert proposal["plan_draft"]["steps"] == []
    addition = proposal["plan_draft"]["step_additions"][0]
    assert addition["required_capabilities"] == ["knowledge.search"]
    assert addition["verification"]
    assert proposal["plan_created"] is False
    assert proposal["execution_performed"] is False
    assert proposal["permission_granted"] is False
    assert proposal["automatic_action"] is False


def test_review_ready_revision_routes_to_explicit_creator_review_not_execution():
    proposal = build_improvement_proposal(
        _agenda(),
        kind="procedure_revision",
        subject="skill-revision-2",
    )

    assert proposal["proposal_type"] == "creator_review"
    assert proposal["next_explicit_action"] == "continuity.skill.status"
    assert proposal["next_action_args"] == {"skill_id": "skill-revision-2"}
    assert proposal["execution_performed"] is False
    assert proposal["model_promoted"] is False


def test_trial_ready_model_routes_to_existing_explicit_trial_action():
    proposal = build_improvement_proposal(
        _agenda(),
        kind="model_experiment",
        subject="exp-1",
    )

    assert proposal["proposal_type"] == "model_trial"
    assert proposal["next_explicit_action"] == "model.experiment.dispatch"
    assert proposal["next_action_args"] == {"experiment_id": "exp-1"}
    assert proposal["model_promoted"] is False


def test_unknown_agenda_item_is_refused():
    try:
        build_improvement_proposal(
            _agenda(),
            kind="capability",
            subject="sensor.unknown",
        )
    except KeyError as exc:
        assert "improvement agenda item not found" in str(exc)
    else:
        raise AssertionError("unknown improvement agenda item was accepted")
