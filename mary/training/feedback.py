"""Explicit private response-feedback store for future Mary evaluation/training.

Nothing is logged merely because a conversation happened. A record exists only
after an explicit creator rating/correction action. Feedback is never identity,
memory, relationship, or development authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
from typing import Any
import uuid


_ALLOWED_RATINGS = {"positive", "negative", "neutral"}
_ALLOWED_TAGS = {
    "felt_like_mary", "did_not_feel_like_mary", "too_verbose", "too_short",
    "too_robotic", "too_agreeable", "good_question", "good_reaction",
    "wrong_memory", "good_memory", "voice_good", "voice_bad",
    "sarcasm_good", "sarcasm_bad", "flirt_good", "flirt_bad",
    "performance_good", "performance_bad", "correction_supplied",
}
_ALLOWED_SOURCE_KINDS = {"creator_turn", "mary_initiative"}


@dataclass(frozen=True)
class ResponseFeedback:
    rating: str
    assistant_text: str
    user_text: str = ""
    context_text: str = ""
    chosen_text: str = ""
    source_kind: str = "creator_turn"
    input_authority: str = "creator"
    provider: str = "unknown"
    model: str = "unknown"
    conversation_mode: str = "adaptive"
    performance_context: str = "private"
    character_patterns: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    note: str = ""
    turn_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id: str = field(default_factory=lambda: f"feedback_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResponseFeedbackStore:
    VERSION = "13.2"

    def __init__(self, path: str | Path | None = None, *, max_records: int = 5000) -> None:
        self.path = Path(path).expanduser().resolve() if path else None
        self.max_records = max(100, min(50_000, int(max_records)))
        self._lock = RLock()
        self._records: list[ResponseFeedback] = []
        if self.path and self.path.exists():
            self.load()

    def configure(self, path: str | Path, *, load: bool = True) -> None:
        with self._lock:
            self.path = Path(path).expanduser().resolve()
            self._records = []
            if load and self.path.exists():
                self.load()

    def load(self) -> bool:
        if self.path is None or not self.path.exists():
            return False
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            records: list[ResponseFeedback] = []
            for item in list(raw.get("records", []) if isinstance(raw, dict) else []):
                if not isinstance(item, dict):
                    continue
                rating = str(item.get("rating", "neutral")).strip().lower()
                if rating not in _ALLOWED_RATINGS:
                    continue
                tags = tuple(str(tag) for tag in item.get("tags", []) if str(tag) in _ALLOWED_TAGS)
                source_kind = str(item.get("source_kind") or "creator_turn").strip().lower()
                if source_kind not in _ALLOWED_SOURCE_KINDS:
                    source_kind = "creator_turn"
                records.append(ResponseFeedback(
                    rating=rating,
                    user_text=str(item.get("user_text", ""))[:4000],
                    context_text=str(item.get("context_text", ""))[:4000],
                    assistant_text=str(item.get("assistant_text", ""))[:8000],
                    chosen_text=str(item.get("chosen_text", item.get("correction_text", "")))[:8000],
                    source_kind=source_kind,
                    input_authority=str(item.get("input_authority", "creator"))[:80],
                    provider=str(item.get("provider", "unknown"))[:120],
                    model=str(item.get("model", "unknown"))[:160],
                    conversation_mode=str(item.get("conversation_mode", "adaptive"))[:60],
                    performance_context=str(item.get("performance_context", "private"))[:60],
                    character_patterns=tuple(str(x)[:80] for x in list(item.get("character_patterns", []) or [])[:12]),
                    tags=tags,
                    note=str(item.get("note", ""))[:1200],
                    turn_id=str(item.get("turn_id", ""))[:120],
                    created_at=str(item.get("created_at", "")) or datetime.now(timezone.utc).isoformat(),
                    id=str(item.get("id", "")) or f"feedback_{uuid.uuid4().hex[:12]}",
                ))
            with self._lock:
                self._records = records[-self.max_records:]
            return True
        except Exception:
            return False

    def save(self) -> bool:
        if self.path is None:
            return False
        with self._lock:
            payload = {
                "version": self.VERSION,
                "policy": {
                    "explicit_feedback_only": True,
                    "identity_authority": False,
                    "memory_authority": False,
                    "development_evidence": False,
                    "silent_conversation_harvest": False,
                },
                "records": [record.to_dict() for record in self._records[-self.max_records:]],
            }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.path)
            return True
        except OSError:
            return False

    def record(
        self,
        *,
        rating: str,
        assistant_text: str,
        user_text: str = "",
        context_text: str = "",
        chosen_text: str = "",
        source_kind: str = "creator_turn",
        input_authority: str = "creator",
        provider: str = "unknown",
        model: str = "unknown",
        conversation_mode: str = "adaptive",
        performance_context: str = "private",
        character_patterns: list[str] | tuple[str, ...] | None = None,
        tags: list[str] | tuple[str, ...] | None = None,
        note: str = "",
        turn_id: str = "",
    ) -> ResponseFeedback:
        resolved = str(rating or "").strip().lower()
        if resolved not in _ALLOWED_RATINGS:
            raise ValueError("rating must be positive, negative, or neutral")
        source = str(source_kind or "creator_turn").strip().lower()
        if source not in _ALLOWED_SOURCE_KINDS:
            raise ValueError("source_kind must be creator_turn or mary_initiative")
        safe_tags = list(dict.fromkeys(
            str(tag).strip() for tag in list(tags or [])
            if str(tag).strip() in _ALLOWED_TAGS
        ))[:12]
        chosen = str(chosen_text or "").strip()[:8000]
        if chosen and "correction_supplied" not in safe_tags:
            safe_tags.append("correction_supplied")
        record = ResponseFeedback(
            rating=resolved,
            user_text=str(user_text or "").strip()[:4000],
            context_text=str(context_text or "").strip()[:4000],
            assistant_text=str(assistant_text or "").strip()[:8000],
            chosen_text=chosen,
            source_kind=source,
            input_authority=str(input_authority or "creator")[:80],
            provider=str(provider or "unknown")[:120],
            model=str(model or "unknown")[:160],
            conversation_mode=str(conversation_mode or "adaptive")[:60],
            performance_context=str(performance_context or "private")[:60],
            character_patterns=tuple(dict.fromkeys(str(x).strip()[:80] for x in list(character_patterns or []) if str(x).strip()))[:12],
            tags=tuple(safe_tags),
            note=str(note or "")[:1200],
            turn_id=str(turn_id or "")[:120],
        )
        if not record.assistant_text:
            raise ValueError("feedback requires a completed Mary response")
        if record.source_kind == "creator_turn" and not record.user_text:
            raise ValueError("creator-turn feedback requires the completed user text")
        if record.source_kind == "mary_initiative" and not record.context_text:
            raise ValueError("Mary-initiative feedback requires grounded initiative context")
        with self._lock:
            self._records.append(record)
            if len(self._records) > self.max_records:
                del self._records[: len(self._records) - self.max_records]
        self.save()
        return record

    def records(self) -> list[ResponseFeedback]:
        with self._lock:
            return list(self._records)

    def status(self) -> dict[str, Any]:
        with self._lock:
            counts = {rating: 0 for rating in sorted(_ALLOWED_RATINGS)}
            corrections = 0
            initiative = 0
            for item in self._records:
                counts[item.rating] += 1
                corrections += bool(item.chosen_text)
                initiative += item.source_kind == "mary_initiative"
            return {
                "version": self.VERSION,
                "records": len(self._records),
                "ratings": counts,
                "corrections": corrections,
                "initiative_ratings": initiative,
                "persistent": self.path is not None,
                "policy": "explicit creator feedback only; private evaluation/training data, never character-state authority",
            }
