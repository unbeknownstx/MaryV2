"""Deterministic fake capability node for adapter development and tests."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class SimulatedCapabilityResult:
    capability: str
    ok: bool
    result: dict[str, Any] = field(default_factory=dict)
    error_kind: str | None = None


class CapabilitySimulator:
    """Small fake node; never registers as Mary or owns canonical state."""

    VERSION = "13.6"

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
        self._fail_next: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    def register(
        self,
        capability: str,
        handler: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        name = str(capability or "").strip().lower()
        if not name:
            raise ValueError("capability is required")
        self._handlers[name] = handler

    def fail_next(
        self,
        capability: str,
        error_kind: str = "transport_error",
    ) -> None:
        self._fail_next[str(capability).strip().lower()] = str(error_kind).strip().lower()

    def invoke(
        self,
        capability: str,
        args: dict[str, Any] | None = None,
    ) -> SimulatedCapabilityResult:
        name = str(capability or "").strip().lower()
        payload = dict(args or {})
        self.calls.append({"capability": name, "args": payload})
        if name in self._fail_next:
            kind = self._fail_next.pop(name)
            return SimulatedCapabilityResult(name, False, error_kind=kind)
        handler = self._handlers.get(name)
        if handler is None:
            return SimulatedCapabilityResult(name, False, error_kind="unsupported")
        try:
            return SimulatedCapabilityResult(
                name,
                True,
                result=dict(handler(payload) or {}),
            )
        except Exception as exc:
            return SimulatedCapabilityResult(
                name,
                False,
                error_kind=f"handler_error:{type(exc).__name__}",
            )

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "capabilities": sorted(self._handlers),
            "calls": len(self.calls),
            "policy": "development/test fake capability node only; never canonical Mary",
        }
