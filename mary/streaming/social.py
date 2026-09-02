"""Bounded audience roster for live social context.

This is intentionally not Mary's relationship model.  It keeps stable public
platform identities and lightweight session familiarity so repeated viewers can
be treated as people rather than an anonymous wall of text without promoting
raw stream chat into durable personal memory.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import log1p
from threading import RLock
from typing import Any

from .chat import ChatMessage, ChatSelection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AudienceMember:
    identity: str
    platform: str
    author_id: str
    display_name: str
    messages_seen: int = 0
    direct_mentions: int = 0
    noticed: int = 0
    response_candidates: int = 0
    first_seen: str = ""
    last_seen: str = ""

    @property
    def familiarity(self) -> float:
        # Deliberately slow-growing.  Session familiarity is texture, not trust.
        return min(1.0, log1p(max(0, self.messages_seen)) / log1p(60))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["familiarity"] = round(self.familiarity, 3)
        return payload


class AudienceRoster:
    VERSION = "1"

    def __init__(self, *, capacity: int = 512) -> None:
        self.capacity = max(32, min(5000, int(capacity)))
        self._members: dict[str, AudienceMember] = {}
        self._order: list[str] = []
        self._lock = RLock()

    @staticmethod
    def identity_for(message: ChatMessage) -> str:
        return f"{str(message.platform or 'unknown').casefold()}:{str(message.author_id or 'unknown')}"[:180]

    def observe(self, message: ChatMessage, selection: ChatSelection | None = None) -> AudienceMember:
        identity = self.identity_for(message)
        now = _now()
        with self._lock:
            member = self._members.get(identity)
            if member is None:
                member = AudienceMember(
                    identity=identity,
                    platform=str(message.platform or "unknown")[:40],
                    author_id=str(message.author_id or "unknown")[:120],
                    display_name=str(message.display_name or "viewer")[:120],
                    first_seen=now,
                    last_seen=now,
                )
                self._members[identity] = member
                self._order.append(identity)
            member.display_name = str(message.display_name or member.display_name)[:120]
            member.messages_seen += 1
            member.last_seen = now
            if message.direct_to_mary:
                member.direct_mentions += 1
            if selection is not None:
                if selection.action == "notice":
                    member.noticed += 1
                elif selection.action == "respond":
                    member.response_candidates += 1
            while len(self._members) > self.capacity and self._order:
                oldest = self._order.pop(0)
                self._members.pop(oldest, None)
            return member

    def get(self, identity: str) -> AudienceMember | None:
        with self._lock:
            return self._members.get(str(identity))

    def top(self, *, limit: int = 12) -> list[dict[str, Any]]:
        with self._lock:
            members = sorted(
                self._members.values(),
                key=lambda item: (item.response_candidates, item.direct_mentions, item.messages_seen, item.last_seen),
                reverse=True,
            )
            return [item.to_dict() for item in members[: max(1, min(50, int(limit)))]]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            count = len(self._members)
        return {
            "version": self.VERSION,
            "known_this_session": count,
            "top": self.top(limit=12),
            "policy": "session social texture only; familiarity is not trust and does not mutate Mary's creator relationship",
        }
