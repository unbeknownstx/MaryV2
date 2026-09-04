"""Resilient, network-neutral Twitch runtime contracts for MaryV2 13.3.

No network calls are made here.  The contracts model EventSub session lifecycle,
outbound chat safety, reply threading, self-echo suppression, deduplication, and
bounded rate planning.  A future Mac/Windows Twitch node performs the actual
WebSocket/HTTP I/O and feeds these sanitized decisions to canonical Mary Core.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from time import monotonic
from typing import Any, Mapping
import uuid


class EventSubSessionPhase(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    WELCOMED = "welcomed"
    SUBSCRIBING = "subscribing"
    READY = "ready"
    RECONNECTING = "reconnecting"
    REVOKED = "revoked"


@dataclass(frozen=True)
class EventSubControlAction:
    action: str
    session_id: str = ""
    reconnect_url: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TwitchEventSubSession:
    """Small explicit state machine for EventSub WebSocket continuity."""

    VERSION = "1"

    def __init__(self) -> None:
        self.phase = EventSubSessionPhase.DISCONNECTED
        self.session_id = ""
        self.connected_at = ""
        self.keepalive_timeout_seconds: float | None = None
        self.last_message_monotonic = monotonic()
        self.reconnect_url = ""
        self.reconnects = 0
        self.notifications = 0
        self.revocations = 0

    def connecting(self) -> None:
        self.phase = EventSubSessionPhase.CONNECTING

    @staticmethod
    def _message_type(payload: Mapping[str, Any]) -> str:
        metadata = payload.get("metadata") if isinstance(payload, Mapping) else {}
        return str((metadata or {}).get("message_type") or "").strip()

    def handle(self, payload: Mapping[str, Any]) -> list[EventSubControlAction]:
        self.last_message_monotonic = monotonic()
        message_type = self._message_type(payload)
        body = payload.get("payload") if isinstance(payload, Mapping) else {}
        body = body if isinstance(body, Mapping) else {}
        actions: list[EventSubControlAction] = []

        if message_type == "session_welcome":
            session = body.get("session") if isinstance(body, Mapping) else {}
            session = session if isinstance(session, Mapping) else {}
            self.session_id = str(session.get("id") or "")[:160]
            self.reconnect_url = ""
            try:
                timeout = session.get("keepalive_timeout_seconds")
                self.keepalive_timeout_seconds = float(timeout) if timeout is not None else None
            except (TypeError, ValueError):
                self.keepalive_timeout_seconds = None
            self.connected_at = datetime.now(timezone.utc).isoformat()
            self.phase = EventSubSessionPhase.WELCOMED
            actions.append(EventSubControlAction("subscribe", session_id=self.session_id))
            return actions

        if message_type == "session_keepalive":
            return actions

        if message_type == "notification":
            self.notifications += 1
            if self.phase in {EventSubSessionPhase.WELCOMED, EventSubSessionPhase.SUBSCRIBING}:
                self.phase = EventSubSessionPhase.READY
            return actions

        if message_type == "session_reconnect":
            session = body.get("session") if isinstance(body, Mapping) else {}
            session = session if isinstance(session, Mapping) else {}
            self.reconnect_url = str(session.get("reconnect_url") or "")[:500]
            self.phase = EventSubSessionPhase.RECONNECTING
            self.reconnects += 1
            actions.append(
                EventSubControlAction(
                    "reconnect",
                    session_id=str(session.get("id") or self.session_id)[:160],
                    reconnect_url=self.reconnect_url,
                    reason="twitch_requested_reconnect",
                )
            )
            return actions

        if message_type == "revocation":
            subscription = body.get("subscription") if isinstance(body, Mapping) else {}
            subscription = subscription if isinstance(subscription, Mapping) else {}
            self.phase = EventSubSessionPhase.REVOKED
            self.revocations += 1
            actions.append(
                EventSubControlAction(
                    "resubscribe_required",
                    session_id=self.session_id,
                    reason=str(subscription.get("status") or "revoked")[:160],
                )
            )
        return actions

    def mark_subscribing(self) -> None:
        if self.phase == EventSubSessionPhase.WELCOMED:
            self.phase = EventSubSessionPhase.SUBSCRIBING

    def mark_ready(self) -> None:
        if self.phase not in {EventSubSessionPhase.REVOKED, EventSubSessionPhase.DISCONNECTED}:
            self.phase = EventSubSessionPhase.READY

    def disconnected(self) -> None:
        self.phase = EventSubSessionPhase.DISCONNECTED

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "phase": self.phase.value,
            "session_id": self.session_id,
            "connected_at": self.connected_at,
            "keepalive_timeout_seconds": self.keepalive_timeout_seconds,
            "reconnect_pending": bool(self.reconnect_url),
            "reconnects": self.reconnects,
            "notifications": self.notifications,
            "revocations": self.revocations,
            "policy": "transport continuity only; no Mary identity or memory authority",
        }


@dataclass(frozen=True)
class TwitchChatSend:
    channel: str
    text: str
    reply_parent_message_id: str = ""
    request_id: str = field(default_factory=lambda: f"twitch_send_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["text"] = " ".join(str(self.text).split())[:500]
        return payload


class TwitchChatOutbox:
    """Bounded outbound planner; actual HTTP send belongs to a capability node."""

    VERSION = "1"

    def __init__(
        self,
        *,
        approved_channels: tuple[str, ...] = (),
        bot_user_id: str = "",
        max_messages: int = 18,
        window_seconds: float = 30.0,
        capacity: int = 128,
    ) -> None:
        self.approved_channels = {str(x).strip().casefold().lstrip("#") for x in approved_channels if str(x).strip()}
        self.bot_user_id = str(bot_user_id or "")[:160]
        self.max_messages = max(1, min(100, int(max_messages)))
        self.window_seconds = max(1.0, min(120.0, float(window_seconds)))
        self._sent_times: deque[float] = deque()
        self._recent: deque[TwitchChatSend] = deque(maxlen=max(16, min(1024, int(capacity))))
        self._dedupe: deque[str] = deque(maxlen=max(16, min(1024, int(capacity))))
        self._stats = {"planned": 0, "rate_limited": 0, "rejected": 0, "duplicate": 0, "self_echo_ignored": 0}

    def is_self_message(self, *, author_id: str) -> bool:
        same = bool(self.bot_user_id and str(author_id or "") == self.bot_user_id)
        if same:
            self._stats["self_echo_ignored"] += 1
        return same

    def _prune(self, now: float) -> None:
        while self._sent_times and now - self._sent_times[0] >= self.window_seconds:
            self._sent_times.popleft()

    def plan(
        self,
        *,
        channel: str,
        text: str,
        reply_parent_message_id: str = "",
        dedupe_key: str = "",
    ) -> tuple[TwitchChatSend | None, str]:
        normalized_channel = str(channel or "").strip().casefold().lstrip("#")
        value = " ".join(str(text or "").split()).strip()[:500]
        if not normalized_channel or not value:
            self._stats["rejected"] += 1
            return None, "channel_and_text_required"
        if self.approved_channels and normalized_channel not in self.approved_channels:
            self._stats["rejected"] += 1
            return None, "channel_not_approved"
        key = str(dedupe_key or "").strip()[:200]
        if key and key in self._dedupe:
            self._stats["duplicate"] += 1
            return None, "duplicate"
        now = monotonic()
        self._prune(now)
        if len(self._sent_times) >= self.max_messages:
            self._stats["rate_limited"] += 1
            return None, "rate_limited"
        planned = TwitchChatSend(
            channel=normalized_channel,
            text=value,
            reply_parent_message_id=str(reply_parent_message_id or "")[:160],
        )
        self._sent_times.append(now)
        self._recent.append(planned)
        if key:
            self._dedupe.append(key)
        self._stats["planned"] += 1
        return planned, "ok"

    def snapshot(self) -> dict[str, Any]:
        now = monotonic()
        self._prune(now)
        return {
            "version": self.VERSION,
            "approved_channels": sorted(self.approved_channels),
            "bot_user_id_present": bool(self.bot_user_id),
            "window_seconds": self.window_seconds,
            "max_messages": self.max_messages,
            "remaining_in_window": max(0, self.max_messages - len(self._sent_times)),
            "stats": dict(self._stats),
            "recent": [item.to_dict() for item in list(self._recent)[-8:]],
            "policy": "outbound presentation only; actual Twitch I/O requires configured node credentials",
        }
