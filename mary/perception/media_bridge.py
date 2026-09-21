"""Connect registered media assets to Mary's existing PerceptionDirector.

Timeline observations stay derived evidence. This bridge lets cognition consume
a bounded temporal window through the same objective perception boundary used
by cameras/screens, without promoting observations into memory or world truth.
"""
from __future__ import annotations

from typing import Any

from .director import PerceptionDirector
from .media_sessions import MediaSessionRegistry


def publish_media_context(
    sessions: MediaSessionRegistry,
    director: PerceptionDirector,
    *,
    asset_id: str,
    at_seconds: float,
    importance: float = 0.55,
) -> list[dict[str, Any]]:
    published: list[dict[str, Any]] = []
    for item in sessions.context(asset_id, at_seconds=at_seconds):
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        kind = str(item.get("kind") or "media").strip().lower()
        modality = "vision" if kind in {"vision", "frame", "image"} else "audio" if kind in {"speech", "audio", "transcript"} else "media"
        observation = director.observe(
            text,
            modality=modality,
            source=f"media_timeline:{str(item.get('source') or 'unknown')[:80]}",
            confidence=float(item.get("confidence", 0.5) or 0.5),
            importance=importance,
            metadata={
                "asset_id": str(asset_id)[:120],
                "at_seconds": float(item.get("at_seconds", 0.0) or 0.0),
                "temporal_context": True,
            },
        )
        published.append(observation.to_dict())
    return published
