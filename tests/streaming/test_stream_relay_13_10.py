from __future__ import annotations

import pytest

from mary.integrations.twitch_chat import TwitchChatSendConfig, parse_send_chat_response
from mary.streaming.relay import LocalOBSRelay, StreamRelayState


def test_relay_tracks_only_latest_bounded_audio_packet() -> None:
    state = StreamRelayState()
    first = state.publish_audio(b"abc", mime_type="audio/mpeg", caption="Hello chat")
    assert first.sequence == 1
    assert first.caption == "Hello chat"
    assert state.audio(1) == (b"abc", "audio/mpeg")

    second = state.publish_audio(b"defg", mime_type="audio/wav", caption="Second")
    assert second.sequence == 2
    assert state.audio(1) is None
    assert state.audio(2) == (b"defg", "audio/wav")


def test_relay_rejects_non_audio_and_non_loopback_binding() -> None:
    state = StreamRelayState()
    with pytest.raises(ValueError):
        state.publish_audio(b"abc", mime_type="text/plain")
    with pytest.raises(ValueError):
        LocalOBSRelay(host="0.0.0.0")


def test_twitch_send_contract_is_bounded_and_supports_replies() -> None:
    cfg = TwitchChatSendConfig(
        client_id="client",
        oauth_token="token",
        broadcaster_user_id="broadcaster",
        sender_user_id="mary-bot",
    )
    body = cfg.body("x" * 700, reply_parent_message_id="parent-1")
    assert body["broadcaster_id"] == "broadcaster"
    assert body["sender_id"] == "mary-bot"
    assert len(body["message"]) == 500
    assert body["reply_parent_message_id"] == "parent-1"
    assert cfg.public_status()["token_present"] is True
    assert "token" not in str(cfg.public_status()).replace("token_present", "")


def test_twitch_send_response_exposes_only_safe_delivery_result() -> None:
    result = parse_send_chat_response({
        "data": [{
            "message_id": "sent-1",
            "is_sent": False,
            "drop_reason": {"code": "automod_held", "message": "held"},
        }]
    })
    assert result == {
        "is_sent": False,
        "message_id": "sent-1",
        "drop_code": "automod_held",
        "drop_message": "held",
    }
