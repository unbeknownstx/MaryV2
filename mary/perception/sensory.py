"""Unified permission and attention policy for Mary's eyes and ears.

Surfaces capture raw media; capability workers perceive it; Mary Core receives
only bounded observations. This module decides what a surface may sense and when
an observation deserves deeper inspection. It never stores raw pixels/audio.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SensoryPolicy:
    mode: str
    camera: bool
    screen: bool
    microphone: bool
    system_audio: bool
    photos: bool
    browser: bool

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


_POLICIES = {
    "private": SensoryPolicy("private", False, False, True, False, True, False),
    "creator": SensoryPolicy("creator", False, True, True, True, True, True),
    "performance": SensoryPolicy("performance", False, True, True, True, True, True),
    "streamer": SensoryPolicy("streamer", False, True, True, True, True, True),
}


class SensoryAttentionController:
    VERSION = "1"

    def __init__(self) -> None:
        self._last_signature: dict[str, str] = {}

    def policy(self, mode: Any) -> SensoryPolicy:
        return _POLICIES.get(str(mode or "private").strip().casefold(), _POLICIES["private"])

    def allowed(self, modality: Any, *, mode: Any, explicit_consent: bool = False) -> bool:
        policy = self.policy(mode)
        name = str(modality or "").strip().casefold()
        if name in {"camera", "live_camera"}:
            # Live camera is never ambient-by-default, even in public modes.
            return policy.camera and bool(explicit_consent)
        return bool({
            "screen": policy.screen,
            "window": policy.screen,
            "microphone": policy.microphone,
            "audio": policy.microphone,
            "system_audio": policy.system_audio,
            "photo": policy.photos,
            "image": policy.photos,
            "browser": policy.browser,
        }.get(name, False))

    def should_inspect(self, *, source_id: Any, change_signature: Any, importance: float = 0.5,
                       requested_by_mary: bool = False, creator_requested: bool = False) -> dict[str, Any]:
        source = str(source_id or "surface")[:120]
        signature = str(change_signature or "")[:240]
        previous = self._last_signature.get(source)
        changed = bool(signature and signature != previous)
        if signature:
            self._last_signature[source] = signature
        score = max(0.0, min(1.0, float(importance)))
        inspect = bool(creator_requested or requested_by_mary or (changed and score >= 0.35))
        return {
            "inspect": inspect,
            "changed": changed,
            "importance": score,
            "reason": "creator_requested" if creator_requested else "mary_requested" if requested_by_mary else "meaningful_change" if inspect else "no_meaningful_change",
        }

    @staticmethod
    def observation_context(observation: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "observation_id": str(observation.get("id") or "")[:120],
            "modality": str(observation.get("modality") or "unknown")[:60],
            "source": str(observation.get("source") or "unknown")[:120],
            "description": str(observation.get("description") or "")[:1400],
            "confidence": max(0.0, min(1.0, float(observation.get("confidence", 0.5)))),
            "authority": "environment_context_only",
            "durable": False,
        }
