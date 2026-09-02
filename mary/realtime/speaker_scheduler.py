"""Social-floor scheduling for Mary's realtime character presence.

SpeechOutputArbiter answers *which audio item may play*.  This scheduler answers
an earlier question: *is this a good moment for Mary to take the conversational
floor at all?*  The split mirrors mature multi-speaker VTuber systems while
preserving Mary's deterministic creator precedence and existing Presence owner.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from time import monotonic
from typing import Any
import uuid

from .decision_trace import RealtimeDecisionTrace


class FloorDisposition(str, Enum):
    SPEAK = "speak"
    WAIT = "wait"
    DROP = "drop"
    YIELD = "yield"


@dataclass(frozen=True)
class SpeakerOpportunity:
    speaker_id: str = "mary"
    source_kind: str = "conversation"
    source_id: str = ""
    target: str = "creator"
    relevance: float = 0.5
    direct: bool = False
    priority: int = 50
    ttl_seconds: float = 20.0
    metadata: dict[str, Any] = field(default_factory=dict)
    opportunity_id: str = field(default_factory=lambda: f"floor_{uuid.uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_monotonic: float = field(default_factory=monotonic, compare=False, repr=False)

    @property
    def expired(self) -> bool:
        return monotonic() - self.created_monotonic > max(1.0, float(self.ttl_seconds))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("created_monotonic", None)
        payload["relevance"] = round(max(0.0, min(1.0, float(self.relevance))), 3)
        payload["priority"] = max(0, min(100, int(self.priority)))
        payload["ttl_seconds"] = round(max(1.0, min(300.0, float(self.ttl_seconds))), 2)
        payload["metadata"] = {
            str(k)[:48]: str(v)[:100]
            for k, v in list(dict(self.metadata or {}).items())[:8]
            if str(k).casefold() not in {"token", "authorization", "api_key", "secret", "password", "text", "content"}
        }
        return payload


@dataclass(frozen=True)
class FloorDecision:
    disposition: FloorDisposition
    opportunity_id: str
    reason: str
    floor_owner: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["disposition"] = self.disposition.value
        payload["score"] = round(max(0.0, min(1.0, float(self.score))), 3)
        return payload


class SpeakerScheduler:
    """Bounded single-stage floor policy, separate from audio playback."""

    VERSION = "1"

    def __init__(
        self,
        *,
        capacity: int = 64,
        trace: RealtimeDecisionTrace | None = None,
        repeat_cooldown_seconds: float = 2.0,
    ) -> None:
        self.capacity = max(8, min(256, int(capacity)))
        self.trace = trace
        self.repeat_cooldown_seconds = max(0.0, min(30.0, float(repeat_cooldown_seconds)))
        self._pending: deque[SpeakerOpportunity] = deque(maxlen=self.capacity)
        self._floor_owner = "none"
        self._last_spoken_by_source: dict[str, float] = {}
        self._stats = {"speak": 0, "wait": 0, "drop": 0, "yield": 0, "expired": 0}
        self._lock = RLock()

    @staticmethod
    def _owner(value: str) -> str:
        owner = " ".join(str(value or "none").split()).strip().casefold()[:64]
        return owner or "none"

    def set_floor(self, owner: str, *, reason: str = "state_update") -> str:
        resolved = self._owner(owner)
        with self._lock:
            previous = self._floor_owner
            self._floor_owner = resolved
        if self.trace is not None and previous != resolved:
            self.trace.record("floor", resolved, reason, source=previous, target=resolved)
        return resolved

    @property
    def floor_owner(self) -> str:
        with self._lock:
            return self._floor_owner

    def _prune_locked(self) -> None:
        kept = deque(maxlen=self.capacity)
        for item in self._pending:
            if item.expired:
                self._stats["expired"] += 1
                continue
            kept.append(item)
        self._pending = kept

    def _record(self, decision: FloorDecision, opportunity: SpeakerOpportunity) -> FloorDecision:
        self._stats[decision.disposition.value] += 1
        if self.trace is not None:
            self.trace.record(
                "speaker_floor",
                decision.disposition.value,
                decision.reason,
                score=decision.score,
                source=opportunity.source_kind,
                target=opportunity.target,
                metadata={"floor_owner": decision.floor_owner, "direct": opportunity.direct},
            )
        return decision

    def consider(
        self,
        opportunity: SpeakerOpportunity,
        *,
        floor_owner: str | None = None,
        enqueue_wait: bool = True,
    ) -> FloorDecision:
        owner = self._owner(self.floor_owner if floor_owner is None else floor_owner)
        relevance = max(0.0, min(1.0, float(opportunity.relevance)))
        if opportunity.expired:
            return self._record(FloorDecision(FloorDisposition.DROP, opportunity.opportunity_id, "opportunity expired", owner, 0.0), opportunity)

        # Creator speech is a hard floor boundary, not a learned preference.
        if owner in {"creator", "human", "melvin"} and opportunity.speaker_id.casefold() != owner:
            if opportunity.direct or relevance >= .52:
                if enqueue_wait:
                    with self._lock:
                        self._prune_locked()
                        if not any(item.opportunity_id == opportunity.opportunity_id for item in self._pending):
                            self._pending.append(opportunity)
                return self._record(FloorDecision(FloorDisposition.WAIT, opportunity.opportunity_id, "creator currently owns conversational floor", owner, relevance), opportunity)
            return self._record(FloorDecision(FloorDisposition.DROP, opportunity.opportunity_id, "ambient opportunity is not strong enough to wait behind creator", owner, relevance), opportunity)

        if owner not in {"none", "idle", opportunity.speaker_id.casefold()}:
            if opportunity.direct or relevance >= .72:
                if enqueue_wait:
                    with self._lock:
                        self._prune_locked()
                        self._pending.append(opportunity)
                return self._record(FloorDecision(FloorDisposition.WAIT, opportunity.opportunity_id, "another participant owns conversational floor", owner, relevance), opportunity)
            return self._record(FloorDecision(FloorDisposition.DROP, opportunity.opportunity_id, "another participant has floor and opportunity is low priority", owner, relevance), opportunity)

        key = str(opportunity.source_id or opportunity.source_kind)[:160]
        last = self._last_spoken_by_source.get(key, 0.0)
        if (
            not opportunity.direct
            and self.repeat_cooldown_seconds > 0
            and last > 0
            and monotonic() - last < self.repeat_cooldown_seconds
        ):
            return self._record(FloorDecision(FloorDisposition.DROP, opportunity.opportunity_id, "source cooldown suppresses repetitive floor capture", owner, relevance), opportunity)

        if relevance < .34 and not opportunity.direct:
            return self._record(FloorDecision(FloorDisposition.DROP, opportunity.opportunity_id, "opportunity below social floor relevance threshold", owner, relevance), opportunity)
        return self._record(FloorDecision(FloorDisposition.SPEAK, opportunity.opportunity_id, "floor is available for Mary", owner, max(relevance, .65 if opportunity.direct else relevance)), opportunity)

    def next_ready(self, *, floor_owner: str | None = None) -> SpeakerOpportunity | None:
        owner = self._owner(self.floor_owner if floor_owner is None else floor_owner)
        if owner not in {"none", "idle", "mary"}:
            return None
        with self._lock:
            self._prune_locked()
            if not self._pending:
                return None
            ranked = sorted(
                self._pending,
                key=lambda item: (int(item.priority), -float(item.relevance), item.created_monotonic),
            )
            selected = ranked[0]
            self._pending = deque((item for item in self._pending if item.opportunity_id != selected.opportunity_id), maxlen=self.capacity)
            return selected

    def mark_spoken(self, source_id: str) -> None:
        key = str(source_id or "unknown")[:160]
        with self._lock:
            self._last_spoken_by_source[key] = monotonic()
            if len(self._last_spoken_by_source) > 512:
                # Values are monotonic timestamps, so retaining the newest is deterministic.
                latest = sorted(self._last_spoken_by_source.items(), key=lambda pair: pair[1], reverse=True)[:256]
                self._last_spoken_by_source = dict(latest)

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._prune_locked()
            pending = sorted(
                self._pending,
                key=lambda item: (int(item.priority), -float(item.relevance), item.created_monotonic),
            )[:12]
            return {
                "version": self.VERSION,
                "floor_owner": self._floor_owner,
                "pending": [item.to_dict() for item in pending],
                "pending_count": len(self._pending),
                "stats": dict(self._stats),
                "policy": "creator floor precedence is deterministic; model scores may rank opportunities but cannot seize the floor",
            }
