from mary.perception.director import PerceptionDirector
from mary.perception.media_bridge import publish_media_context
from mary.perception.media_sessions import MediaSessionRegistry


def test_media_context_enters_existing_perception_boundary_only():
    sessions = MediaSessionRegistry()
    sessions.observe("asset-x", at_seconds=5, kind="vision", text="Mary waves", source="vlm", confidence=.9)
    sessions.observe("asset-x", at_seconds=6, kind="speech", text="hello", source="stt", confidence=.8)
    director = PerceptionDirector()
    published = publish_media_context(sessions, director, asset_id="asset-x", at_seconds=6)
    assert [x["description"] for x in published] == ["Mary waves", "hello"]
    assert all(x["durable"] is False for x in published)
    assert director.snapshot()["recent"][-1]["metadata"]["temporal_context"] is True
