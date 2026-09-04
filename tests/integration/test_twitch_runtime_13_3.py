from mary.integrations.twitch_eventsub import normalize_chat_notification
from mary.integrations.twitch_runtime import (
    EventSubSessionPhase,
    TwitchChatOutbox,
    TwitchEventSubSession,
)


def _frame(kind, payload):
    return {"metadata": {"message_type": kind}, "payload": payload}


def test_eventsub_session_tracks_welcome_notification_and_reconnect():
    session = TwitchEventSubSession()
    actions = session.handle(_frame("session_welcome", {"session": {"id": "s1", "keepalive_timeout_seconds": 10}}))
    assert actions[0].action == "subscribe"
    assert session.phase == EventSubSessionPhase.WELCOMED
    session.mark_subscribing()
    session.handle(_frame("notification", {}))
    assert session.phase == EventSubSessionPhase.READY
    actions = session.handle(_frame("session_reconnect", {"session": {"id": "s2", "reconnect_url": "wss://example.invalid/reconnect"}}))
    assert actions[0].action == "reconnect"
    assert session.phase == EventSubSessionPhase.RECONNECTING


def test_twitch_outbox_is_bounded_deduped_and_thread_aware():
    outbox = TwitchChatOutbox(approved_channels=("unbe",), bot_user_id="mary-id", max_messages=1)
    send, reason = outbox.plan(channel="#unbe", text=" hello   chat ", reply_parent_message_id="p1", dedupe_key="turn-1")
    assert reason == "ok"
    assert send is not None
    assert send.text == "hello chat"
    assert send.reply_parent_message_id == "p1"
    duplicate, reason = outbox.plan(channel="unbe", text="again", dedupe_key="turn-1")
    assert duplicate is None and reason == "duplicate"
    assert outbox.is_self_message(author_id="mary-id") is True


def test_eventsub_chat_preserves_reply_thread_metadata():
    payload = _frame("notification", {
        "subscription": {"type": "channel.chat.message"},
        "event": {
            "message_id": "m1",
            "chatter_user_id": "u1",
            "chatter_user_name": "Viewer",
            "broadcaster_user_login": "unbe",
            "message": {"text": "Mary hi"},
            "reply": {
                "parent_message_id": "p1",
                "parent_user_id": "u0",
                "thread_message_id": "t1",
            },
        },
    })
    message = normalize_chat_notification(payload)
    assert message is not None
    assert message.direct_to_mary is True
    assert message.metadata["reply_parent_message_id"] == "p1"
    assert message.metadata["reply_thread_message_id"] == "t1"
