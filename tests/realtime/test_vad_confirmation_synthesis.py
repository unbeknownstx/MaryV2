from mary.realtime import RealtimeInteractionCoordinator


def test_unconfirmed_vad_does_not_interrupt_active_mary_speech():
    realtime = RealtimeInteractionCoordinator()
    realtime.speech_started(source="test")
    generation = realtime.interrupt_generation

    realtime.report_voice_activity(True, confirmed=False, source="vad", confidence=.7)

    status = realtime.status()
    assert status["phase"] == "speaking"
    assert status["speaker_scheduler"]["floor_owner"] == "mary"
    assert status["interrupt_generation"] == generation
    assert status["voice_activity"]["confirmed"] is False


def test_confirmed_vad_can_barge_in_and_claim_creator_floor():
    realtime = RealtimeInteractionCoordinator()
    realtime.speech_started(source="test")

    realtime.report_voice_activity(True, confirmed=True, source="vad", confidence=.9)

    status = realtime.status()
    assert status["phase"] == "listening"
    assert status["speaker_scheduler"]["floor_owner"] == "creator"
    assert status["interrupt_generation"] == 1
    assert status["voice_activity"]["confirmed"] is True


def test_false_vad_candidate_is_counted_without_becoming_attention_truth():
    realtime = RealtimeInteractionCoordinator()
    realtime.report_voice_activity(True, confirmed=False, source="vad")
    realtime.report_voice_activity(False, confirmed=False, source="vad")
    status = realtime.status()
    assert status["stats"]["vad_candidates"] == 1
    assert status["stats"]["vad_false_starts"] == 1
    assert status["attention"]["pending"] == 0
