from mary.presence.live_scene import LiveScene, SceneParticipant


def test_live_scene_tracks_current_context_without_persistence():
    scene = LiveScene(event_capacity=8)
    scene.set_mode("stream")
    scene.set_context(project="Unbeknownst", activity="drawing")
    scene.upsert_participant(SceneParticipant("creator", "creator", speaking=True, attention=1.0))
    scene.set_floor("creator", realtime_phase="listening")
    scene.observe(
        event_id="e1",
        kind="twitch_mention",
        source="twitch:chat",
        summary="viewer: Mary what do you think?",
        importance=.9,
        metadata={"display_name": "viewer"},
    )
    status = scene.snapshot()
    assert status["project"] == "Unbeknownst"
    assert status["floor_owner"] == "creator"
    assert status["mary_target"] == "viewer"
    assert status["persistence"] == "none"
