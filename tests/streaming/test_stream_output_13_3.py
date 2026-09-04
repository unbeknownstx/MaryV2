from mary.presence import PresenceManager
from mary.streaming import ChatMessage, StreamingPresenceCoordinator
from mary.streaming.output import StreamOutputMode, plan_stream_response


def test_direct_chat_can_use_both_when_creator_floor_is_open():
    plan = plan_stream_response(
        action="respond",
        score=.91,
        direct_to_mary=True,
        creator_speaking=False,
        floor_disposition="speak",
        target_identity="twitch:u1",
        reply_to_message_id="m1",
    )
    assert plan.mode == StreamOutputMode.BOTH
    assert plan.reply_to_message_id == "m1"


def test_direct_chat_types_instead_of_stealing_creator_audio_floor():
    plan = plan_stream_response(
        action="respond",
        score=.95,
        direct_to_mary=True,
        creator_speaking=True,
        floor_disposition="wait",
    )
    assert plan.mode == StreamOutputMode.CHAT
    assert plan.voice_priority < plan.chat_priority


def test_stream_coordinator_suppresses_registered_self_echo(tmp_path):
    stream = StreamingPresenceCoordinator(PresenceManager(tmp_path), self_author_ids={"mary-bot"})
    result = stream.ingest_chat(
        ChatMessage(
            message_id="self-1",
            author_id="mary-bot",
            display_name="Mary",
            text="I already sent this.",
            platform="twitch",
        )
    )
    assert result == {"accepted": False, "reason": "self_echo"}
    assert stream.snapshot()["stats"]["self_echo_ignored"] == 1
