from mary.cognition.deliberation import (
    DeliberationCandidate,
    DeliberationExecutor,
    DeliberationPlan,
    VerificationResult,
)
from mary.learning.trajectory import TrajectoryRecorder


def test_branch_verify_selects_best_candidate_and_records_only_structure():
    recorder = TrajectoryRecorder()
    executor = DeliberationExecutor(recorder=recorder)
    plan = DeliberationPlan(
        strategy="branch_verify",
        max_passes=3,
        max_branches=2,
        verifier_required=True,
        confidence_floor=0.8,
        latency_budget_ms=10_000,
        external_verifier_allowed=False,
    )

    def generate(pass_index, branch_index, previous, verification):
        return DeliberationCandidate(
            content=("candidate-a" if branch_index == 0 else "candidate-b"),
            confidence=0.5,
            structural_metrics={"provider_attempts": 1, "total_tokens": 10},
        )

    def verify(candidate, branch_index):
        return VerificationResult(score=(0.3 if branch_index == 0 else 0.9))

    outcome = executor.execute(
        plan,
        generate=generate,
        verify=verify,
        task_class="coding",
    )

    assert outcome.content == "candidate-b"
    assert outcome.passes == 2
    assert outcome.branches == 2
    assert outcome.verifier_calls == 2
    assert outcome.private_reasoning_retained is False

    rows = recorder.samples()
    assert len(rows) == 1
    assert rows[0]["task_class"] == "coding"
    assert rows[0]["strategy"] == "branch_verify"
    assert rows[0]["total_tokens"] == 20
    assert "candidate-a" not in str(rows[0])
    assert "candidate-b" not in str(rows[0])


def test_verify_once_revises_when_below_confidence_floor():
    executor = DeliberationExecutor()
    plan = DeliberationPlan(
        strategy="verify_once",
        max_passes=2,
        max_branches=1,
        verifier_required=True,
        confidence_floor=0.8,
        latency_budget_ms=10_000,
        external_verifier_allowed=False,
    )

    def generate(pass_index, branch_index, previous, verification):
        return DeliberationCandidate(
            content=("first" if pass_index == 0 else "revised"),
            confidence=(0.4 if pass_index == 0 else 0.9),
        )

    def verify(candidate, branch_index):
        return VerificationResult(score=(0.4 if candidate.content == "first" else 0.9))

    outcome = executor.execute(plan, generate=generate, verify=verify)
    assert outcome.content == "revised"
    assert outcome.passes == 2
    assert outcome.verifier_score == 0.9


def test_required_verifier_degrades_without_exposing_or_persisting_scratch_work():
    recorder = TrajectoryRecorder()
    executor = DeliberationExecutor(recorder=recorder)
    plan = DeliberationPlan(
        strategy="branch_verify",
        max_passes=3,
        max_branches=2,
        verifier_required=True,
        confidence_floor=0.8,
        latency_budget_ms=10_000,
        external_verifier_allowed=False,
    )

    outcome = executor.execute(
        plan,
        generate=lambda *_: DeliberationCandidate("safe-final", confidence=0.6),
        verify=None,
        task_class="general",
    )

    assert outcome.content == "safe-final"
    assert outcome.degraded is True
    assert outcome.failure_kind == "verifier_unavailable"
    assert recorder.samples()[0]["failure_kind"] == "verifier_unavailable"
