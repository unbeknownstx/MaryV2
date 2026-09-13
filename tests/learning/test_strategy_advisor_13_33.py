from mary.learning.strategy_advisor import StrategyAdvisor


def test_strategy_advisor_requires_enough_structural_evidence():
    proposal = StrategyAdvisor(min_samples=3).propose([], task_class="coding")
    assert proposal.strategy is None
    assert proposal.reason == "insufficient_structural_evidence"
    assert proposal.authority == "proposal_only_no_runtime_mutation"


def test_strategy_advisor_prefers_observed_success_without_mutating_policy():
    rows = []
    for _ in range(4):
        rows.append({
            "task_class": "coding",
            "strategy": "verify_once",
            "outcome": "success",
            "reward": 1.0,
            "verifier_score": 0.9,
        })
    for _ in range(4):
        rows.append({
            "task_class": "coding",
            "strategy": "single_pass",
            "outcome": "failed",
            "reward": -1.0,
            "verifier_score": None,
        })

    advisor = StrategyAdvisor(min_samples=3)
    proposal = advisor.propose(rows, task_class="coding")

    assert proposal.strategy == "verify_once"
    assert proposal.sample_count == 4
    assert proposal.confidence > 0.5
    status = advisor.status()
    assert status["automatic_training"] is False
    assert status["automatic_policy_mutation"] is False
    assert status["content_required"] is False
