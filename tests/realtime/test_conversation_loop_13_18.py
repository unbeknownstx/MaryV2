from mary.realtime.conversation_loop import RealtimeConversationLoop
from mary.realtime.streaming import TurnCancellation
from mary.realtime.turn_end import TurnEndEvidence, TurnEndPolicy


def test_confirmed_creator_barge_in_cancels_current_turn():
    cancellation = TurnCancellation()
    loop = RealtimeConversationLoop(barge_in_ms=120)
    result = loop.observe(
        TurnEndEvidence(transcript="wait", speech_active=True),
        creator_speech_ms=180,
        mary_speaking=True,
        cancellation=cancellation,
    )
    assert result.action == "yield_floor"
    assert result.generation_cancelled is True
    assert cancellation.cancelled is True


def test_short_noise_does_not_cancel_mary():
    cancellation = TurnCancellation()
    loop = RealtimeConversationLoop(barge_in_ms=180)
    result = loop.observe(
        TurnEndEvidence(transcript="", speech_active=True),
        creator_speech_ms=70,
        mary_speaking=True,
        cancellation=cancellation,
    )
    assert result.action == "listen"
    assert cancellation.cancelled is False


def test_semantically_complete_turn_is_committed():
    loop = RealtimeConversationLoop(turn_end=TurnEndPolicy(settle_ms=300))
    result = loop.observe(TurnEndEvidence(
        transcript="Can you explain that?",
        speech_active=False,
        silence_ms=380,
        stt_final=True,
        semantic_end_probability=0.9,
    ))
    assert result.action == "commit_creator_turn"


def test_loop_is_transport_neutral_and_core_authoritative():
    status = RealtimeConversationLoop().status()
    assert status["transport"] == "provider_neutral"
    assert status["cognition_authority"] == "Mary Core"
