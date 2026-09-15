from mary.realtime.turn_end import TurnEndEvidence, TurnEndPolicy


def test_active_speech_never_commits():
    policy = TurnEndPolicy()
    decision = policy.decide(TurnEndEvidence(transcript="I was thinking", speech_active=True))
    assert decision.complete is False


def test_semantic_end_can_commit_after_short_natural_pause():
    policy = TurnEndPolicy(settle_ms=300)
    decision = policy.decide(TurnEndEvidence(
        transcript="What do you think?",
        speech_active=False,
        silence_ms=380,
        stt_final=True,
        semantic_end_probability=0.92,
    ))
    assert decision.complete is True
    assert decision.wait_ms == 0


def test_short_pause_without_end_evidence_waits():
    policy = TurnEndPolicy(settle_ms=360)
    decision = policy.decide(TurnEndEvidence(
        transcript="because I was",
        speech_active=False,
        silence_ms=180,
        stt_final=False,
        semantic_end_probability=0.15,
    ))
    assert decision.complete is False
    assert decision.wait_ms > 0


def test_final_stt_hard_timeout_commits_without_semantic_model():
    policy = TurnEndPolicy(hard_ms=900)
    decision = policy.decide(TurnEndEvidence(
        transcript="tell me about that",
        speech_active=False,
        silence_ms=950,
        stt_final=True,
    ))
    assert decision.complete is True


def test_status_makes_optional_semantic_dependency_explicit():
    status = TurnEndPolicy().status()
    assert status["semantic_signal"] == "optional"
    assert status["audio_capture"] == "external"
