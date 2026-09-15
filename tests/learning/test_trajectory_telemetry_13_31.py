from mary.learning.trajectory import TrajectoryRecorder


def test_trajectory_recorder_keeps_structural_evidence_only():
    recorder = TrajectoryRecorder(capacity=16)
    sample = recorder.record(
        task_class="architecture",
        strategy="branch_verify",
        passes=3,
        branches=2,
        verifier_score=0.92,
        outcome="success",
        reward=1.0,
        provider_attempts=2,
        tool_calls=1,
        latency_ms=1200,
        total_tokens=3400,
        tags=("deliberate", "verified"),
    )
    payload = sample.to_dict()
    assert "prompt" not in payload
    assert "response" not in payload
    assert payload["verifier_score"] == 0.92
    snapshot = recorder.snapshot()
    assert snapshot["content_retained"] is False
    assert snapshot["automatic_training"] is False


def test_trajectory_capacity_is_bounded():
    recorder = TrajectoryRecorder(capacity=16)
    for index in range(40):
        recorder.record(
            task_class="test",
            strategy="single_pass",
            outcome="success",
            tags=(str(index),),
        )
    assert len(recorder.samples()) == 16
