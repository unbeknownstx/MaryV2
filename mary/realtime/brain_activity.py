"""Read-only realtime activity projection for debugging and UI.

The projection exposes bounded causal labels and queue/floor state only. It
contains no chain-of-thought, prompt text, private memory payloads, or write
authority.
"""
from __future__ import annotations

from typing import Any


class BrainActivityProjection:
    VERSION = "13.6"

    def __init__(self, realtime: Any) -> None:
        self.realtime = realtime

    def snapshot(self) -> dict[str, Any]:
        rt = self.realtime
        trace = getattr(
            getattr(rt, "decision_trace", None),
            "snapshot",
            lambda: {},
        )()
        attention = getattr(
            getattr(rt, "attention", None),
            "snapshot",
            lambda: {},
        )()
        speaker = getattr(
            getattr(rt, "speaker_scheduler", None),
            "status",
            lambda: {},
        )()
        speech = getattr(
            getattr(rt, "speech_arbiter", None),
            "status",
            lambda: {},
        )()
        sessions = getattr(
            getattr(rt, "presentation_sessions", None),
            "status",
            lambda: {},
        )()
        return {
            "version": self.VERSION,
            "phase": getattr(getattr(rt, "_phase", None), "value", "unknown"),
            "attention": {
                "pending": attention.get(
                    "pending",
                    attention.get("pending_count"),
                ),
                "triage": attention.get("triage", {}),
                "peripheral": attention.get("peripheral", []),
            },
            "speech": {
                "floor": speaker.get("floor"),
                "active": speech.get("active"),
                "queue_depth": speech.get("queue_depth", 0),
                "presentation_session": sessions.get("active"),
            },
            "recent_decisions": list(trace.get("recent", []))[-16:],
            "policy": (
                "read-only bounded causal projection; no private reasoning or "
                "canonical authority"
            ),
        }
