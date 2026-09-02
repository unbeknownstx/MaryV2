"""Single-floor speech arbitration for MaryV2.

The arbiter is presentation/realtime coordination only.  It does not generate
text or audio.  It decides whether a proposed speech item may play now, should
queue, should interrupt the current item, or should be dropped as stale/noisy.
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

from mary.runtime.turn_observability import record_turn_stage


class SpeechDisposition(str, Enum):
    PLAY = "play"
    QUEUE = "queue"
    DROP = "drop"
    INTERRUPT = "interrupt"


@dataclass(frozen=True)
class SpeechRequest:
    text: str
    source: str = "mary"
    target: str = "creator"
    priority: int = 50
    interruptible: bool = True
    can_interrupt: bool = False
    ttl_seconds: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"speech_{uuid.uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_monotonic: float = field(default_factory=monotonic, compare=False, repr=False)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("created_monotonic", None)
        payload["text"] = " ".join(str(self.text).split())[:1200]
        payload["metadata"] = {
            str(k)[:60]: str(v)[:160]
            for k, v in list(dict(self.metadata or {}).items())[:12]
            if str(k).casefold() not in {"token", "authorization", "api_key", "secret", "password"}
        }
        return payload


@dataclass(frozen=True)
class SpeechArbitration:
    disposition: SpeechDisposition
    request_id: str
    reason: str
    interrupted_request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["disposition"] = self.disposition.value
        return result


class SpeechOutputArbiter:
    VERSION = "1"

    def __init__(self, *, queue_capacity: int = 12) -> None:
        self._lock = RLock()
        self.queue_capacity = max(2, min(64, int(queue_capacity)))
        self._active: SpeechRequest | None = None
        self._queue: deque[SpeechRequest] = deque(maxlen=self.queue_capacity)
        self._stats = {
            "played": 0,
            "queued": 0,
            "dropped": 0,
            "interrupts": 0,
            "completed": 0,
        }

    @staticmethod
    def _traced(result: SpeechArbitration) -> SpeechArbitration:
        record_turn_stage(
            "speech_arbitration",
            status="success",
            elapsed_ms=0.0,
            outcome=result.disposition.value,
            result_ids={"speech_request_id": result.request_id},
        )
        return result

    @staticmethod
    def _expired(request: SpeechRequest) -> bool:
        return monotonic() - request.created_monotonic > max(1.0, float(request.ttl_seconds))

    def _prune_locked(self) -> None:
        kept = deque(maxlen=self.queue_capacity)
        for item in self._queue:
            if self._expired(item):
                self._stats["dropped"] += 1
            else:
                kept.append(item)
        self._queue = kept

    def request(self, request: SpeechRequest) -> SpeechArbitration:
        if not " ".join(str(request.text or "").split()):
            self._stats["dropped"] += 1
            return self._traced(SpeechArbitration(SpeechDisposition.DROP, request.id, "empty speech request"))
        with self._lock:
            self._prune_locked()
            active = self._active
            if active is None:
                self._active = request
                self._stats["played"] += 1
                return self._traced(SpeechArbitration(SpeechDisposition.PLAY, request.id, "speech floor was free"))

            # Lower number = higher priority, mirroring AttentionBus.
            higher_priority = int(request.priority) < int(active.priority)
            if request.can_interrupt and active.interruptible and higher_priority:
                old_id = active.id
                self._active = request
                self._stats["interrupts"] += 1
                self._stats["played"] += 1
                return self._traced(SpeechArbitration(
                    SpeechDisposition.INTERRUPT,
                    request.id,
                    "higher-priority interruptible speech took the floor",
                    interrupted_request_id=old_id,
                ))

            if len(self._queue) >= self.queue_capacity:
                # Prefer the more important request rather than blindly
                # retaining an old low-priority queue tail.
                worst = max(self._queue, key=lambda item: int(item.priority), default=None)
                if worst is not None and int(request.priority) < int(worst.priority):
                    self._queue.remove(worst)
                    self._stats["dropped"] += 1
                else:
                    self._stats["dropped"] += 1
                    return self._traced(SpeechArbitration(SpeechDisposition.DROP, request.id, "speech queue full"))

            self._queue.append(request)
            self._queue = deque(sorted(self._queue, key=lambda item: (int(item.priority), item.created_monotonic)), maxlen=self.queue_capacity)
            self._stats["queued"] += 1
            return self._traced(SpeechArbitration(SpeechDisposition.QUEUE, request.id, "another voice item owns the floor"))

    def finish_active(self, request_id: str | None = None) -> SpeechRequest | None:
        with self._lock:
            if self._active is not None and request_id and self._active.id != str(request_id):
                return self._active
            if self._active is not None:
                self._stats["completed"] += 1
            self._active = None
            self._prune_locked()
            while self._queue:
                next_item = self._queue.popleft()
                if self._expired(next_item):
                    self._stats["dropped"] += 1
                    continue
                self._active = next_item
                self._stats["played"] += 1
                return next_item
            return None

    def interrupt_active(self, *, reason: str = "barge_in") -> SpeechRequest | None:
        del reason  # reserved for future trace metadata
        with self._lock:
            active = self._active
            if active is not None:
                self._stats["interrupts"] += 1
                self._active = None
            return active

    def abandon(self, request_id: str) -> bool:
        target = str(request_id)
        with self._lock:
            if self._active is not None and self._active.id == target:
                self._active = None
                self._stats["dropped"] += 1
                return True
            before = len(self._queue)
            self._queue = deque((item for item in self._queue if item.id != target), maxlen=self.queue_capacity)
            if len(self._queue) != before:
                self._stats["dropped"] += 1
                return True
            return False

    @property
    def active(self) -> SpeechRequest | None:
        with self._lock:
            return self._active

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._prune_locked()
            return {
                "version": self.VERSION,
                "active": self._active.to_dict() if self._active else None,
                "queue": [item.to_dict() for item in list(self._queue)[:8]],
                "queue_depth": len(self._queue),
                "stats": dict(self._stats),
                "policy": "one Mary speech floor; queue/drop/interrupt are realtime presentation decisions only",
            }
