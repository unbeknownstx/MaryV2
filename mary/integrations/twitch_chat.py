"""Bounded Twitch Send Chat Message contract for MaryV2 stream cohosting.

Network execution remains in the explicit stream host adapter. This module only
validates/sanitizes the request/response shape so Mary Core credentials and
social context never become an implicit generic HTTP capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


SEND_CHAT_URL = "https://api.twitch.tv/helix/chat/messages"


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[: max(0, int(limit))]


@dataclass(frozen=True)
class TwitchChatSendConfig:
    client_id: str
    oauth_token: str
    broadcaster_user_id: str
    sender_user_id: str

    @property
    def configured(self) -> bool:
        return bool(
            self.client_id.strip()
            and self.oauth_token.strip()
            and self.broadcaster_user_id.strip()
            and self.sender_user_id.strip()
        )

    def public_status(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "broadcaster_user_id": self.broadcaster_user_id[:32],
            "sender_user_id": self.sender_user_id[:32],
            "token_present": bool(self.oauth_token),
            "endpoint": SEND_CHAT_URL,
            "authority": "typed stream presentation only",
        }

    def body(self, message: str, *, reply_parent_message_id: str = "") -> dict[str, str]:
        if not self.configured:
            raise ValueError("Twitch chat send configuration is incomplete")
        text = _clean(message, 500)
        if not text:
            raise ValueError("Twitch chat message cannot be empty")
        payload = {
            "broadcaster_id": _clean(self.broadcaster_user_id, 160),
            "sender_id": _clean(self.sender_user_id, 160),
            "message": text,
        }
        reply = _clean(reply_parent_message_id, 180)
        if reply:
            payload["reply_parent_message_id"] = reply
        return payload


def parse_send_chat_response(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = payload if isinstance(payload, Mapping) else {}
    data = raw.get("data")
    first = data[0] if isinstance(data, list) and data and isinstance(data[0], Mapping) else {}
    is_sent = bool(first.get("is_sent"))
    drop = first.get("drop_reason") if isinstance(first.get("drop_reason"), Mapping) else {}
    return {
        "is_sent": is_sent,
        "message_id": _clean(first.get("message_id"), 180),
        "drop_code": _clean(drop.get("code"), 80),
        "drop_message": _clean(drop.get("message"), 240),
    }
