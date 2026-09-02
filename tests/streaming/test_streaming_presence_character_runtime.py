from mary.presence import PresenceManager
from mary.streaming import ChatMessage, StreamingPresenceCoordinator


def test_stream_chat_enters_presence_as_environment_context(tmp_path):
    presence = PresenceManager(tmp_path)
    stream = StreamingPresenceCoordinator(presence)
    result = stream.ingest_chat(
        ChatMessage(
            message_id="1",
            author_id="u1",
            display_name="Ray",
            text="Mary what are you drawing?",
            platform="twitch",
            direct_to_mary=True,
        ),
        creator_speaking=False,
    )
    assert result["accepted"] is True
    assert result["published"] is True
    assert result["presence"]["event"]["event_type"] == "twitch_mention"
    assert result["presence"]["event"]["metadata"]["display_name"] == "Ray"


def test_stream_chat_defers_when_creator_has_floor(tmp_path):
    presence = PresenceManager(tmp_path)
    stream = StreamingPresenceCoordinator(presence)
    result = stream.ingest_chat(
        ChatMessage(
            message_id="2",
            author_id="u2",
            display_name="Viewer",
            text="random comment",
            platform="twitch",
        ),
        creator_speaking=True,
    )
    assert result["accepted"] is True
    assert result["selection"]["action"] == "ignore"


def test_fast_brain_reranks_without_bypassing_creator_floor(tmp_path):
    from mary.mind.fast_brain import CallableFastBrain, FastBrainResult

    presence = PresenceManager(tmp_path)
    brain = CallableFastBrain(
        lambda request: FastBrainResult(
            "respond", .99, {"respond": .99}, provider="test", model="tiny-ranker"
        )
    )
    stream = StreamingPresenceCoordinator(presence, fast_brain=brain)
    result = stream.ingest_chat(
        ChatMessage(
            message_id="fb1",
            author_id="u3",
            display_name="Viewer",
            text="please react to this",
            platform="twitch",
        ),
        creator_speaking=True,
    )
    assert result["selection"]["action"] == "ignore"
    assert result["published"] is False
    assert stream.snapshot()["fast_brain"]["last"]["reason"] == "creator_has_floor"


def test_fast_brain_can_raise_interesting_chat_when_floor_open(tmp_path):
    from mary.mind.fast_brain import CallableFastBrain, FastBrainResult

    presence = PresenceManager(tmp_path)
    brain = CallableFastBrain(
        lambda request: FastBrainResult(
            "respond", 1.0, {"respond": 1.0}, provider="test", model="tiny-ranker"
        )
    )
    stream = StreamingPresenceCoordinator(presence, fast_brain=brain)
    result = stream.ingest_chat(
        ChatMessage(
            message_id="fb2",
            author_id="u4",
            display_name="Viewer",
            text="this is a thoughtful comment about the scene",
            platform="twitch",
        ),
        creator_speaking=False,
    )
    assert result["accepted"] is True
    assert result["selection"]["action"] in {"notice", "respond"}
    assert "fast_brain:respond" in result["selection"]["reasons"]
    assert result["fast_brain"]["model"] == "tiny-ranker"
