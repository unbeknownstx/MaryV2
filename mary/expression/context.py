"""Ephemeral social/performance context for one canonical Mary.

This is not a persona switch.  Mary remains the same authored character; the
context only changes how much performance energy/initiative is appropriate and
whether the current surface should be treated as potentially public.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PerformanceContext:
    mode: str
    audience: str
    public: bool
    initiative_gain: float
    expressiveness_gain: float
    silence_gain: float
    privacy_rule: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CONTEXTS: dict[str, PerformanceContext] = {
    "private": PerformanceContext(
        "private", "creator", False, 1.0, 1.0, 1.0,
        "private creator context may be used when relevant",
    ),
    "casual": PerformanceContext(
        "casual", "creator", False, 1.06, 1.06, 0.94,
        "private creator context may be used when relevant",
    ),
    "focus": PerformanceContext(
        "focus", "creator", False, 0.35, 0.78, 1.40,
        "minimize unsolicited interruption while focus is active",
    ),
    "stream": PerformanceContext(
        "stream", "public_audience", True, 1.15, 1.16, 0.86,
        "do not surface private creator profile, private memories, or relationship details to the audience",
    ),
    "performance": PerformanceContext(
        "performance", "audience", True, 1.12, 1.20, 0.88,
        "perform outwardly without exposing private creator/profile material",
    ),
}


class PerformanceContextManager:
    """Tiny process-local context switch; never identity/memory authority."""

    def __init__(self, mode: str = "private") -> None:
        self._mode = self._normalize(mode)

    @staticmethod
    def _normalize(mode: Any) -> str:
        value = str(mode or "private").strip().lower()
        return value if value in _CONTEXTS else "private"

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def current(self) -> PerformanceContext:
        return _CONTEXTS[self._mode]

    def set_mode(self, mode: str) -> dict[str, Any]:
        self._mode = self._normalize(mode)
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            **self.current.to_dict(),
            "available_modes": list(_CONTEXTS),
            "authority": "ephemeral_presentation_context",
            "identity_switch": False,
            "persistence": "none",
        }
