"""Sensor-worker extension for the existing bounded capability-node agent."""
from __future__ import annotations

from typing import Any

from mary.desktop.device_node import DesktopCapabilityNodeAgent

from .sensors import (
    AUDIO_TRANSCRIBE_CAPABILITY,
    SCREEN_CAPTURE_CAPABILITY,
    SENSOR_CAPABILITIES,
    execute_audio_transcribe,
    execute_screen_capture,
)


class SensorCapabilityNodeAgent(DesktopCapabilityNodeAgent):
    """Adds only explicitly typed sensor executors to the existing node agent."""

    def _handle_task(self, task: dict[str, Any]) -> dict[str, Any]:
        capability = str(task.get("capability") or "").strip().lower()
        if capability not in SENSOR_CAPABILITIES:
            return super()._handle_task(task)

        task_id = str(task.get("task_id") or "")
        self._last_task = {"task_id": task_id, "capability": capability, "status": "received"}
        if not self.permissions.is_allowed(capability):
            result = self.gateway.complete_capability_task(
                task_id,
                status="rejected",
                error=f"Local device permission does not allow {capability}.",
            )
            self._last_task["status"] = "rejected"
            return result

        try:
            args = dict(task.get("args") or {})
            if capability == AUDIO_TRANSCRIBE_CAPABILITY:
                result_payload = execute_audio_transcribe(args)
            elif capability == SCREEN_CAPTURE_CAPABILITY:
                result_payload = execute_screen_capture(args)
            else:  # defensive; SENSOR_CAPABILITIES is closed above
                raise ValueError(f"No bounded sensor executor exists for {capability}.")
            result = self.gateway.complete_capability_task(
                task_id,
                status="completed",
                result=result_payload,
            )
            self._last_task["status"] = "completed"
            self._last_error = ""
            return result
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:500]
            self._last_error = error
            self._last_task["status"] = "failed"
            try:
                return self.gateway.complete_capability_task(task_id, status="failed", error=error)
            except Exception:
                return {"ok": False, "error": error}
