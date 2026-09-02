"""Bounded causal decision ledger for Mary's continuous realtime behavior.

Turn observability already traces canonical request execution.  This ledger fills
one different gap: many character decisions happen *between* turns (ambient
attention, floor arbitration, barge-in, speech queueing).  It records only
bounded labels/scores/reasons and never raw dialogue, prompts, audio, images, or
identity/memory state.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any
import uuid

_SECRET = {"token", "authorization", "api_key", "apikey", "secret", "password", "cookie", "credential"}


def _clip(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _metadata(values: dict[str, Any] | None) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in list(dict(values or {}).items())[:12]:
        name = _clip(key, 48)
        if not name or any(secret in name.casefold() for secret in _SECRET):
            continue
        if isinstance(value, bool):
            output[name] = value
        elif isinstance(value, (int, float)):
            output[name] = value
        elif value is not None:
            output[name] = _clip(value, 100)
    return output


@dataclass(frozen=True)
class DecisionTraceEntry:
    kind: str
    outcome: str
    reason: str
    score: float | None = None
    source: str = ""
    target: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    decision_id: str = field(default_factory=lambda: f"decision_{uuid.uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = _clip(self.kind, 48)
        payload["outcome"] = _clip(self.outcome, 48)
        payload["reason"] = _clip(self.reason, 180)
        payload["source"] = _clip(self.source, 64)
        payload["target"] = _clip(self.target, 64)
        payload["metadata"] = _metadata(self.metadata)
        if self.score is not None:
            payload["score"] = round(max(0.0, min(1.0, float(self.score))), 3)
        return payload


class RealtimeDecisionTrace:
    """Small process-local trace of *why* Mary reacted/waited/spoke."""

    VERSION = "1"

    def __init__(self, *, capacity: int = 160) -> None:
        self.capacity = max(32, min(1000, int(capacity)))
        self._entries: deque[DecisionTraceEntry] = deque(maxlen=self.capacity)
        self._lock = RLock()

    def record(
        self,
        kind: str,
        outcome: str,
        reason: str,
        *,
        score: float | None = None,
        source: str = "",
        target: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> DecisionTraceEntry:
        entry = DecisionTraceEntry(
            kind=_clip(kind, 48) or "unknown",
            outcome=_clip(outcome, 48) or "unknown",
            reason=_clip(reason, 180) or "unspecified",
            score=None if score is None else max(0.0, min(1.0, float(score))),
            source=_clip(source, 64),
            target=_clip(target, 64),
            metadata=_metadata(metadata),
        )
        with self._lock:
            self._entries.append(entry)
        return entry

    def recent(self, *, limit: int = 24) -> list[dict[str, Any]]:
        with self._lock:
            return [item.to_dict() for item in list(self._entries)[-max(1, min(100, int(limit))):]]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            entries = list(self._entries)
        kinds = Counter(item.kind for item in entries)
        outcomes = Counter(item.outcome for item in entries)
        return {
            "version": self.VERSION,
            "count": len(entries),
            "kinds": dict(kinds.most_common(12)),
            "outcomes": dict(outcomes.most_common(12)),
            "recent": [item.to_dict() for item in entries[-24:]],
            "policy": (
                "ephemeral causal observability only; no raw dialogue/media, no canonical memory, "
                "and no decision trace entry grants authority"
            ),
        }
