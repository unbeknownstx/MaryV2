"""Priority attention queue for MaryV2 realtime inputs.

The queue is deliberately *not* a memory store and it does not grant authority
based on where text came from.  It solves a different problem: when several
things happen around Mary at once, which event deserves processing first?

This is inspired by realtime character systems that serialize microphone,
vision, proactive, and tool events through one bounded queue.  Mary's version
keeps provenance and authority separate from priority so an urgent visual or
system event can never masquerade as creator-authored truth.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import deque
import heapq
from threading import RLock
from typing import Any
import uuid

from mary.runtime.turn_observability import record_turn_stage
from .decision_trace import RealtimeDecisionTrace


class AttentionSource(str, Enum):
    CREATOR_SPEECH = "creator_speech"
    CREATOR_TEXT = "creator_text"
    SYSTEM = "system"
    TOOL = "tool"
    NODE = "node"
    VISUAL = "visual"
    MEMORY = "memory"
    CURIOSITY = "curiosity"
    SCHEDULE = "schedule"
    BACKGROUND = "background"


class AttentionDisposition(str, Enum):
    """What the attention layer wants cognition to do with an observation."""

    REACT = "react"
    NOTE = "note"
    DROP = "drop"


@dataclass(frozen=True)
class AttentionJudgment:
    disposition: AttentionDisposition
    score: float
    reason: str
    addressed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "score": round(max(0.0, min(1.0, float(self.score))), 3),
            "reason": str(self.reason)[:200],
            "addressed": bool(self.addressed),
        }


@dataclass
class PeripheralNote:
    note_id: str
    source: AttentionSource
    summary: str
    importance: float
    metadata: dict[str, Any]
    created_at: str
    dedupe_key: str
    times_seen: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "note_id": self.note_id,
            "source": self.source.value,
            "summary": self.summary[:600],
            "importance": round(max(0.0, min(1.0, float(self.importance))), 3),
            "metadata": _safe_metadata(self.metadata),
            "created_at": self.created_at,
            "times_seen": max(1, int(self.times_seen)),
        }


_DEFAULT_PRIORITY: dict[AttentionSource, int] = {
    AttentionSource.CREATOR_SPEECH: 0,
    AttentionSource.CREATOR_TEXT: 5,
    AttentionSource.SYSTEM: 18,
    AttentionSource.TOOL: 22,
    AttentionSource.NODE: 28,
    AttentionSource.VISUAL: 35,
    AttentionSource.MEMORY: 45,
    AttentionSource.CURIOSITY: 50,
    AttentionSource.SCHEDULE: 58,
    AttentionSource.BACKGROUND: 70,
}

_SENSITIVE_METADATA_KEYS = {
    "audio", "audio_bytes", "raw_audio", "image", "frame", "screenshot",
    "raw_image", "pixels", "base64", "prompt", "system_prompt", "api_key",
    "token", "authorization", "password", "secret",
}


def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in dict(metadata or {}).items():
        normalized = str(key).strip().casefold()
        if normalized in _SENSITIVE_METADATA_KEYS or any(
            marker in normalized for marker in ("api_key", "password", "secret", "authorization")
        ):
            continue
        if isinstance(value, (bytes, bytearray, memoryview)):
            continue
        # Keep status payloads bounded and JSON-friendly without importing the
        # runtime's serialization layer here.
        if isinstance(value, str):
            output[str(key)[:80]] = value[:500]
        elif isinstance(value, (bool, int, float)) or value is None:
            output[str(key)[:80]] = value
        elif isinstance(value, (list, tuple)):
            output[str(key)[:80]] = [str(item)[:120] for item in list(value)[:12]]
        elif isinstance(value, dict):
            output[str(key)[:80]] = {
                str(k)[:60]: str(v)[:160]
                for k, v in list(value.items())[:12]
                if str(k).casefold() not in _SENSITIVE_METADATA_KEYS
            }
        else:
            output[str(key)[:80]] = str(value)[:200]
    return output


@dataclass(frozen=True)
class AttentionEvent:
    source: AttentionSource
    summary: str
    priority: int
    importance: float = 0.5
    interruptible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id: str = field(default_factory=lambda: f"attention_{uuid.uuid4().hex[:12]}")
    sequence: int = 0
    dedupe_key: str | None = None
    execution_status: str = "not_executed"

    @property
    def attention_id(self) -> str:
        return self.id

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source"] = self.source.value
        payload["attention_id"] = self.id
        return payload


class AttentionBus:
    """Thread-safe bounded priority queue plus small recent-event trace.

    Lower numeric priority wins. FIFO ordering is preserved on ties through a
    monotonic sequence counter. The queue is ephemeral by design.
    """

    VERSION = "13.1"

    def __init__(self, *, max_pending: int = 256, recent_limit: int = 128, decision_trace: RealtimeDecisionTrace | None = None) -> None:
        self.max_pending = max(16, min(4096, int(max_pending)))
        self.recent_limit = max(16, min(1024, int(recent_limit)))
        self._lock = RLock()
        self._heap: list[tuple[int, int, AttentionEvent]] = []
        self._recent: list[AttentionEvent] = []
        self._sequence = 0
        self._published = 0
        self._claimed = 0
        self._dropped = 0
        self._deduplicated = 0
        self._triage = {"react": 0, "note": 0, "drop": 0}
        self._peripheral: deque[PeripheralNote] = deque(maxlen=max(16, min(256, self.recent_limit)))
        self._paused = False
        self._pause_reason: str | None = None
        self.decision_trace = decision_trace

    def judge(
        self,
        source: AttentionSource | str,
        *,
        importance: float = 0.5,
        addressed: bool = False,
        noise: bool = False,
        novelty: float = 0.5,
    ) -> AttentionJudgment:
        """Pure-ish deterministic gate inspired by live character attention systems.

        Addressed input is deterministic: Mary should not roll dice to decide whether
        a person who directly addressed her deserves a turn.  Unaddressed ambient
        observations may be reacted to, merely noted for the next turn, or dropped.
        This is attention only; it grants no authority and performs no action.
        """

        resolved = AttentionSource(str(getattr(source, "value", source)).strip().lower())
        importance_value = max(0.0, min(1.0, float(importance)))
        novelty_value = max(0.0, min(1.0, float(novelty)))
        if noise:
            judgment = AttentionJudgment(AttentionDisposition.DROP, 0.0, "explicit noise", bool(addressed))
        elif addressed or resolved in {AttentionSource.CREATOR_SPEECH, AttentionSource.CREATOR_TEXT}:
            judgment = AttentionJudgment(
                AttentionDisposition.REACT,
                max(0.82, importance_value),
                "directly addressed input bypasses probabilistic salience",
                True,
            )
        else:
            source_bias = {
                AttentionSource.SYSTEM: .16,
                AttentionSource.TOOL: .12,
                AttentionSource.NODE: .08,
                AttentionSource.VISUAL: .02,
                AttentionSource.MEMORY: .00,
                AttentionSource.CURIOSITY: .02,
                AttentionSource.SCHEDULE: -.02,
                AttentionSource.BACKGROUND: -.10,
            }.get(resolved, 0.0)
            score = max(0.0, min(1.0, importance_value * .78 + novelty_value * .22 + source_bias))
            if score >= .66:
                judgment = AttentionJudgment(AttentionDisposition.REACT, score, "ambient event is salient enough to wake cognition")
            elif score >= .30:
                judgment = AttentionJudgment(AttentionDisposition.NOTE, score, "ambient event enters peripheral awareness without a model turn")
            else:
                judgment = AttentionJudgment(AttentionDisposition.DROP, score, "ambient event is below the cognitive noise floor")
        with self._lock:
            self._triage[judgment.disposition.value] += 1
        record_turn_stage(
            "attention_judgment",
            status="success",
            elapsed_ms=0.0,
            outcome=judgment.disposition.value,
        )
        if self.decision_trace is not None:
            self.decision_trace.record(
                "attention",
                judgment.disposition.value,
                judgment.reason,
                score=judgment.score,
                source=resolved.value,
                target="cognition",
                metadata={"addressed": judgment.addressed},
            )
        return judgment

    def note_peripheral(
        self,
        source: AttentionSource | str,
        summary: str,
        *,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
    ) -> PeripheralNote:
        """Keep a small zero-LLM 'while you were busy' digest."""

        resolved = AttentionSource(str(getattr(source, "value", source)).strip().lower())
        text = " ".join(str(summary or "").split()).strip()[:600]
        if not text:
            raise ValueError("Peripheral notes require a non-empty summary.")
        key = " ".join(str(dedupe_key or f"{resolved.value}|{text.casefold()}").split())[:220]
        with self._lock:
            for item in reversed(self._peripheral):
                if item.dedupe_key == key:
                    item.times_seen += 1
                    item.importance = max(item.importance, max(0.0, min(1.0, float(importance))))
                    record_turn_stage(
                        "peripheral_awareness",
                        status="success",
                        elapsed_ms=0.0,
                        outcome="coalesced",
                        result_ids={"peripheral_note_id": item.note_id},
                    )
                    return item
            item = PeripheralNote(
                note_id=f"peripheral_{uuid.uuid4().hex[:12]}",
                source=resolved,
                summary=text,
                importance=max(0.0, min(1.0, float(importance))),
                metadata=_safe_metadata(metadata),
                created_at=datetime.now(timezone.utc).isoformat(),
                dedupe_key=key,
            )
            self._peripheral.append(item)
            record_turn_stage(
                "peripheral_awareness",
                status="success",
                elapsed_ms=0.0,
                outcome="noted",
                result_ids={"peripheral_note_id": item.note_id},
            )
            return item

    def peripheral(self, limit: int = 6) -> list[PeripheralNote]:
        with self._lock:
            ranked = sorted(
                self._peripheral,
                key=lambda item: (item.importance, item.times_seen, item.created_at),
                reverse=True,
            )
            return list(ranked[: max(1, min(16, int(limit)))])

    def claim_peripheral(self, note_ids: list[str] | tuple[str, ...]) -> int:
        ids = {str(item) for item in note_ids if str(item)}
        if not ids:
            return 0
        with self._lock:
            before = len(self._peripheral)
            self._peripheral = deque(
                (item for item in self._peripheral if item.note_id not in ids),
                maxlen=self._peripheral.maxlen,
            )
            return before - len(self._peripheral)

    def publish(
        self,
        source: AttentionSource | str,
        summary: str,
        *,
        priority: int | None = None,
        importance: float = 0.5,
        interruptible: bool = True,
        metadata: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
    ) -> AttentionEvent:
        resolved = AttentionSource(str(getattr(source, "value", source)).strip().lower())
        text = " ".join(str(summary or "").split()).strip()[:1200]
        if not text:
            raise ValueError("Attention events require a non-empty summary.")
        normalized_dedupe = " ".join(str(dedupe_key or "").split()).strip()[:160] or None
        with self._lock:
            if normalized_dedupe is not None:
                for _, _, queued in self._heap:
                    if queued.dedupe_key == normalized_dedupe:
                        self._deduplicated += 1
                        record_turn_stage(
                            "attention_publication",
                            status="skipped",
                            elapsed_ms=0.0,
                            outcome="deduplicated",
                            result_ids={"attention_id": queued.id},
                        )
                        return queued
            self._sequence += 1
            event = AttentionEvent(
                source=resolved,
                summary=text,
                priority=max(0, min(100, int(_DEFAULT_PRIORITY[resolved] if priority is None else priority))),
                importance=max(0.0, min(1.0, float(importance))),
                interruptible=bool(interruptible),
                metadata=_safe_metadata(metadata),
                sequence=self._sequence,
                dedupe_key=normalized_dedupe,
            )
            heapq.heappush(self._heap, (event.priority, event.sequence, event))
            self._recent.append(event)
            if len(self._recent) > self.recent_limit:
                del self._recent[: len(self._recent) - self.recent_limit]
            self._published += 1
            self._trim_pending_locked()
            record_turn_stage(
                "attention_publication",
                status="success",
                elapsed_ms=0.0,
                outcome="published",
                result_ids={"attention_id": event.id},
            )
            return event

    def _trim_pending_locked(self) -> None:
        while len(self._heap) > self.max_pending:
            # Drop the least urgent/newest item first. The bounded queue is
            # context only, so dropping background noise is safer than allowing
            # unbounded growth.
            worst_index = max(
                range(len(self._heap)),
                key=lambda idx: (self._heap[idx][0], self._heap[idx][1]),
            )
            self._heap.pop(worst_index)
            heapq.heapify(self._heap)
            self._dropped += 1

    def claim(self, event_id: str) -> AttentionEvent | None:
        target = str(event_id or "").strip()
        if not target:
            return None
        with self._lock:
            if self._paused:
                return None
            for index, (_, _, event) in enumerate(self._heap):
                if event.id != target:
                    continue
                self._heap.pop(index)
                heapq.heapify(self._heap)
                self._claimed += 1
                return event
        return None

    def next(self) -> AttentionEvent | None:
        with self._lock:
            if self._paused:
                return None
            if not self._heap:
                return None
            _, _, event = heapq.heappop(self._heap)
            self._claimed += 1
            return event

    def claim_context(
        self,
        *,
        limit: int = 3,
        minimum_importance: float = 0.55,
    ) -> list[AttentionEvent]:
        """Claim a few meaningful pending events for the next cognitive turn.

        This is not a truth/memory operation. Events remain labeled with their
        source and are merely offered as environment/context candidates.
        Low-value background noise stays queued until it ages out or is dropped.
        """
        limit = max(1, min(8, int(limit)))
        threshold = max(0.0, min(1.0, float(minimum_importance)))
        with self._lock:
            if self._paused:
                return []
            ordered = sorted(self._heap, key=lambda item: (item[0], item[1]))
            chosen = [item[2] for item in ordered if item[2].importance >= threshold][:limit]
            for event in chosen:
                for index, (_, _, queued) in enumerate(self._heap):
                    if queued.id == event.id:
                        self._heap.pop(index)
                        heapq.heapify(self._heap)
                        self._claimed += 1
                        break
            return chosen

    def pending(self, limit: int = 20) -> list[AttentionEvent]:
        with self._lock:
            ordered = sorted(self._heap, key=lambda item: (item[0], item[1]))
            return [item[2] for item in ordered[: max(1, min(100, int(limit)))]]

    def recent(self, limit: int = 20) -> list[AttentionEvent]:
        with self._lock:
            return list(self._recent[-max(1, min(100, int(limit))):])

    def pause(self, reason: str = "lifecycle_sleep") -> None:
        """Pause claims while retaining the bounded ephemeral queue."""
        with self._lock:
            self._paused = True
            self._pause_reason = " ".join(str(reason or "paused").split())[:120]

    def wake(self) -> None:
        """Resume claims without claiming or executing an event."""
        with self._lock:
            self._paused = False
            self._pause_reason = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            pending = self.pending(12)
            recent = self.recent(8)
            return {
                "version": self.VERSION,
                "pending": len(self._heap),
                "published": self._published,
                "claimed": self._claimed,
                "dropped": self._dropped,
                "deduplicated": self._deduplicated,
                "triage": dict(self._triage),
                "peripheral": [item.to_dict() for item in self.peripheral(6)],
                "paused": self._paused,
                "pause_reason": self._pause_reason,
                "next": pending[0].to_dict() if pending else None,
                "recent": [event.to_dict() for event in recent],
                "policy": "priority is attention only; provenance/authority remain owned by canonical Mary systems",
            }
