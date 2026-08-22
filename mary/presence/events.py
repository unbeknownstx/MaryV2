"""Typed live-context events for Mary Presence."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

class PresenceEventType(str, Enum):
    CREATOR_SPEECH = "creator_speech"
    TWITCH_CHAT = "twitch_chat"
    TWITCH_MENTION = "twitch_mention"
    OBS_SCENE = "obs_scene"
    FOREGROUND_APP = "foreground_app"
    VISUAL_OBSERVATION = "visual_observation"
    MEDIA_CHANGED = "media_changed"
    PROJECT_CHANGED = "project_changed"
    IDLE_TICK = "idle_tick"
    SYSTEM = "system"

@dataclass(frozen=True)
class PresenceEvent:
    event_type: PresenceEventType
    summary: str
    source: str
    importance: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id: str = field(default_factory=lambda: f"presence_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self); payload["event_type"] = self.event_type.value; return payload
