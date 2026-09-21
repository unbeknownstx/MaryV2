from mary.perception.media_sessions import MediaSessionRegistry


def test_media_session_registry_builds_bounded_multimodal_context():
    registry = MediaSessionRegistry(capacity=4, observations_per_asset=16)
    registry.observe("asset-1", at_seconds=1, kind="speech", text="hello", source="stt")
    registry.observe("asset-1", at_seconds=3, kind="vision", text="waves", source="vision")
    assert [x["text"] for x in registry.context("asset-1", at_seconds=3)] == ["hello", "waves"]
    status = registry.status()
    assert status["raw_media_stored"] is False
    assert status["authority"] == "derived_perception_evidence"
