"""Bounded asset metadata registry for Mary's perception and Creator Lab.

The registry records provenance and semantic grounding, never raw media bytes.
Surfaces or capability nodes remain responsible for temporary/local media storage.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


@dataclass
class PerceptionAsset:
    asset_id: str
    kind: str
    source: str
    mime_type: str
    content_sha256: str
    byte_count: int
    created_at: str
    description: str = ""
    description_source: str = "unseen_asset"
    provider: str = ""
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PerceptionAssetRegistry:
    """Process-local bounded metadata registry; no identity or memory authority."""

    def __init__(self, capacity: int = 128) -> None:
        self.capacity = max(8, min(2048, int(capacity)))
        self._items: dict[str, PerceptionAsset] = {}
        self._order: deque[str] = deque()

    def register(
        self,
        *,
        kind: Any,
        source: Any,
        mime_type: Any = "",
        content_sha256: Any = "",
        byte_count: Any = 0,
    ) -> dict[str, Any]:
        digest = _text(content_sha256, 64).lower()
        if digest and (len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest)):
            raise ValueError("content_sha256 must be a SHA-256 hex digest.")
        try:
            size = max(0, min(64 * 1024 * 1024, int(byte_count or 0)))
        except (TypeError, ValueError) as exc:
            raise ValueError("byte_count must be an integer.") from exc
        item = PerceptionAsset(
            asset_id=f"asset_{uuid4().hex}",
            kind=_text(kind or "image", 40).casefold(),
            source=_text(source or "surface", 120),
            mime_type=_text(mime_type, 100).casefold(),
            content_sha256=digest,
            byte_count=size,
            created_at=_now(),
        )
        self._items[item.asset_id] = item
        self._order.append(item.asset_id)
        while len(self._order) > self.capacity:
            expired = self._order.popleft()
            self._items.pop(expired, None)
        return item.to_dict()

    def describe(
        self,
        asset_id: Any,
        *,
        description: Any,
        provider: Any = "",
        model: Any = "",
        description_source: Any = "perception_capability",
    ) -> dict[str, Any]:
        key = _text(asset_id, 120)
        item = self._items.get(key)
        if item is None:
            raise ValueError("Unknown perception asset.")
        text = _text(description, 12_000)
        if not text:
            raise ValueError("A grounded description is required.")
        item.description = text
        item.description_source = _text(description_source, 80) or "perception_capability"
        item.provider = _text(provider, 80)
        item.model = _text(model, 180)
        return item.to_dict()

    def get(self, asset_id: Any) -> dict[str, Any]:
        item = self._items.get(_text(asset_id, 120))
        if item is None:
            raise ValueError("Unknown perception asset.")
        return item.to_dict()

    def status(self, limit: int = 12) -> dict[str, Any]:
        ids = list(self._order)[-max(1, min(64, int(limit))):]
        return {
            "authority": "ephemeral_perception_asset_metadata",
            "raw_media_stored": False,
            "count": len(self._items),
            "recent": [self._items[key].to_dict() for key in reversed(ids) if key in self._items],
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
