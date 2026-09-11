"""Ephemeral stream-input governor for MaryV2.

Chat remains untrusted social context. The governor performs cheap normalization,
dedupe, cooldown, injection/spam/bait heuristics, and ignored-chat texture
summaries before existing Streaming Presence / Attention decides react-note-drop.
No result here is durable relationship truth or tool authority.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, asdict
from time import monotonic
from typing import Any
import re

_INJECTION = re.compile(r"\b(ignore (all|any|the) (previous|prior)|system prompt|developer message|reveal (your|the) prompt|act as root|jailbreak)\b", re.I)
_SPAM = re.compile(r"(.)\1{7,}")
_HOSTILE_BAIT = re.compile(r"\b(kill yourself|kys|doxx? |swat |leak (their|his|her) address)\b", re.I)


@dataclass(frozen=True)
class StreamInputDecision:
    action: str
    score_delta: float = 0.0
    reasons: tuple[str, ...] = ()
    unsafe: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StreamInputGovernor:
    VERSION = "1"

    def __init__(self, *, viewer_cooldown_seconds: float = 4.0, answered_ttl_seconds: float = 120.0, texture_capacity: int = 120) -> None:
        self.viewer_cooldown_seconds = max(0.0, float(viewer_cooldown_seconds))
        self.answered_ttl_seconds = max(10.0, float(answered_ttl_seconds))
        self._last_viewer: dict[str, float] = {}
        self._answered: dict[str, float] = {}
        self._unsafe_until: dict[str, float] = {}
        self._texture: deque[str] = deque(maxlen=max(20, int(texture_capacity)))
        self._stats = Counter()

    @staticmethod
    def _clean(text: str) -> str:
        return " ".join(str(text or "").split())[:500]

    def evaluate(self, message: Any) -> StreamInputDecision:
        now = monotonic()
        text = self._clean(getattr(message, "text", ""))
        author = str(getattr(message, "author_id", "") or "")[:160]
        message_id = str(getattr(message, "message_id", "") or "")[:200]
        direct = bool(getattr(message, "direct_to_mary", False))
        if not text or not message_id:
            self._stats["drop_empty"] += 1
            return StreamInputDecision("drop", reasons=("empty_or_missing_id",))
        self._answered = {k: v for k, v in self._answered.items() if now - v <= self.answered_ttl_seconds}
        self._unsafe_until = {k: v for k, v in self._unsafe_until.items() if v > now}
        if message_id in self._answered:
            self._stats["drop_answered"] += 1
            return StreamInputDecision("drop", reasons=("recently_answered",))
        if author and author in self._unsafe_until:
            self._stats["drop_unsafe_viewer"] += 1
            return StreamInputDecision("drop", reasons=("temporary_unsafe_viewer",), unsafe=True)
        if _INJECTION.search(text):
            if author:
                self._unsafe_until[author] = now + 180.0
            self._stats["drop_injection"] += 1
            self._texture.append("prompt-injection attempt filtered")
            return StreamInputDecision("drop", reasons=("prompt_injection_pattern",), unsafe=True)
        if _HOSTILE_BAIT.search(text):
            if author:
                self._unsafe_until[author] = now + 300.0
            self._stats["drop_hostile_bait"] += 1
            return StreamInputDecision("drop", reasons=("hostile_or_privacy_bait",), unsafe=True)
        if _SPAM.search(text) or (len(text.split()) >= 7 and len(set(text.casefold().split())) <= 2):
            self._stats["note_spam"] += 1
            self._texture.append(text)
            return StreamInputDecision("note", score_delta=-0.35, reasons=("spam_like",))
        last = self._last_viewer.get(author) if author else None
        if author:
            self._last_viewer[author] = now
        if last is not None and now - last < self.viewer_cooldown_seconds and not direct:
            self._stats["note_cooldown"] += 1
            self._texture.append(text)
            return StreamInputDecision("note", score_delta=-0.25, reasons=("viewer_cooldown",))
        self._stats["pass"] += 1
        return StreamInputDecision("pass", score_delta=0.0, reasons=("governor_pass",))

    def mark_answered(self, message_id: str) -> None:
        value = str(message_id or "").strip()
        if value:
            self._answered[value[:200]] = monotonic()

    def note_ignored(self, text: str) -> None:
        value = self._clean(text)
        if value:
            self._texture.append(value)

    def texture_summary(self, *, limit: int = 5) -> list[dict[str, Any]]:
        normalized = [" ".join(x.casefold().split()) for x in self._texture if x.strip()]
        counts = Counter(normalized)
        return [{"text": text[:180], "count": count} for text, count in counts.most_common(max(1, min(12, int(limit))))]

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "stats": dict(self._stats),
            "texture": self.texture_summary(),
            "temporary_unsafe_viewers": len(self._unsafe_until),
            "recently_answered": len(self._answered),
            "authority": "ephemeral untrusted-input filtering only",
        }
