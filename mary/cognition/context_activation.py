"""Bounded ephemeral context activation for MaryV2.

This mines the useful part of lorebook/character systems: small authored facts or
instructions may become temporarily relevant when recent conversation contains a
matching cue.  Activation is a prompt projection only. It is never Mary memory,
relationship truth, identity authority, or an autonomous write path.

Safety/continuity properties:
- scan only a bounded recent-message window;
- hard character budget;
- source/provenance retained;
- no recursive activation (activated text is never re-scanned for more keys);
- deterministic ordering and deduplication;
- wildcard support is deliberately narrow: leading/trailing ``*`` only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class ContextCue:
    cue_id: str
    keys: tuple[str, ...]
    text: str
    source: str = "creator_authored"
    category: str = "context"
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActivatedContext:
    cue_id: str
    text: str
    source: str
    category: str
    matched_key: str
    priority: int

    def prompt_view(self) -> dict[str, Any]:
        return {
            "id": self.cue_id,
            "text": self.text,
            "source": self.source,
            "category": self.category,
            "matched_key": self.matched_key,
            "boundary": "ephemeral_context_not_memory",
        }


class ContextActivationEngine:
    """Select small prompt-only context from recent creator/assistant messages."""

    VERSION = "13.26"

    def __init__(
        self,
        cues: Iterable[ContextCue] = (),
        *,
        recent_messages: int = 4,
        max_characters: int = 1600,
        max_activations: int = 6,
    ) -> None:
        self.cues = tuple(cues)
        self.recent_messages = max(1, min(12, int(recent_messages)))
        self.max_characters = max(128, min(12_000, int(max_characters)))
        self.max_activations = max(1, min(24, int(max_activations)))

    @staticmethod
    def _message_text(item: Any) -> str:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return str(item.get("content") or item.get("text") or "")
        return str(getattr(item, "content", getattr(item, "text", "")) or "")

    @staticmethod
    def _matches(text: str, key: str) -> bool:
        haystack = text.casefold()
        raw = str(key or "").strip().casefold()
        if not raw:
            return False
        leading = raw.startswith("*")
        trailing = raw.endswith("*")
        needle = raw.strip("*").strip()
        if not needle:
            return False
        if leading and trailing:
            return needle in haystack
        if leading:
            return haystack.rstrip().endswith(needle)
        if trailing:
            return haystack.lstrip().startswith(needle)
        return needle in haystack

    def activate(self, history: Iterable[Any] | None) -> tuple[ActivatedContext, ...]:
        # Only original conversation text is scanned. Activated cue text is never
        # appended back into this search material, preventing recursive triggers.
        recent = list(history or [])[-self.recent_messages :]
        searchable = "\n".join(self._message_text(item) for item in recent if self._message_text(item)).strip()
        if not searchable:
            return ()

        candidates: list[ActivatedContext] = []
        for cue in self.cues:
            text = " ".join(str(cue.text or "").split())
            if not cue.cue_id or not text:
                continue
            for key in cue.keys:
                if self._matches(searchable, key):
                    candidates.append(ActivatedContext(
                        cue_id=str(cue.cue_id)[:120],
                        text=text,
                        source=str(cue.source or "creator_authored")[:180],
                        category=str(cue.category or "context")[:80],
                        matched_key=str(key)[:160],
                        priority=max(-1000, min(1000, int(cue.priority))),
                    ))
                    break

        # Higher priority first, then stable cue id. A cue may activate at most once.
        candidates.sort(key=lambda item: (-item.priority, item.cue_id))
        selected: list[ActivatedContext] = []
        used_ids: set[str] = set()
        used_chars = 0
        for item in candidates:
            if item.cue_id in used_ids or len(selected) >= self.max_activations:
                continue
            remaining = self.max_characters - used_chars
            if remaining <= 0:
                break
            if len(item.text) > remaining:
                # Do not inject a misleading partial fact/instruction.
                continue
            selected.append(item)
            used_ids.add(item.cue_id)
            used_chars += len(item.text)
        return tuple(selected)

    def prompt_view(self, history: Iterable[Any] | None) -> dict[str, Any]:
        active = self.activate(history)
        return {
            "version": self.VERSION,
            "policy": "bounded_recent_trigger_context_no_recursive_activation",
            "items": [item.prompt_view() for item in active],
            "used_characters": sum(len(item.text) for item in active),
            "max_characters": self.max_characters,
            "persistence": "none",
            "authority": "prompt_context_only",
        }
