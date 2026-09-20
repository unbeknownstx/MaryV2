"""Bounded process-local media session registry.

A session attaches timestamped multimodal observations to an already-registered
PerceptionAsset. It is a derived view only: no raw media, memory promotion, or
world-model write occurs here.
"""
from __future__ import annotations

from collections import deque
from typing import Any

from .media_timeline import MediaObservation, build_media_observation_timeline, context_window


class MediaSessionRegistry:
    VERSION = "13.71"

    def __init__(self, capacity: int = 32, observations_per_asset: int = 600) -> None:
        self.capacity = max(4, min(256, int(capacity)))
        self.observations_per_asset = max(16, min(5000, int(observations_per_asset)))
        self._items: dict[str, deque[MediaObservation]] = {}
        self._order: deque[str] = deque()

    def _touch(self, asset_id: str) -> deque[MediaObservation]:
        key = str(asset_id or "").strip()[:240]
        if not key:
            raise ValueError("asset_id is required")
        if key not in self._items:
            self._items[key] = deque(maxlen=self.observations_per_asset)
            self._order.append(key)
        while len(self._order) > self.capacity:
            expired = self._order.popleft()
            self._items.pop(expired, None)
        return self._items[key]

    def observe(
        self, asset_id: str, *, at_seconds: float, kind: str, text: str,
        source: str, confidence: float = 1.0, previous_context: str = "",
    ) -> dict[str, Any]:
        item = MediaObservation(
            at_seconds, kind, text, source, confidence, previous_context
        )
        self._touch(asset_id).append(item)
        return item.to_dict()

    def timeline(self, asset_id: str) -> dict[str, Any]:
        items = list(self._touch(asset_id))
        return build_media_observation_timeline(
            asset_id, items, max_observations=self.observations_per_asset
        ).to_dict()

    def context(self, asset_id: str, *, at_seconds: float) -> list[dict[str, Any]]:
        items = list(self._touch(asset_id))
        timeline = build_media_observation_timeline(
            asset_id, items, max_observations=self.observations_per_asset
        )
        return context_window(timeline, at_seconds=at_seconds)

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "sessions": len(self._items),
            "observations": sum(len(v) for v in self._items.values()),
            "authority": "derived_perception_evidence",
            "raw_media_stored": False,
            "persistence": "process_local",
        }
