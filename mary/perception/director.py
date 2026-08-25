"""Objective perception boundary for MaryV2.

Perception providers describe what was observed. Mary's cognition interprets
that description. This keeps a camera/screen/VLM from speaking in-character or
silently writing identity/memory state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from mary.realtime import AttentionBus, AttentionSource


_SENSITIVE = {"image", "frame", "screenshot", "pixels", "base64", "raw_image", "audio", "raw_audio"}


@dataclass(frozen=True)
class PerceptionObservation:
    description: str
    modality: str
    source: str
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id: str = field(default_factory=lambda: f"observation_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["authority"] = "environment_context_only"
        payload["durable"] = False
        return payload


class PerceptionDirector:
    VERSION = "13.1"

    def __init__(self, attention: AttentionBus | None = None, *, recent_limit: int = 64) -> None:
        self.attention = attention
        self.recent_limit = max(8, min(256, int(recent_limit)))
        self._recent: list[PerceptionObservation] = []

    @staticmethod
    def _sanitize(metadata: dict[str, Any] | None) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in dict(metadata or {}).items():
            normalized = str(key).casefold()
            if normalized in _SENSITIVE or any(marker in normalized for marker in ("token", "secret", "password", "api_key")):
                continue
            if isinstance(value, (bytes, bytearray, memoryview)):
                continue
            result[str(key)[:80]] = str(value)[:240] if not isinstance(value, (bool, int, float)) else value
        return result

    def observe(
        self,
        description: str,
        *,
        modality: str = "vision",
        source: str = "perception_provider",
        confidence: float = 0.5,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> PerceptionObservation:
        text = " ".join(str(description or "").split()).strip()[:1400]
        if not text:
            raise ValueError("Perception observations require a description.")
        observation = PerceptionObservation(
            description=text,
            modality=str(modality or "unknown")[:60],
            source=str(source or "perception_provider")[:100],
            confidence=max(0.0, min(1.0, float(confidence))),
            metadata=self._sanitize(metadata),
        )
        self._recent.append(observation)
        if len(self._recent) > self.recent_limit:
            del self._recent[: len(self._recent) - self.recent_limit]
        if self.attention is not None:
            self.attention.publish(
                AttentionSource.VISUAL if observation.modality in {"vision", "screen", "camera", "image"} else AttentionSource.BACKGROUND,
                observation.description,
                importance=max(0.0, min(1.0, float(importance))),
                metadata={
                    "observation_id": observation.id,
                    "modality": observation.modality,
                    "source": observation.source,
                    "confidence": observation.confidence,
                },
            )
        return observation

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "recent": [item.to_dict() for item in self._recent[-12:]],
            "policy": "providers describe; Mary interprets; raw media is not retained here and observations are not creator authority",
        }
