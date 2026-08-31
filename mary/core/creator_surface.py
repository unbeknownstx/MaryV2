"""Process-local creator-surface lifecycle coordination.

Surface leases are deliberately ephemeral. A restarted Core has no connected
creator surfaces and therefore starts in ``SLEEPING`` while remaining healthy
and reachable.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock
from time import monotonic
from typing import Callable


class MaryLifecycleState(str, Enum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    SLEEPING = "SLEEPING"
    OFFLINE = "OFFLINE"


@dataclass
class _SurfaceLease:
    visible: bool
    foreground: bool
    expires_at: float
    last_seen: float
    last_activity: float


class CreatorSurfaceCoordinator:
    """Derive Mary's lifecycle from bounded, monotonic surface leases."""

    def __init__(
        self,
        *,
        idle_seconds: float = 60.0,
        sleep_seconds: float = 300.0,
        lease_ttl_seconds: float = 90.0,
        max_surfaces: int = 64,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._clock = clock
        self.idle_seconds = max(0.0, float(idle_seconds))
        self.sleep_seconds = max(self.idle_seconds, float(sleep_seconds))
        self.lease_ttl_seconds = max(0.05, float(lease_ttl_seconds))
        self.max_surfaces = max(1, min(256, int(max_surfaces)))
        self._surfaces: dict[str, _SurfaceLease] = {}
        self._lock = RLock()
        self._offline = False
        self._state = MaryLifecycleState.SLEEPING

    def register(
        self,
        surface_id: str,
        *,
        visible: bool = True,
        foreground: bool = True,
        lease_seconds: float | None = None,
    ) -> dict:
        with self._lock:
            now = self._clock()
            self._prune_locked(now)
            key = self._surface_id(surface_id)
            if key not in self._surfaces and len(self._surfaces) >= self.max_surfaces:
                raise RuntimeError("Creator surface lease limit reached.")
            self._surfaces[key] = _SurfaceLease(
                visible=bool(visible),
                foreground=bool(foreground),
                expires_at=now + self._lease(lease_seconds),
                last_seen=now,
                last_activity=now,
            )
            return self._status_locked(now)

    def renew(
        self,
        surface_id: str,
        *,
        visible: bool | None = None,
        foreground: bool | None = None,
        activity: bool = False,
        lease_seconds: float | None = None,
    ) -> dict:
        with self._lock:
            now = self._clock()
            self._prune_locked(now)
            key = self._surface_id(surface_id)
            surface = self._surfaces.get(key)
            if surface is None:
                raise KeyError("Creator surface has no active lease.")

            became_present = (
                (visible is True and not surface.visible)
                or (foreground is True and not surface.foreground)
            )
            if visible is not None:
                surface.visible = bool(visible)
            if foreground is not None:
                surface.foreground = bool(foreground)
            surface.expires_at = now + self._lease(lease_seconds)
            surface.last_seen = now
            if activity or became_present:
                surface.last_activity = now
            return self._status_locked(now)

    def update_visibility(
        self,
        surface_id: str,
        visible: bool,
        *,
        foreground: bool | None = None,
    ) -> dict:
        return self.renew(
            surface_id,
            visible=visible,
            foreground=foreground,
            activity=bool(visible),
        )

    def disconnect(self, surface_id: str) -> dict:
        with self._lock:
            now = self._clock()
            self._surfaces.pop(self._surface_id(surface_id), None)
            return self._status_locked(now)

    def wake(self, surface_id: str) -> dict:
        """Wake an existing lease without overriding explicit OFFLINE."""
        with self._lock:
            now = self._clock()
            self._prune_locked(now)
            if self._offline:
                raise RuntimeError(
                    "Mary is explicitly offline; use authorized online control first."
                )
            key = self._surface_id(surface_id)
            surface = self._surfaces.get(key)
            if surface is None:
                raise KeyError("Creator surface has no active lease.")
            surface.visible = True
            surface.foreground = True
            surface.last_seen = now
            surface.last_activity = now
            surface.expires_at = now + self.lease_ttl_seconds
            return self._status_locked(now)

    def set_offline(self, offline: bool = True) -> dict:
        with self._lock:
            self._offline = bool(offline)
            return self._status_locked(self._clock())

    def status(self) -> dict:
        with self._lock:
            return self._status_locked(self._clock())

    def _status_locked(self, now: float) -> dict:
        self._prune_locked(now)
        previous = self._state
        if self._offline:
            state = MaryLifecycleState.OFFLINE
        elif not self._surfaces:
            state = MaryLifecycleState.SLEEPING
        else:
            last_activity = max(item.last_activity for item in self._surfaces.values())
            elapsed = max(0.0, now - last_activity)
            if elapsed < self.idle_seconds:
                state = MaryLifecycleState.ACTIVE
            elif elapsed < self.sleep_seconds:
                state = MaryLifecycleState.IDLE
            else:
                state = MaryLifecycleState.SLEEPING
        self._state = state
        next_transition_at: float | None = None
        if self._surfaces:
            candidates = [item.expires_at for item in self._surfaces.values()]
            if not self._offline:
                last_activity = max(
                    item.last_activity for item in self._surfaces.values()
                )
                if state == MaryLifecycleState.ACTIVE:
                    candidates.append(last_activity + self.idle_seconds)
                elif state == MaryLifecycleState.IDLE:
                    candidates.append(last_activity + self.sleep_seconds)
            future = [candidate for candidate in candidates if candidate > now]
            if future:
                next_transition_at = min(future)
        return {
            "state": state.value,
            "previous_state": previous.value,
            "transitioned": state != previous,
            "offline": self._offline,
            "surface_count": len(self._surfaces),
            "visible_surface_count": sum(
                1 for item in self._surfaces.values() if item.visible
            ),
            "foreground_surface_count": sum(
                1 for item in self._surfaces.values() if item.foreground
            ),
            "idle_seconds": self.idle_seconds,
            "sleep_seconds": self.sleep_seconds,
            "lease_ttl_seconds": self.lease_ttl_seconds,
            "max_surfaces": self.max_surfaces,
            "next_transition_seconds": (
                round(max(0.0, next_transition_at - now), 3)
                if next_transition_at is not None
                else None
            ),
            "surfaces": [
                {
                    "surface_id": key,
                    "visible": item.visible,
                    "foreground": item.foreground,
                    "lease_remaining_seconds": round(
                        max(0.0, item.expires_at - now), 3
                    ),
                }
                for key, item in sorted(self._surfaces.items())
            ],
        }

    def _prune_locked(self, now: float) -> None:
        for key, item in list(self._surfaces.items()):
            if item.expires_at <= now:
                self._surfaces.pop(key, None)

    def _lease(self, requested: float | None) -> float:
        if requested is None:
            return self.lease_ttl_seconds
        return max(0.05, min(self.lease_ttl_seconds, float(requested)))

    @staticmethod
    def _surface_id(value: str) -> str:
        text = str(value or "").strip()
        if not text or len(text) > 160:
            raise ValueError("surface_id is required and must be at most 160 characters.")
        return text