import pytest

from mary.autonomy import (
    ActionPriority,
    ActionTrigger,
    AutonomyRuntime,
    AutonomyRuntimeStateError,
    TriggerContext,
)
from mary.realtime import AttentionBus, AttentionSource


def test_attention_is_opaque_deduplicated_prioritized_and_paused_without_loss():
    bus = AttentionBus(max_pending=16)
    low = bus.publish(
        AttentionSource.BACKGROUND,
        "background consideration",
        dedupe_key="same-background-event",
    )
    duplicate = bus.publish(
        AttentionSource.BACKGROUND,
        "duplicate wording is not authoritative",
        dedupe_key="same-background-event",
    )
    urgent = bus.publish(AttentionSource.CREATOR_SPEECH, "creator input")

    assert duplicate is low
    assert urgent.attention_id.startswith("attention_")
    assert urgent.to_dict()["execution_status"] == "not_executed"
    assert bus.snapshot()["deduplicated"] == 1

    bus.pause("creator_surface_sleeping")
    assert bus.next() is None
    assert bus.snapshot()["pending"] == 2
    bus.wake()
    assert bus.next() is urgent


def test_attention_evaluation_proposal_linkage_is_bounded_and_non_executing():
    bus = AttentionBus()
    attention = bus.publish(
        AttentionSource.CURIOSITY,
        "consider the next safe step",
        dedupe_key="curiosity:next-step",
    )
    runtime = AutonomyRuntime()
    runtime.triggers.register(
        ActionTrigger(
            "consider next step",
            "consider_next_step",
            priority=ActionPriority.HIGH,
        )
    )
    runtime.start()

    first = runtime.cycle(
        TriggerContext(metadata={"attention_id": attention.attention_id}),
        now=10.0,
    )
    proposal = first.actions_created[0]
    metadata = proposal.metadata

    assert first.evaluation_id.startswith("evaluation_")
    assert metadata["attention_id"] == attention.attention_id
    assert metadata["evaluation_id"] == first.evaluation_id
    assert metadata["proposal_id"].startswith("proposal_")
    assert metadata["dedupe_key"] == "trigger:consider_next_step"
    assert metadata["priority"] == "high"
    assert metadata["confirmation_required"] is True
    assert metadata["execution_status"] == "not_executed"
    assert metadata["proposal_only"] is True
    assert proposal.attempts == 0
    assert first.actions_ready == ()

    second = runtime.cycle(
        TriggerContext(metadata={"attention_id": attention.attention_id}),
        now=11.0,
    )
    assert second.actions_created == ()
    assert len(runtime.actions.all()) == 1


def test_runtime_sleep_pause_blocks_evaluation_until_explicit_wake():
    runtime = AutonomyRuntime()
    runtime.start()
    runtime.pause()

    with pytest.raises(AutonomyRuntimeStateError, match="must be running"):
        runtime.cycle(now=1.0)
    assert runtime.cycle_count == 0

    runtime.resume()
    result = runtime.cycle(now=2.0)
    assert result.cycle_id == 1
    assert result.actions_created == ()