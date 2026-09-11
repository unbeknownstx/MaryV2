"""Idempotent retry ledger for replaceable capability invocations.

The ledger is process-local orchestration state. It never turns node output
into identity, memory, or creator truth. It only prevents duplicate execution
within an explicitly reused idempotency key and centralizes bounded retry
policy for transient capability failures.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any
import hashlib
import json
import uuid


_TRANSIENT = {
    "timeout",
    "busy",
    "temporarily_unavailable",
    "transport_error",
    "rate_limited",
}


@dataclass
class CapabilityInvocation:
    capability: str
    idempotency_key: str
    args_digest: str
    invocation_id: str = field(
        default_factory=lambda: f"invocation_{uuid.uuid4().hex[:12]}"
    )
    attempts: int = 0
    max_attempts: int = 3
    status: str = "pending"
    last_error_kind: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CapabilityInvocationLedger:
    """Bounded process-local idempotency and retry coordination."""

    VERSION = "13.6"

    def __init__(self, *, capacity: int = 512) -> None:
        self._lock = RLock()
        self._capacity = max(64, min(4096, int(capacity)))
        self._items: OrderedDict[str, CapabilityInvocation] = OrderedDict()

    @staticmethod
    def digest_args(args: dict[str, Any] | None) -> str:
        encoded = json.dumps(
            dict(args or {}),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]

    def begin(
        self,
        capability: str,
        *,
        args: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        max_attempts: int = 3,
    ) -> tuple[CapabilityInvocation, bool]:
        name = str(capability or "").strip().lower()
        if not name:
            raise ValueError("capability is required")
        digest = self.digest_args(args)
        # Automatic keys are useful for a single bounded orchestration scope.
        # Callers performing repeated legitimate actions should provide their
        # own request/turn-scoped key rather than treating the ledger as history.
        key = str(idempotency_key or f"{name}:{digest}").strip()[:180]
        with self._lock:
            existing = self._items.get(key)
            if existing is not None:
                self._items.move_to_end(key)
                return existing, False
            item = CapabilityInvocation(
                name,
                key,
                digest,
                max_attempts=max(1, min(8, int(max_attempts))),
            )
            self._items[key] = item
            while len(self._items) > self._capacity:
                self._items.popitem(last=False)
            return item, True

    def start_attempt(self, key: str) -> CapabilityInvocation:
        with self._lock:
            item = self._items[str(key)]
            if item.status == "completed":
                return item
            item.attempts += 1
            item.status = "running"
            return item

    def fail(self, key: str, error_kind: str) -> bool:
        """Record a failure and return whether one bounded retry is allowed."""
        kind = str(error_kind or "unknown").strip().lower()
        with self._lock:
            item = self._items[str(key)]
            item.last_error_kind = kind[:64]
            retry = kind in _TRANSIENT and item.attempts < item.max_attempts
            item.status = "retryable" if retry else "failed"
            return retry

    def complete(self, key: str) -> CapabilityInvocation:
        with self._lock:
            item = self._items[str(key)]
            item.status = "completed"
            return item

    def status(self) -> dict[str, Any]:
        with self._lock:
            items = list(self._items.values())[-24:]
            return {
                "version": self.VERSION,
                "count": len(self._items),
                "recent": [item.to_dict() for item in items],
                "policy": (
                    "process-local idempotency/retry coordination only; capability "
                    "results remain non-authoritative until canonical Mary interprets them"
                ),
            }
