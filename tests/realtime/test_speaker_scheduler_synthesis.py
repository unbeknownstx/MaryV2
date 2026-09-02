from mary.realtime import (
    AttentionBus,
    AttentionSource,
    FloorDisposition,
    RealtimeInteractionCoordinator,
    SpeakerOpportunity,
    SpeakerScheduler,
)


def test_creator_floor_forces_mary_to_wait_even_for_relevant_viewer():
    scheduler = SpeakerScheduler()
    opportunity = SpeakerOpportunity(
        speaker_id="mary",
        source_kind="viewer",
        source_id="twitch:viewer",
        target="twitch:viewer",
        relevance=.9,
        direct=True,
    )
    decision = scheduler.consider(opportunity, floor_owner="creator")
    assert decision.disposition == FloorDisposition.WAIT
    assert scheduler.status()["pending_count"] == 1


def test_free_floor_allows_direct_mary_response_and_trace_is_content_free():
    realtime = RealtimeInteractionCoordinator()
    decision = realtime.speaker_scheduler.consider(
        SpeakerOpportunity(source_kind="viewer", source_id="viewer-1", direct=True, relevance=.8),
        floor_owner="none",
    )
    assert decision.disposition == FloorDisposition.SPEAK
    trace = realtime.decision_trace.snapshot()
    assert trace["count"] >= 1
    assert trace["recent"][-1]["kind"] == "speaker_floor"
    assert "dialogue" not in trace["policy"].casefold() or "no raw dialogue" in trace["policy"].casefold()


def test_attention_judgment_enters_same_realtime_decision_trace():
    realtime = RealtimeInteractionCoordinator()
    realtime.attention.judge(AttentionSource.BACKGROUND, importance=.7, novelty=.8)
    assert any(item["kind"] == "attention" for item in realtime.decision_trace.snapshot()["recent"])


def test_realtime_lifecycle_updates_social_floor():
    realtime = RealtimeInteractionCoordinator()
    realtime.mark_listening(True)
    assert realtime.speaker_scheduler.status()["floor_owner"] == "creator"
    realtime.mark_listening(False)
    assert realtime.speaker_scheduler.status()["floor_owner"] == "none"
    realtime.speech_started(source="test")
    assert realtime.speaker_scheduler.status()["floor_owner"] == "mary"
    realtime.speech_ended()
    assert realtime.speaker_scheduler.status()["floor_owner"] == "none"
