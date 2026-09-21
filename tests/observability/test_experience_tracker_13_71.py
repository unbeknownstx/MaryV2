from mary.observability.experience_tracker import ExperienceLatencyTracker


def test_tracker_keeps_first_milestone_and_reports_deltas():
    tracker = ExperienceLatencyTracker()
    tracker.start("t", at_ms=100)
    tracker.mark("t", "first_visible_reaction", at_ms=140)
    tracker.mark("t", "first_visible_reaction", at_ms=180)
    tracker.mark("t", "first_audio", at_ms=350)
    tracker.mark("t", "completed", at_ms=700)
    item = tracker.get("t")
    assert item["time_to_first_visible_reaction_ms"] == 40.0
    assert item["time_to_first_audio_ms"] == 250.0
    assert item["turn_total_ms"] == 600.0
