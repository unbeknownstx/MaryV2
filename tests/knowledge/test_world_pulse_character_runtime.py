from datetime import datetime, timezone

from mary.knowledge.world_pulse import WorldPulsePlanner


def test_world_pulse_is_planning_only_and_tracks_freshness():
    pulse = WorldPulsePlanner()
    due = pulse.due(limit=20)
    assert any(item["lane"] == "games" for item in due)
    assert all(item["authority"] == "research_plan_only" for item in due)
    pulse.mark_refreshed("games", when=datetime.now(timezone.utc))
    assert not any(item["lane"] == "games" for item in pulse.due(limit=20))
