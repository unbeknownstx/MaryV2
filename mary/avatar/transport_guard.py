"""Avatar transport correctness helpers.

External avatar bridges such as VTube Studio often multiplex mouth updates,
expressions and hotkeys over one request/reply WebSocket. This guard serializes
request/reply pairs so concurrent presentation paths cannot consume each other's
responses. It does not decide expressions or Mary state.
"""
from __future__ import annotations

from threading import RLock
from typing import Any, Callable
import math


class SerializedRequestReplyTransport:
    VERSION = "1"

    def __init__(self, request_reply: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._request_reply = request_reply
        self._lock = RLock()
        self._sequence = 0

    def call(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._sequence += 1
            response = self._request_reply(dict(payload))
            if not isinstance(response, dict):
                raise TypeError("avatar transport response must be a mapping")
            return response

    @property
    def sequence(self) -> int:
        return self._sequence


def normalized_mouth_level(*, rms: float, peak: float, gain: float = 1.0) -> float:
    """Audio-driven mouth openness that preserves whisper-vs-loudness contrast."""
    rms_value = max(0.0, float(rms))
    peak_value = max(0.0, float(peak))
    floor = 0.05
    reference = max(peak_value, floor)
    ratio = rms_value / reference if reference else 0.0
    shaped = math.sqrt(max(0.0, ratio)) * max(0.0, float(gain))
    return max(0.0, min(1.0, shaped))
