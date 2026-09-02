"""Optional Twitch EventSub chat adapter for MaryV2.

The adapter is deliberately transport-only. It converts Twitch chat events into
Mary's platform-neutral ``ChatMessage`` contract. It never calls cognition, tools,
or memory directly. A node/runner forwards the normalized message to Mary Core.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from mary.streaming import ChatMessage


EVENTSUB_URL = "wss://eventsub.wss.twitch.tv/ws"
CHAT_MESSAGE_TYPE = "channel.chat.message"
CHAT_MESSAGE_VERSION = "1"


@dataclass(frozen=True)
class TwitchEventSubConfig:
    client_id: str
    oauth_token: str
    broadcaster_user_id: str
    user_id: str

    def subscription_body(self, session_id: str) -> dict[str, Any]:
        if not session_id.strip():
            raise ValueError("EventSub session id is required")
        return {
            "type": CHAT_MESSAGE_TYPE,
            "version": CHAT_MESSAGE_VERSION,
            "condition": {
                "broadcaster_user_id": self.broadcaster_user_id,
                "user_id": self.user_id,
            },
            "transport": {"method": "websocket", "session_id": session_id},
        }

    def public_status(self) -> dict[str, Any]:
        return {
            "configured": bool(self.client_id and self.oauth_token and self.broadcaster_user_id and self.user_id),
            "broadcaster_user_id": self.broadcaster_user_id[:32],
            "user_id": self.user_id[:32],
            "token_present": bool(self.oauth_token),
            "authority": "untrusted_social_input_only",
        }


def eventsub_message_type(payload: Mapping[str, Any]) -> str:
    metadata = payload.get("metadata") if isinstance(payload, Mapping) else {}
    return str((metadata or {}).get("message_type") or "").strip()


def session_from_welcome(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if eventsub_message_type(payload) != "session_welcome":
        return None
    body = payload.get("payload") if isinstance(payload, Mapping) else {}
    session = (body or {}).get("session") if isinstance(body, Mapping) else None
    return dict(session) if isinstance(session, Mapping) else None


def normalize_chat_notification(payload: Mapping[str, Any]) -> ChatMessage | None:
    if eventsub_message_type(payload) != "notification":
        return None
    body = payload.get("payload") if isinstance(payload, Mapping) else {}
    if not isinstance(body, Mapping):
        return None
    subscription = body.get("subscription")
    event = body.get("event")
    if not isinstance(subscription, Mapping) or not isinstance(event, Mapping):
        return None
    if str(subscription.get("type") or "") != CHAT_MESSAGE_TYPE:
        return None
    message = event.get("message")
    if not isinstance(message, Mapping):
        return None
    text = " ".join(str(message.get("text") or "").split())
    message_id = str(event.get("message_id") or "").strip()
    if not text or not message_id:
        return None
    display_name = str(event.get("chatter_user_name") or event.get("chatter_user_login") or "viewer")[:120]
    lower = text.casefold()
    return ChatMessage(
        message_id=message_id[:160],
        author_id=str(event.get("chatter_user_id") or "unknown")[:160],
        display_name=display_name,
        text=text[:1000],
        platform="twitch",
        channel=str(event.get("broadcaster_user_login") or event.get("broadcaster_user_name") or "")[:120],
        direct_to_mary=("@mary" in lower or lower.startswith("mary ") or lower.startswith("mary,")),
        metadata={
            "color": str(event.get("color") or "")[:32],
            "message_type": str(event.get("message_type") or "text")[:40],
            "badges": ",".join(str(x.get("set_id") or "") for x in list(event.get("badges") or [])[:8] if isinstance(x, Mapping))[:160],
        },
    )
