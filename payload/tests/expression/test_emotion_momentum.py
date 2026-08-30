from mary.expression.emotion import Emotion, EmotionManager


def test_strong_emotion_keeps_short_lived_momentum_across_neutral_decay():
    manager = EmotionManager()
    manager.signal(Emotion.FRUSTRATION, 0.82, source="grounded_event")
    before = manager.snapshot()

    manager.decay(0.05)
    after = manager.snapshot()

    assert before["primary"] == "frustration"
    assert after["primary"] == "frustration"
    assert 0.0 < after["intensity"] < before["intensity"]
    assert 0.0 < after["momentum"] < before["momentum"]


def test_emotional_momentum_eventually_returns_to_resting_baseline():
    manager = EmotionManager()
    manager.signal(Emotion.ANGER, 0.7, source="grounded_event")

    for _ in range(80):
        manager.decay(0.05)

    state = manager.snapshot()
    assert state["primary"] == "neutral"
    assert state["intensity"] == 0.0
    assert state["momentum"] == 0.0


def test_repeated_same_emotion_strengthens_continuity_without_identity_mutation():
    manager = EmotionManager()
    manager.signal(Emotion.EXCITEMENT, 0.45, source="event_1")
    first = manager.snapshot()
    manager.signal(Emotion.EXCITEMENT, 0.65, source="event_2")
    second = manager.snapshot()

    assert second["primary"] == "excitement"
    assert second["momentum"] >= first["momentum"]
    assert "personality" not in second
    assert "developed_self" not in second
