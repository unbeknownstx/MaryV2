"""Private server-side Voice Lab for MaryV2 13.0.

Voice IDs never need to be embedded in the mobile frontend.  The authenticated
mobile client refers to server-side profiles by generated profile IDs/labels.
"""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from typing import Any
import uuid

from mary.runtime.persistence import atomic_write_json, load_json_recovering


BASELINE = {
    "stability": 0.50,
    "similarity": 0.75,
    "style": 0.0,
    "speed": 1.0,
    "speaker_boost": False,
}


class VoiceLabStore:
    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.profiles: list[dict[str, Any]] = []
        self.selected_profile_id: str | None = None
        self.load()
        self._seed_environment_voice()

    @staticmethod
    def _clean_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
        raw = dict(settings or {})
        def flt(name: str, default: float, lo: float, hi: float) -> float:
            try:
                value = float(raw.get(name, default))
            except (TypeError, ValueError):
                value = default
            return round(max(lo, min(hi, value)), 3)
        return {
            "stability": flt("stability", BASELINE["stability"], 0.0, 1.0),
            "similarity": flt("similarity", BASELINE["similarity"], 0.0, 1.0),
            "style": flt("style", BASELINE["style"], 0.0, 1.0),
            "speed": flt("speed", BASELINE["speed"], 0.7, 1.2),
            "speaker_boost": bool(raw.get("speaker_boost", BASELINE["speaker_boost"])),
        }

    def _seed_environment_voice(self) -> None:
        if self.profiles:
            return
        voice_id = os.getenv("MARY_ELEVENLABS_VOICE_ID", "").strip()
        if not voice_id:
            return
        settings = self._clean_settings({
            "stability": os.getenv("MARY_TTS_STABILITY", BASELINE["stability"]),
            "similarity": os.getenv("MARY_TTS_SIMILARITY", BASELINE["similarity"]),
            "style": os.getenv("MARY_TTS_STYLE", BASELINE["style"]),
            "speed": os.getenv("MARY_TTS_SPEED", BASELINE["speed"]),
            "speaker_boost": str(os.getenv("MARY_TTS_SPEAKER_BOOST", "false")).lower() in {"1","true","yes","on"},
        })
        item = self.save_profile("Mary · Environment", voice_id, settings=settings, select=True)
        self.selected_profile_id = item["id"]

    def load(self) -> bool:
        payload, _ = load_json_recovering(self.path, backup_generations=3, restore_primary=False)
        if payload is None:
            return True
        if not isinstance(payload, dict):
            return False
        profiles = payload.get("profiles", [])
        self.profiles = [dict(x) for x in profiles if isinstance(x, dict) and x.get("voice_id")][-12:]
        selected = str(payload.get("selected_profile_id") or "").strip()
        self.selected_profile_id = selected or None
        return True

    def save(self) -> bool:
        return atomic_write_json(self.path, {
            "schema_version": self.SCHEMA_VERSION,
            "selected_profile_id": self.selected_profile_id,
            "profiles": self.profiles[-12:],
        }, backup_generations=3, indent=2)

    def save_profile(self, label: str, voice_id: str, *, settings: dict[str, Any] | None = None, profile_id: str | None = None, select: bool = False) -> dict[str, Any]:
        label = str(label or "Mary Voice").strip()[:80] or "Mary Voice"
        voice_id = str(voice_id or "").strip()
        if not voice_id or len(voice_id) > 200:
            raise ValueError("A valid ElevenLabs voice ID is required.")
        pid = str(profile_id or f"voice_{uuid.uuid4().hex[:12]}").strip()
        now = datetime.now().isoformat()
        existing = next((x for x in self.profiles if x.get("id") == pid), None)
        item = existing if existing is not None else {"id": pid, "created_at": now}
        item.update({
            "label": label,
            "voice_id": voice_id,
            "settings": self._clean_settings(settings),
            "updated_at": now,
        })
        if existing is None:
            self.profiles.append(item)
            self.profiles = self.profiles[-12:]
        if select or self.selected_profile_id is None:
            self.selected_profile_id = pid
        self.save()
        return dict(item)

    def select(self, profile_id: str) -> dict[str, Any]:
        item = self.get(profile_id)
        if item is None:
            raise KeyError("Voice profile not found.")
        self.selected_profile_id = str(item["id"])
        self.save()
        return dict(item)

    def delete(self, profile_id: str) -> bool:
        before = len(self.profiles)
        self.profiles = [x for x in self.profiles if x.get("id") != profile_id]
        changed = len(self.profiles) != before
        if changed and self.selected_profile_id == profile_id:
            self.selected_profile_id = self.profiles[0]["id"] if self.profiles else None
        if changed:
            self.save()
        return changed

    def get(self, profile_id: str | None) -> dict[str, Any] | None:
        return next((dict(x) for x in self.profiles if x.get("id") == profile_id), None)

    def selected(self) -> dict[str, Any] | None:
        return self.get(self.selected_profile_id)

    def public_state(self) -> dict[str, Any]:
        # Voice IDs stay server-side even though this endpoint is authenticated.
        return {
            "selected_profile_id": self.selected_profile_id,
            "baseline": dict(BASELINE),
            "dynamic_delivery": str(os.getenv("MARY_TTS_DYNAMIC_DELIVERY", "false")).lower() in {"1","true","yes","on"},
            "performance_delivery": str(os.getenv("MARY_TTS_PERFORMANCE_DELIVERY", "true")).lower() not in {"0","false","no","off"},
            "profiles": [
                {
                    "id": x.get("id"),
                    "label": x.get("label"),
                    "settings": dict(x.get("settings", {}) or {}),
                    "selected": x.get("id") == self.selected_profile_id,
                }
                for x in self.profiles
            ],
        }
