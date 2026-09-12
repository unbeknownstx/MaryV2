"""Core-owned runtime performance profiles.

Profiles tune replaceable realtime resources; they never switch Mary identity,
personality, memory, relationship state, or authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class RuntimePerformanceProfile:
    name: str
    vad_confirm_ms: int
    tts_chunk_chars: int
    perception_hz: float
    avatar_hz: int
    local_keepalive_seconds: int
    background_consolidation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_PROFILES = {
    "light": RuntimePerformanceProfile(
        "light", 260, 220, 0.5, 20, 30, "low"
    ),
    "balanced": RuntimePerformanceProfile(
        "balanced", 180, 150, 1.0, 30, 180, "normal"
    ),
    "performance": RuntimePerformanceProfile(
        "performance", 120, 96, 2.0, 60, 900, "normal"
    ),
}


class RuntimePerformanceProfiles:
    VERSION = "13.6"

    def __init__(self, default: str = "balanced") -> None:
        self._lock = RLock()
        self._name = default if default in _PROFILES else "balanced"

    def set(self, name: str) -> RuntimePerformanceProfile:
        value = str(name or "").strip().lower()
        if value not in _PROFILES:
            raise ValueError(f"unknown performance profile: {value}")
        with self._lock:
            self._name = value
            return _PROFILES[value]

    @property
    def current(self) -> RuntimePerformanceProfile:
        with self._lock:
            return _PROFILES[self._name]

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "version": self.VERSION,
                "current": _PROFILES[self._name].to_dict(),
                "available": {
                    name: profile.to_dict()
                    for name, profile in _PROFILES.items()
                },
                "authority": "mary_core_runtime_policy",
                "identity_switch": False,
            }
