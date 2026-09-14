"""Capability-node-only resource reporting wrapper for Mary Protocol.

The wrapped gateway remains the authority/transport owner. This adapter only
adds a tiny, cached `_resource` envelope to successful device-task completions.
It never changes node permissions, task status, Mary state, or ordinary client
traffic. Resource probes refresh asynchronously so hardware observation never
sits on the model/tool completion critical path.
"""
from __future__ import annotations

from threading import RLock, Thread
from time import monotonic
from typing import Any, Callable

from mary.distributed.resource_probe import observe_live_resources
from mary.distributed.resource_telemetry import telemetry_from_observation


class ResourceReportingGateway:
    """Delegate a node gateway while adding bounded completion telemetry."""

    VERSION = "13.53"

    def __init__(
        self,
        gateway: Any,
        *,
        sample_seconds: float = 30.0,
        observer: Callable[[], Any] = observe_live_resources,
    ) -> None:
        self._gateway = gateway
        self._sample_seconds = max(5.0, min(90.0, float(sample_seconds)))
        self._observer = observer
        self._lock = RLock()
        self._last_sample_at = -1.0
        self._last_payload: dict[str, Any] = {}
        self._refreshing = False
        self._start_refresh()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._gateway, name)

    def _start_refresh(self) -> None:
        with self._lock:
            if self._refreshing:
                return
            self._refreshing = True
        thread = Thread(
            target=self._refresh_resource_cache,
            name="MaryNodeResourceProbe",
            daemon=True,
        )
        thread.start()

    def _refresh_resource_cache(self) -> None:
        try:
            payload = dict(telemetry_from_observation(self._observer()) or {})
        except Exception:
            payload = {}
        measured_at = monotonic()
        with self._lock:
            self._last_payload = payload
            self._last_sample_at = measured_at
            self._refreshing = False

    def _resource_payload(self) -> dict[str, Any]:
        now = monotonic()
        should_refresh = False
        with self._lock:
            fresh = (
                self._last_sample_at >= 0.0
                and now - self._last_sample_at < self._sample_seconds
            )
            if fresh:
                return dict(self._last_payload)
            should_refresh = not self._refreshing
        if should_refresh:
            self._start_refresh()
        # Never extend stale hardware evidence just because a refresh is slow or
        # unavailable. Core's own telemetry TTL can then expire old pressure.
        return {}

    def complete_capability_task(
        self,
        task_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> dict[str, Any]:
        values = dict(result or {})
        if str(status or "").strip().lower() == "completed" and "_resource" not in values:
            # NodeTaskCompletionRequest keeps an eight-field result budget. Until
            # `_resource` has a dedicated top-level protocol slot, preserve every
            # legal business result rather than making completion fail.
            if len(values) < 8:
                resource = self._resource_payload()
                if resource:
                    values["_resource"] = resource
        return self._gateway.complete_capability_task(
            task_id,
            status=status,
            result=values,
            error=error,
        )
