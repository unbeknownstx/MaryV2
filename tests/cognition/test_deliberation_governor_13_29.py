from mary.cognition.deliberation import DeliberationGovernor


def test_deep_deliberation_branches_and_verifies_without_exposing_private_reasoning():
    plan = DeliberationGovernor().plan(
        {
            "cognitive_mode": "deliberate",
            "reasoning_depth": "deep",
            "latency_priority": "quality_first",
        },
        uncertainty=0.7,
        verifier_available=True,
    )
    assert plan.strategy == "branch_verify"
    assert plan.max_passes == 3
    assert plan.max_branches == 2
    assert plan.verifier_required is True
    assert plan.expose_private_reasoning is False
    assert plan.persistence == "ephemeral_structural_state_only"


def test_realtime_deliberation_compresses_branching():
    plan = DeliberationGovernor().plan(
        {
            "cognitive_mode": "deliberate",
            "reasoning_depth": "deep",
            "latency_priority": "quality_first",
        },
        uncertainty=0.8,
        verifier_available=True,
        realtime=True,
    )
    assert plan.strategy == "verify_once"
    assert plan.max_passes <= 2
    assert plan.max_branches == 1
    assert plan.latency_budget_ms <= 3200


def test_external_verifier_requires_explicit_authorization_signal():
    governor = DeliberationGovernor()
    denied = governor.plan({"cognitive_mode": "balanced"})
    allowed = governor.plan(
        {"cognitive_mode": "balanced"},
        external_verifier_authorized=True,
    )
    assert denied.external_verifier_allowed is False
    assert allowed.external_verifier_allowed is True
