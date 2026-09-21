from mary.observability.experience_latency import ExperienceLatency


def test_experience_latency_reports_character_facing_milestones():
    sample = ExperienceLatency(
        turn_id="turn-1",
        started_ms=1000,
        first_visible_reaction_ms=1060,
        first_token_ms=1120,
        first_audio_ms=1450,
        completed_ms=2200,
    ).to_dict()
    assert sample["time_to_first_visible_reaction_ms"] == 60.0
    assert sample["ttft_ms"] == 120.0
    assert sample["time_to_first_audio_ms"] == 450.0
    assert sample["turn_total_ms"] == 1200.0
    assert sample["authority"] == "derived_observability"
