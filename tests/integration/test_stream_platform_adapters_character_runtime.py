import base64
import hashlib

from mary.integrations.obs_client import (
    ObsHello,
    authentication_string,
    identify_message,
    normalize_obs_event,
    parse_hello,
)
from mary.integrations.twitch_eventsub import (
    CHAT_MESSAGE_TYPE,
    TwitchEventSubConfig,
    normalize_chat_notification,
    session_from_welcome,
)


def test_twitch_welcome_and_subscription_are_transport_only():
    welcome = {
        "metadata": {"message_type": "session_welcome"},
        "payload": {"session": {"id": "session-123", "status": "connected"}},
    }
    session = session_from_welcome(welcome)
    assert session == {"id": "session-123", "status": "connected"}

    cfg = TwitchEventSubConfig(
        client_id="client",
        oauth_token="test-oauth-token",
        broadcaster_user_id="broadcaster",
        user_id="chat-user",
    )
    body = cfg.subscription_body(session["id"])
    assert body["type"] == CHAT_MESSAGE_TYPE
    assert body["transport"] == {"method": "websocket", "session_id": "session-123"}
    public = cfg.public_status()
    assert public["configured"] is True
    assert public["token_present"] is True
    assert "test-oauth-token" not in repr(public)
    assert public["authority"] == "untrusted_social_input_only"


def test_twitch_notification_normalizes_to_existing_chat_contract():
    payload = {
        "metadata": {"message_type": "notification"},
        "payload": {
            "subscription": {"type": CHAT_MESSAGE_TYPE},
            "event": {
                "broadcaster_user_login": "unbeknownstx",
                "chatter_user_id": "42",
                "chatter_user_name": "ArtGirl",
                "message_id": "msg-1",
                "message": {"text": "Mary, the purple beanie wins"},
                "message_type": "text",
                "color": "#123456",
                "badges": [{"set_id": "subscriber"}],
            },
        },
    }
    message = normalize_chat_notification(payload)
    assert message is not None
    assert message.platform == "twitch"
    assert message.channel == "unbeknownstx"
    assert message.direct_to_mary is True
    assert message.text == "Mary, the purple beanie wins"
    assert message.metadata["badges"] == "subscriber"


def test_obs_authentication_matches_protocol_formula():
    hello = ObsHello(rpc_version=1, challenge="challenge", salt="salt")
    first = base64.b64encode(hashlib.sha256(b"passwordsalt").digest()).decode("ascii")
    expected = base64.b64encode(hashlib.sha256((first + "challenge").encode()).digest()).decode("ascii")
    assert authentication_string("password", hello) == expected


def test_obs_hello_identify_and_event_sanitize():
    hello = parse_hello({
        "op": 0,
        "d": {
            "rpcVersion": 1,
            "authentication": {"challenge": "abc", "salt": "def"},
        },
    })
    identify = identify_message(hello, password="pw", event_subscriptions=(1 << 0) | (1 << 2) | (1 << 6))
    assert identify["op"] == 1
    assert identify["d"]["rpcVersion"] == 1
    assert identify["d"]["authentication"]

    event = normalize_obs_event({
        "op": 5,
        "d": {
            "eventType": "CurrentProgramSceneChanged",
            "eventData": {
                "sceneName": "Mary Stream",
                "authorizationToken": "must-not-leak",
                "nested": {"not": "copied"},
            },
        },
    })
    assert event is not None
    assert event["summary"] == "CurrentProgramSceneChanged"
    assert event["metadata"]["sceneName"] == "Mary Stream"
    assert "authorizationToken" not in event["metadata"]
    assert "nested" not in event["metadata"]
    assert event["authority"] == "environment_context_only"
