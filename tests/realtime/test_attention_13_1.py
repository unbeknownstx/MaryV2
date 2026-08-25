from mary.realtime import AttentionBus, AttentionSource, RealtimeInteractionCoordinator


def test_attention_priority_and_sensitive_metadata_boundary():
    bus = AttentionBus(max_pending=16)
    bus.publish(AttentionSource.BACKGROUND, "low", metadata={"api_key": "never", "safe": "ok"})
    speech = bus.publish(AttentionSource.CREATOR_SPEECH, "hello", metadata={"raw_audio": b"x", "device": "mic"})
    assert bus.next().id == speech.id
    recent = bus.snapshot()["recent"]
    assert all("api_key" not in item["metadata"] for item in recent)
    assert all("raw_audio" not in item["metadata"] for item in recent)


def test_claim_context_is_bounded_and_context_only():
    bus = AttentionBus()
    low = bus.publish(AttentionSource.BACKGROUND, "noise", importance=0.1)
    important = bus.publish(AttentionSource.VISUAL, "A document appeared on screen", importance=0.9)
    claimed = bus.claim_context(limit=2, minimum_importance=0.6)
    assert [item.id for item in claimed] == [important.id]
    assert [item.id for item in bus.pending()] == [low.id]


def test_realtime_barge_in_and_anti_echo():
    rt = RealtimeInteractionCoordinator()
    rt.speech_started(source="test")
    assert rt.should_accept_audio_input() is False
    assert rt.status()["stats"]["suppressed_echo_inputs"] == 1
    rt.begin_turn("wait", voice=True)
    state = rt.status()
    assert state["phase"] == "thinking"
    assert state["stats"]["interruptions"] == 1
    assert state["attention"]["pending"] == 0
