"""Small transport-neutral Mary Protocol v1 data contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

_ALLOWED_MODES = {"quick", "adaptive", "engaged", "deep"}


@dataclass(frozen=True)
class TurnRequest:
    text: str
    conversation_id: str = field(default_factory=lambda: f"conversation_{uuid4().hex}")
    device_id: str = "unknown-device"
    requested_mode: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TurnRequest":
        if not isinstance(payload, dict):
            raise ValueError("Turn request must be a JSON object.")
        text = str(payload.get("text") or "").strip()
        if not text:
            raise ValueError("text is required.")
        if len(text) > 32_000:
            raise ValueError("text exceeds the 32,000 character protocol limit.")
        conversation_id = str(payload.get("conversation_id") or f"conversation_{uuid4().hex}").strip()
        device_id = str(payload.get("device_id") or "unknown-device").strip()
        mode_raw = payload.get("requested_mode")
        mode = str(mode_raw).strip().lower() if mode_raw is not None else None
        if mode and mode not in _ALLOWED_MODES:
            raise ValueError(f"requested_mode must be one of: {', '.join(sorted(_ALLOWED_MODES))}.")
        return cls(
            text=text,
            conversation_id=conversation_id[:160],
            device_id=device_id[:160],
            requested_mode=mode,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TurnResponse:
    response: str
    conversation_id: str
    turn_id: str
    effective_mode: str
    provenance: dict[str, Any] = field(default_factory=dict)
    state_changes: dict[str, Any] = field(default_factory=dict)
    conversation_state: dict[str, Any] = field(default_factory=dict)
    display_hints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
