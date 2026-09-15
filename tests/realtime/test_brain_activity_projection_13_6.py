from mary.realtime import RealtimeInteractionCoordinator


def test_brain_activity_is_read_only_projection_without_private_reasoning():
    realtime = RealtimeInteractionCoordinator()
    realtime.attention.judge("background", importance=.2, novelty=.1)
    view = realtime.brain_activity.snapshot()
    assert view["policy"].startswith("read-only")
    assert "recent_decisions" in view
    assert "chain_of_thought" not in str(view).lower()
    assert realtime.status()["brain_activity"]["version"] == "13.6"
