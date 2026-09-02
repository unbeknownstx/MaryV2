from mary.streaming.chat import ChatMessage, ChatSelection
from mary.streaming.social import AudienceRoster


def _message(message_id: str, direct: bool = False):
    return ChatMessage(platform="twitch", channel="test", message_id=message_id, author_id="viewer-1", display_name="Viewer", text="hi mary", direct_to_mary=direct)


def test_audience_roster_builds_bounded_session_familiarity_not_relationship():
    roster = AudienceRoster(capacity=4)
    for index in range(3):
        msg = _message(str(index), direct=index == 2)
        roster.observe(msg, ChatSelection(msg, .8, "respond", ("direct",)))
    member = roster.get("twitch:viewer-1")
    assert member is not None
    assert member.messages_seen == 3
    assert member.direct_mentions == 1
    snapshot = roster.snapshot()
    assert snapshot["top"][0]["familiarity"] > 0
    assert "relationship" in snapshot["policy"].lower()


def test_stream_response_candidate_respects_shared_creator_floor(tmp_path):
    from mary.presence import PresenceManager
    from mary.realtime import RealtimeInteractionCoordinator
    from mary.streaming.presence import StreamingPresenceCoordinator

    realtime = RealtimeInteractionCoordinator()
    presence = PresenceManager(tmp_path / "presence", attention=realtime.attention)
    stream = StreamingPresenceCoordinator(presence, speaker_scheduler=realtime.speaker_scheduler)
    msg = ChatMessage(
        platform="twitch", channel="test", message_id="floor-1", author_id="viewer-2",
        display_name="Viewer2", text="Mary, what do you think?", direct_to_mary=True,
    )
    realtime.speaker_scheduler.set_floor("creator", reason="test")
    result = stream.ingest_chat(msg, creator_speaking=False)
    assert result["selection"]["action"] == "notice"
    assert "speaker_floor:wait" in result["selection"]["reasons"]
    assert stream.snapshot()["speaker_scheduler"]["pending_count"] == 1
