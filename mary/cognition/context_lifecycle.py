"""MaryV2 active conversation context lifecycle.

This module manages the *LLM-facing* slice of the current dialogue session.
It does not own dialogue history and it does not create durable memory.

DialogueManager remains the source of truth for the current session, while
MemoryManager remains the source of truth for durable episodic/semantic memory.
The lifecycle simply chooses a bounded recent window plus a few tiny, temporary
anchors from older user turns so long conversations do not grow every prompt
without bound.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable


_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ConversationContextWindow:
    """Bounded active-session context selected for one cognitive turn."""

    messages: tuple[dict[str, str], ...]
    anchors: tuple[str, ...] = ()
    total_messages: int = 0
    dropped_messages: int = 0
    selected_characters: int = 0
    max_characters: int = 0
    max_turns: int = 0
    policy: str = "recent_turns_plus_ephemeral_anchors"
    promotion_policy: str = "explicit_or_existing_development_paths_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages": [dict(item) for item in self.messages],
            "anchors": list(self.anchors),
            "total_messages": self.total_messages,
            "selected_messages": len(self.messages),
            "dropped_messages": self.dropped_messages,
            "selected_characters": self.selected_characters,
            "max_characters": self.max_characters,
            "max_turns": self.max_turns,
            "policy": self.policy,
            "promotion_policy": self.promotion_policy,
        }


class ConversationContextLifecycle:
    """Select compact recent dialogue without mutating Mary's memories."""

    def __init__(
        self,
        *,
        max_turns: int = 4,
        max_characters: int = 5_000,
        max_message_characters: int = 1_800,
        max_anchors: int = 3,
        anchor_characters: int = 180,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        if max_characters < 500:
            raise ValueError("max_characters must be at least 500")
        if max_message_characters < 200:
            raise ValueError("max_message_characters must be at least 200")
        if max_anchors < 0:
            raise ValueError("max_anchors cannot be negative")
        if anchor_characters < 40:
            raise ValueError("anchor_characters must be at least 40")

        self.max_turns = int(max_turns)
        self.max_characters = int(max_characters)
        self.max_message_characters = int(max_message_characters)
        self.max_anchors = int(max_anchors)
        self.anchor_characters = int(anchor_characters)

    def select(
        self,
        history: Iterable[dict[str, Any]] | None,
    ) -> ConversationContextWindow:
        """Return a bounded recent window and ephemeral older-turn anchors.

        The input is expected to be completed dialogue *before* the current user
        message. The newest complete turns are preserved first. Older content is
        not summarized by an LLM; only short user-authored anchors are retained.
        """

        normalized = self._normalize(history or [])
        if not normalized:
            return ConversationContextWindow(
                messages=(),
                total_messages=0,
                dropped_messages=0,
                selected_characters=0,
                max_characters=self.max_characters,
                max_turns=self.max_turns,
            )

        turns = self._group_turns(normalized)
        selected_turns: list[list[dict[str, str]]] = []
        selected_chars = 0

        for turn in reversed(turns):
            if len(selected_turns) >= self.max_turns:
                break

            compact_turn = [
                {
                    "role": item["role"],
                    "content": self._truncate_message(item["content"]),
                }
                for item in turn
            ]
            turn_chars = sum(len(item["content"]) for item in compact_turn)

            # Always preserve the newest completed turn even if it was unusually
            # long; individual-message truncation already bounds worst-case size.
            if selected_turns and selected_chars + turn_chars > self.max_characters:
                break

            selected_turns.append(compact_turn)
            selected_chars += turn_chars

        selected_turns.reverse()
        selected = [item for turn in selected_turns for item in turn]

        selected_count = len(selected)
        dropped_count = max(0, len(normalized) - selected_count)
        dropped_prefix = normalized[:dropped_count]
        anchors = self._build_anchors(dropped_prefix)

        return ConversationContextWindow(
            messages=tuple(selected),
            anchors=tuple(anchors),
            total_messages=len(normalized),
            dropped_messages=dropped_count,
            selected_characters=selected_chars,
            max_characters=self.max_characters,
            max_turns=self.max_turns,
        )

    @staticmethod
    def _normalize(history: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for raw in history:
            if not isinstance(raw, dict):
                continue
            role = str(raw.get("role", "")).strip().lower()
            content = _SPACE_RE.sub(" ", str(raw.get("content", ""))).strip()
            if role not in {"user", "assistant", "system", "tool"}:
                continue
            if not content:
                continue
            items.append({"role": role, "content": content})
        return items

    @staticmethod
    def _group_turns(messages: list[dict[str, str]]) -> list[list[dict[str, str]]]:
        turns: list[list[dict[str, str]]] = []
        current: list[dict[str, str]] = []

        for item in messages:
            if item["role"] == "user" and current:
                turns.append(current)
                current = []
            current.append(item)

        if current:
            turns.append(current)

        return turns

    def _truncate_message(self, content: str) -> str:
        if len(content) <= self.max_message_characters:
            return content

        marker = " ...[older turn clipped]... "
        available = max(0, self.max_message_characters - len(marker))
        head = available // 2
        tail = available - head
        return content[:head].rstrip() + marker + content[-tail:].lstrip()

    def _build_anchors(self, dropped: list[dict[str, str]]) -> list[str]:
        if self.max_anchors <= 0:
            return []

        user_messages = [
            item["content"]
            for item in dropped
            if item.get("role") == "user"
        ]

        anchors: list[str] = []
        for content in user_messages[-self.max_anchors :]:
            anchor = self._anchor(content)
            if anchor and anchor not in anchors:
                anchors.append(anchor)
        return anchors

    def _anchor(self, content: str) -> str:
        text = _SPACE_RE.sub(" ", str(content)).strip()
        if not text:
            return ""
        if len(text) <= self.anchor_characters:
            return text
        return text[: self.anchor_characters - 1].rstrip() + "…"
