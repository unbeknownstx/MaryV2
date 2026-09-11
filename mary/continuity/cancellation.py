"""Provider-neutral cooperative generation cancellation contract."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Event, RLock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class CancellationHandle:
    id: str
    correlation_id: str


class GenerationCancellationRegistry:
    """Cancellation intent shared across providers that opt into cooperative checks.

    Registering a token never implies that a provider can cancel an already-sent
    remote HTTP request. Providers advertise/implement support independently.
    """

    VERSION = 1

    def __init__(self) -> None:
        self._lock = RLock()
        self._tokens: dict[str, Event] = {}
        self._correlation: dict[str, str] = {}

    def create(self, *, correlation_id: str = "") -> CancellationHandle:
        handle = CancellationHandle(
            id=f"cancel_{uuid4().hex}",
            correlation_id=str(correlation_id).strip()[:160],
        )
        with self._lock:
            self._tokens[handle.id] = Event()
            if handle.correlation_id:
                self._correlation[handle.correlation_id] = handle.id
        return handle

    def cancel(self, handle_id: str) -> bool:
        with self._lock:
            token = self._tokens.get(handle_id)
            if token is None:
                return False
            token.set()
            return True

    def cancel_correlation(self, correlation_id: str) -> bool:
        with self._lock:
            handle_id = self._correlation.get(str(correlation_id))
        return bool(handle_id and self.cancel(handle_id))

    def cancelled(self, handle_id: str) -> bool:
        with self._lock:
            token = self._tokens.get(handle_id)
            return bool(token and token.is_set())

    def complete(self, handle_id: str) -> None:
        with self._lock:
            self._tokens.pop(handle_id, None)
            stale = [key for key, value in self._correlation.items() if value == handle_id]
            for key in stale:
                self._correlation.pop(key, None)

    def status(self) -> dict[str, Any]:
        with self._lock:
            active = len(self._tokens)
            cancelled = sum(1 for token in self._tokens.values() if token.is_set())
        return {
            "version": self.VERSION,
            "active": active,
            "cancelled": cancelled,
            "policy": "cooperative provider contract; capability does not imply provider support",
        }
