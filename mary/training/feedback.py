"""Explicit private response-feedback store for future Mary model evaluation/training.

Nothing is logged merely because a conversation happened.  A record is created
only after an explicit creator rating/feedback action.  The store is private
runtime data and is never identity, memory, relationship, or development
authority.  It exists so Mary can accumulate a clean, consent-driven evaluation
set before custom adapters/LoRA training are attempted on stronger hardware.
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
    "felt_like_mary",
    "did_not_feel_like_mary",
    "too_verbose",
    "too_short",
    "too_robotic",
    "too_agreeable",
    "good_question",
    "good_reaction",
    "wrong_memory",
    "good_memory",
    "voice_good",
    "voice_bad",
}


@dataclass(frozen=True)
class ResponseFeedback:
    rating: str
    user_text: str
    assistant_text: str
    provider: str = "unknown"
    model: str = "unknown"
    conversation_mode: str = "adaptive"
    tags: tuple[str, ...] = ()
    note: str = ""
    turn_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id: str = field(default_factory=lambda: f"feedback_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResponseFeedbackStore:
    VERSION = "13.1"

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
            records = []
            for item in list(raw.get("records", []) if isinstance(raw, dict) else []):
                if not isinstance(item, dict):
                    continue
                rating = str(item.get("rating", "neutral")).strip().lower()
                if rating not in _ALLOWED_RATINGS:
                    continue
                tags = tuple(tag for tag in item.get("tags", []) if str(tag) in _ALLOWED_TAGS)
                records.append(ResponseFeedback(
                    rating=rating,
                    user_text=str(item.get("user_text", ""))[:4000],
                    assistant_text=str(item.get("assistant_text", ""))[:8000],
                    provider=str(item.get("provider", "unknown"))[:120],
                    model=str(item.get("model", "unknown"))[:160],
                    conversation_mode=str(item.get("conversation_mode", "adaptive"))[:60],
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
        user_text: str,
        assistant_text: str,
        provider: str = "unknown",
        model: str = "unknown",
        conversation_mode: str = "adaptive",
        tags: list[str] | tuple[str, ...] | None = None,
        note: str = "",
        turn_id: str = "",
    ) -> ResponseFeedback:
        resolved = str(rating or "").strip().lower()
        if resolved not in _ALLOWED_RATINGS:
            raise ValueError("rating must be positive, negative, or neutral")
        safe_tags = tuple(dict.fromkeys(str(tag).strip() for tag in list(tags or []) if str(tag).strip() in _ALLOWED_TAGS))[:12]
        record = ResponseFeedback(
            rating=resolved,
            user_text=str(user_text or "")[:4000],
            assistant_text=str(assistant_text or "")[:8000],
            provider=str(provider or "unknown")[:120],
            model=str(model or "unknown")[:160],
            conversation_mode=str(conversation_mode or "adaptive")[:60],
            tags=safe_tags,
            note=str(note or "")[:1200],
            turn_id=str(turn_id or "")[:120],
        )
        if not record.user_text or not record.assistant_text:
            raise ValueError("feedback requires the completed user/assistant turn")
        with self._lock:
            self._records.append(record)
            if len(self._records) > self.max_records:
                del self._records[: len(self._records) - self.max_records]
        self.save()
        return record

    def status(self) -> dict[str, Any]:
        with self._lock:
            counts = {rating: 0 for rating in sorted(_ALLOWED_RATINGS)}
            for item in self._records:
                counts[item.rating] += 1
            return {
                "version": self.VERSION,
                "records": len(self._records),
                "ratings": counts,
                "persistent": self.path is not None,
                "policy": "explicit creator feedback only; private evaluation/training data, never character-state authority",
            }
